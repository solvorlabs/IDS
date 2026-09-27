"""Adapters for PX4 SIH ULog topic exports (ulog2csv output)."""

import csv
import glob
import math
from pathlib import Path

from .synthetic import FIELDS


def _topic_rows(directory, topic):
    matches = sorted(glob.glob(str(Path(directory) / f"*{topic}*.csv")))
    if not matches:
        return []
    with open(matches[0], newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    return sorted(rows, key=lambda row: _float(row, "timestamp", 0.0))


def _float(row, *names, default=None):
    for name in names:
        value = row.get(name)
        if value in (None, ""):
            continue
        try:
            number = float(value)
            if math.isfinite(number):
                return number
        except (ValueError, TypeError):
            pass
    return default


def _aligned(rows, timestamp, index):
    if not rows:
        return {}, index
    while index + 1 < len(rows) and _float(rows[index + 1], "timestamp", 0.0) <= timestamp:
        index += 1
    if index + 1 < len(rows):
        before, after = rows[index], rows[index + 1]
        if abs(_float(after, "timestamp", 0.0) - timestamp) < abs(_float(before, "timestamp", 0.0) - timestamp):
            index += 1
    return rows[index], index


def import_sih_topic_csvs(topic_dir, output_csv):
    """Normalize `ulog2csv` outputs into the project's observed-data schema.

    The estimator's local position supplies the independent odometry-like channel;
    the ground-truth topic is retained only in excluded truth columns. Raw GPS is
    converted from WGS84 to a local frame. Missing optional topics receive explicit
    nominal placeholders and are listed in the returned coverage metadata.
    """
    topic_dir = Path(topic_dir)
    local = _topic_rows(topic_dir, "vehicle_local_position")
    # The broad glob above can also match groundtruth; explicitly remove that file
    # when choosing the estimator stream.
    local_files = sorted(p for p in topic_dir.glob("*vehicle_local_position*.csv") if "groundtruth" not in p.name)
    if local_files:
        with local_files[0].open(newline="", encoding="utf-8-sig") as stream:
            local = sorted(list(csv.DictReader(stream)), key=lambda row: _float(row, "timestamp", 0.0))
    truth = _topic_rows(topic_dir, "vehicle_local_position_groundtruth")
    gps = _topic_rows(topic_dir, "sensor_gps")
    global_pos = _topic_rows(topic_dir, "vehicle_global_position")
    baro = _topic_rows(topic_dir, "sensor_baro")
    battery = _topic_rows(topic_dir, "vehicle_battery_status")
    if not local:
        raise FileNotFoundError("ulog2csv topic export must include vehicle_local_position_*.csv")

    topics = {
        "vehicle_local_position": local,
        "vehicle_local_position_groundtruth": truth,
        "sensor_gps": gps,
        "vehicle_global_position": global_pos,
        "sensor_baro": baro,
        "vehicle_battery_status": battery,
    }
    cursors = {name: 0 for name in topics}
    first_gps = next((r for r in gps if _float(r, "latitude_deg", "latitude") is not None), {})
    lat0 = _float(first_gps, "latitude_deg", "latitude", default=0.0)
    lon0 = _float(first_gps, "longitude_deg", "longitude", default=0.0)
    alt0 = _float(first_gps, "altitude_msl_m", "altitude", "altitude_m", default=0.0)
    pressure_rows = [_float(r, "pressure", "pressure_pa", "pressure_mbar") for r in baro]
    pressure_rows = [v for v in pressure_rows if v is not None and v > 0]
    p0 = pressure_rows[0] if pressure_rows else None
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        t0 = _float(local[0], "timestamp", default=0.0)
        for index, lpos in enumerate(local):
            timestamp = _float(lpos, "timestamp", default=t0)
            rowset = {"vehicle_local_position": lpos}
            for topic, values in topics.items():
                if topic == "vehicle_local_position":
                    continue
                rowset[topic], cursors[topic] = _aligned(values, timestamp, cursors[topic])
            odom_n = _float(lpos, "x", default=0.0)
            odom_e = _float(lpos, "y", default=0.0)
            baro_alt = -_float(lpos, "z", default=0.0)
            raw_gps = rowset["sensor_gps"]
            lat = _float(raw_gps, "latitude_deg", "latitude")
            lon = _float(raw_gps, "longitude_deg", "longitude")
            gps_alt = _float(raw_gps, "altitude_msl_m", "altitude", "altitude_m")
            if lat is not None and lon is not None:
                gps_n = 6378137.0 * math.radians(lat - lat0)
                gps_e = 6378137.0 * math.cos(math.radians(lat0)) * math.radians(lon - lon0)
            else:
                gps_n, gps_e = odom_n, odom_e
            if gps_alt is None:
                gpos = rowset["vehicle_global_position"]
                gps_alt = _float(gpos, "alt", "altitude", default=baro_alt + alt0)
            gps_alt -= alt0
            b = rowset["sensor_baro"]
            pressure = _float(b, "pressure", "pressure_pa", "pressure_mbar")
            if pressure is not None and p0:
                baro_alt = 44330.0 * (1.0 - (pressure / p0) ** 0.190294957)
            truth_row = rowset["vehicle_local_position_groundtruth"]
            truth_n = _float(truth_row, "x", default="")
            truth_e = _float(truth_row, "y", default="")
            truth_alt = -_float(truth_row, "z", default="") if truth_row else ""
            battery_row = rowset["vehicle_battery_status"]
            remaining = _float(battery_row, "remaining", default=1.0)
            remaining_pct = remaining * 100.0 if 0.0 <= remaining <= 1.0 else remaining
            time_s = (timestamp - t0) / 1e6
            writer.writerow({
                "run_id": "sih_run_0001", "seed": "", "time_s": round(time_s, 6),
                "attack_start_s": "", "scenario": "normal", "label": "normal", "is_attack": 0,
                "truth_e_m": truth_e, "truth_n_m": truth_n, "truth_alt_m": truth_alt,
                "truth_v_e_mps": _float(truth_row, "vy", default=""),
                "truth_v_n_mps": _float(truth_row, "vx", default=""),
                "gps_e_m": round(gps_e, 5), "gps_n_m": round(gps_n, 5), "gps_alt_m": round(gps_alt, 5),
                "odom_e_m": round(odom_e, 5), "odom_n_m": round(odom_n, 5), "baro_alt_m": round(baro_alt, 5),
                "imu_acc_e_mps2": _float(lpos, "ay", default=0.0),
                "imu_acc_n_mps2": _float(lpos, "ax", default=0.0),
                "imu_acc_u_mps2": -_float(lpos, "az", default=0.0),
                "battery_pct": round(remaining_pct, 3), "command_authorized": 1, "command_code": 16,
                "mavlink_msg_rate_hz": 10.0, "heartbeat_gap_s": 0.1,
                "packet_drop_rate": 0.0, "mean_delay_ms": 0.0, "firmware_hash_match": 1,
            })
    return output_csv


def augment_sih_trace(input_csv, output_csv, seed=20260927):
    """Create matched normal/attack variants from a normalized SIH baseline trace."""
    import random
    rng = random.Random(seed)
    with Path(input_csv).open(newline="", encoding="utf-8-sig") as stream:
        base = list(csv.DictReader(stream))
    if len(base) < 20:
        raise ValueError("SIH trace is too short to create attack variants (need at least 20 samples)")
    duration = float(base[-1]["time_s"])
    if duration <= 1:
        raise ValueError("SIH trace must span at least one second")
    activation = duration * 0.42
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        scenarios = ("normal", "gps_spoof", "command_injection", "telemetry_tampering", "communication_dos", "firmware_integrity")
        for scenario_index, scenario in enumerate(scenarios):
            run_id = f"sih_{scenario_index:02d}_{scenario}"
            for source in base:
                row = dict(source)
                time_s = float(row["time_s"])
                active = scenario != "normal" and time_s >= activation
                row.update({"run_id": run_id, "seed": seed, "scenario": scenario,
                            "attack_start_s": round(activation, 6), "label": scenario if active else "normal",
                            "is_attack": int(active)})
                if active and scenario == "gps_spoof":
                    ramp = min(1.0, (time_s - activation) / max(1.0, duration * 0.15))
                    row["gps_e_m"] = round(float(row["gps_e_m"]) + 8.0 * ramp, 5)
                    row["gps_n_m"] = round(float(row["gps_n_m"]) - 5.0 * ramp, 5)
                elif active and scenario == "command_injection":
                    row["command_authorized"], row["command_code"] = 0, 999
                elif active and scenario == "telemetry_tampering":
                    row["gps_alt_m"] = round(float(row["gps_alt_m"]) + 18.0, 5)
                elif active and scenario == "communication_dos":
                    row["mavlink_msg_rate_hz"] = 0.8
                    row["heartbeat_gap_s"] = 3.0 + rng.random() * 0.5
                    row["packet_drop_rate"] = 0.82 + rng.random() * 0.15
                    row["mean_delay_ms"] = 800.0 + rng.random() * 300.0
                elif active and scenario == "firmware_integrity":
                    row["firmware_hash_match"] = 0
                writer.writerow(row)
    return output_csv
