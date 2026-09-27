"""Command-line entry points for the Drone IDS testbed."""

import argparse
import json
from pathlib import Path

from .pipeline import run_all, run_public_benchmark, run_synthetic_demo
from .sih import augment_sih_trace, import_sih_topic_csvs
from .synthetic import write_dataset


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate UAV cyber data and run an explainable Drone IDS.")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="write a labeled synthetic UAV trace")
    gen.add_argument("--out", default="data/generated/synthetic_uav_ids.csv")
    gen.add_argument("--runs", type=int, default=120)
    gen.add_argument("--duration", type=int, default=120)
    gen.add_argument("--rate", type=int, default=5)
    gen.add_argument("--seed", type=int, default=20260927)

    demo = sub.add_parser("demo", help="generate traces and run the streaming IDS")
    demo.add_argument("--out", default="reports/demo")
    demo.add_argument("--runs-per-class", type=int, default=20)
    demo.add_argument("--duration", type=int, default=120)
    demo.add_argument("--rate", type=int, default=5)
    demo.add_argument("--seed", type=int, default=20260927)

    bench = sub.add_parser("benchmark", help="evaluate network-flow baseline on UAVIDS-2025")
    bench.add_argument("--data", default="data/external/UAVIDS-2025.csv")
    bench.add_argument("--out", default="reports/public")

    all_cmd = sub.add_parser("all", help="run synthetic demo and public benchmark")
    all_cmd.add_argument("--out", default="reports/latest")
    all_cmd.add_argument("--data", default="data/external/UAVIDS-2025.csv")
    all_cmd.add_argument("--runs", type=int, default=120)
    all_cmd.add_argument("--duration", type=int, default=120)
    all_cmd.add_argument("--rate", type=int, default=5)
    all_cmd.add_argument("--seed", type=int, default=20260927)

    sih = sub.add_parser("import-sih", help="normalize pyulog ulog2csv topic exports")
    sih.add_argument("--topics-dir", required=True)
    sih.add_argument("--out", default="data/generated/px4_sih_nominal.csv")

    augment = sub.add_parser("augment-sih", help="make matched synthetic attack variants from normalized SIH data")
    augment.add_argument("--input", default="data/generated/px4_sih_nominal.csv")
    augment.add_argument("--out", default="data/generated/px4_sih_attack_scenarios.csv")
    augment.add_argument("--seed", type=int, default=20260927)

    args = parser.parse_args(argv)
    if args.command == "generate":
        path = write_dataset(args.out, args.runs, args.duration, args.rate, args.seed)
        print(json.dumps({"dataset": str(path), "manifest": str(path.with_suffix('.manifest.json')),
                          "rows": args.runs * (args.duration * args.rate + 1), "seed": args.seed}, indent=2))
    elif args.command == "demo":
        result = run_synthetic_demo(args.out, args.runs_per_class * 6, args.duration, args.rate, args.seed)
        print(json.dumps({"metrics": result["metrics"], "dataset": result["dataset"], "alerts": result["alerts"]}, indent=2))
    elif args.command == "benchmark":
        result = run_public_benchmark(args.data, args.out)
        print(json.dumps({"metrics": result["metrics"], "report": result["metrics_path"]}, indent=2))
    elif args.command == "import-sih":
        path = import_sih_topic_csvs(args.topics_dir, args.out)
        print(json.dumps({"normalized_sih_trace": str(path)}, indent=2))
    elif args.command == "augment-sih":
        path = augment_sih_trace(args.input, args.out, args.seed)
        print(json.dumps({"sih_attack_dataset": str(path)}, indent=2))
    else:
        result = run_all(args.out, args.data, args.runs, args.duration, args.rate, args.seed)
        print(json.dumps({"synthetic_accuracy": result["synthetic"]["metrics"]["accuracy"],
                          "network_accuracy": result["public"]["metrics"]["accuracy"],
                          "html_report": result["html_report"]}, indent=2))


if __name__ == "__main__":
    main()
