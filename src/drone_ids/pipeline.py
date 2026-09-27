"""End-to-end generation, IDS streaming, and report writing."""

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from .detector import DroneIDS
from .metrics import classification_report
from .public_benchmark import evaluate as evaluate_public
from .synthetic import FIELDS, generate_rows, write_dataset


def run_synthetic_demo(out_dir, runs=30, duration_s=120, rate_hz=2, seed=20260927):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = write_dataset(out_dir / "synthetic_uav_ids.csv", runs, duration_s, rate_hz, seed)
    alerts_path = out_dir / "alerts.csv"
    ids = DroneIDS()
    truth, predicted, alert_rows = [], [], []
    first_alert = {}
    activation_by_run = {}
    with dataset_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            expected = row["label"]
            activation_by_run.setdefault(row["run_id"], float(row["attack_start_s"]))
            alerts = ids.inspect(row)
            found = alerts[0]["attack_type"] if alerts else "normal"
            truth.append(expected)
            predicted.append(found)
            for alert in alerts:
                alert_rows.append(alert)
                key = (alert["run_id"], alert["attack_type"])
                first_alert.setdefault(key, float(alert["time_s"]))
    alert_fields = ["run_id", "time_s", "attack_type", "rule", "observed", "threshold", "severity", "explanation"]
    with alerts_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=alert_fields)
        writer.writeheader()
        writer.writerows(alert_rows)
    incidents = defaultdict(list)
    for alert in alert_rows:
        incidents[(alert["run_id"], alert["attack_type"])].append(alert)
    incident_path = out_dir / "alert_incidents.csv"
    with incident_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["run_id", "attack_type", "first_time_s", "last_time_s", "alert_count", "severity", "rule"])
        writer.writeheader()
        for (run_id, attack_type), items in sorted(incidents.items()):
            writer.writerow({"run_id": run_id, "attack_type": attack_type,
                             "first_time_s": items[0]["time_s"], "last_time_s": items[-1]["time_s"],
                             "alert_count": len(items), "severity": items[0]["severity"],
                             "rule": items[0]["rule"]})

    labels = ["normal", "gps_spoof", "command_injection", "telemetry_tampering", "communication_dos", "firmware_integrity"]
    metrics = classification_report(truth, predicted, labels)
    binary = classification_report(
        ["attack" if label != "normal" else "normal" for label in truth],
        ["attack" if label != "normal" else "normal" for label in predicted],
        ["normal", "attack"],
    )
    metrics["binary_detection"] = {
        "accuracy": binary["accuracy"],
        "precision": binary["per_class"]["attack"]["precision"],
        "recall": binary["per_class"]["attack"]["recall"],
        "f1": binary["per_class"]["attack"]["f1"],
        "false_positive_rate": 1.0 - binary["per_class"]["normal"]["recall"],
    }
    metrics.update({
        "dataset": "generated synthetic flight/sensor stream",
        "runs": runs,
        "duration_s": duration_s,
        "rate_hz": rate_hz,
        "seed": seed,
        "rows": len(truth),
        "alerts": len(alert_rows),
        "attack_detection_latency_s": {},
        "limitations": "Synthetic controlled scenarios only; not a flight-dynamics or field-performance claim.",
    })
    per_run_counts = Counter()
    for label in truth:
        per_run_counts[label] += 1
    metrics["class_counts"] = dict(per_run_counts)
    # The expected attack begins at 42% of the run. Compare first detection to
    # this known activation time. Misses are represented as null.
    for label in labels[1:]:
        delays = []
        for run in range(runs):
            if run % 6 == labels.index(label):
                detected = first_alert.get((f"run_{run:04d}", label))
                run_id = f"run_{run:04d}"
                delays.append(max(0.0, detected - activation_by_run[run_id]) if detected is not None else None)
        metrics["attack_detection_latency_s"][label] = delays
    metrics_path = out_dir / "synthetic_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return {"metrics": metrics, "dataset": str(dataset_path), "alerts": str(alerts_path),
            "incidents": str(incident_path), "metrics_path": str(metrics_path)}


def run_public_benchmark(data_path, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics, predictions = evaluate_public(data_path)
    metrics_path = out_dir / "uavids_2025_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    pred_path = out_dir / "uavids_2025_predictions.csv"
    with pred_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["FlowID", "truth", "prediction"])
        for row, prediction in predictions:
            writer.writerow([row["FlowID"], row["label"], prediction])
    return {"metrics": metrics, "metrics_path": str(metrics_path), "predictions_path": str(pred_path)}


def write_html_report(out_path, synthetic_metrics, network_metrics=None):
    out_path = Path(out_path)
    sections = []
    for title, metric in (("Synthetic cyber-physical IDS", synthetic_metrics), ("UAVIDS-2025 network benchmark", network_metrics)):
        if not metric:
            continue
        rows = []
        for label, score in metric["per_class"].items():
            rows.append("<tr><td>{}</td><td>{:.3f}</td><td>{:.3f}</td><td>{:.3f}</td><td>{}</td></tr>".format(
                html.escape(label), score["precision"], score["recall"], score["f1"], score["support"]))
        binary = metric.get("binary_detection")
        binary_line = (f"<p>Attack recall: {binary['recall']:.3%} · False-positive rate: {binary['false_positive_rate']:.3%} · "
                       f"Macro F1: {metric['macro_f1']:.3f}</p>") if binary else f"<p>Macro F1: {metric['macro_f1']:.3f}</p>"
        sections.append(f"<section><h2>{html.escape(title)}</h2><p>Accuracy: {metric['accuracy']:.3%} · Samples: {metric['samples']}</p>"
                        + binary_line
                        +
                        "<table><thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr></thead>"
                        f"<tbody>{''.join(rows)}</tbody></table></section>")
    page = "<!doctype html><html lang='en'><meta charset='utf-8'><title>Drone IDS Evaluation</title>" \
           "<style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 20px;color:#172033}" \
           "h1{color:#12345a}table{border-collapse:collapse;width:100%;margin:16px 0 34px}th,td{padding:9px 12px;border-bottom:1px solid #d9e1ea;text-align:left}" \
           "th{background:#edf3f8}section{margin:28px 0}.note{background:#fff7df;padding:12px 16px;border-left:4px solid #e1a300}</style>" \
           "<body><h1>Drone IDS Evaluation</h1><p class='note'>Synthetic sensor results and the public network-flow benchmark are separate experiments. Neither establishes field or physical-flight performance.</p>" \
           + "".join(sections) + "</body></html>"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def run_all(out_dir, public_data, runs=30, duration_s=120, rate_hz=2, seed=20260927):
    out_dir = Path(out_dir)
    synthetic = run_synthetic_demo(out_dir / "synthetic", runs, duration_s, rate_hz, seed)
    public = run_public_benchmark(public_data, out_dir / "public")
    report = write_html_report(out_dir / "index.html", synthetic["metrics"], public["metrics"])
    return {"synthetic": synthetic, "public": public, "html_report": str(report)}
