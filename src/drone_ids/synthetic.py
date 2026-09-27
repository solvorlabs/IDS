"""Deterministic kinematic UAV and observation generator; no simulator dependency."""

import csv
import hashlib
import json
import math
import random
from collections import Counter
from pathlib import Path


SCENARIOS = (
    "normal",
    "gps_spoof",
    "command_injection",
    "telemetry_tampering",
    "communication_dos",
    "firmware_integrity",
)

FIELDS = [
    "run_id", "seed", "time_s", "attack_start_s", "scenario", "label", "is_attack",
    "truth_e_m", "truth_n_m", "truth_alt_m", "truth_v_e_mps", "truth_v_n_mps",
    "gps_e_m", "gps_n_m", "gps_alt_m", "odom_e_m", "odom_n_m", "baro_alt_m",
    "imu_acc_e_mps2", "imu_acc_n_mps2", "imu_acc_u_mps2", "battery_pct",
    "command_authorized", "command_code", "mavlink_msg_rate_hz", "heartbeat_gap_s",
    "packet_drop_rate", "mean_delay_ms", "firmware_hash_match",
]

# This list is the complete feature interface to the detector. In particular, it
# excludes label, scenario, truth state, and injected attack metadata.
IDS_FEATURES = (
    "gps_e_m", "gps_n_m", "gps_alt_m", "odom_e_m", "odom_n_m", "baro_alt_m",
    "command_authorized", "command_code", "mavlink_msg_rate_hz", "heartbeat_gap_s",
    "packet_drop_rate", "mean_delay_ms", "firmware_hash_match",
)


def _flight_state(t, route):
    """Smooth bounded local ENU route and its analytic velocity/acceleration."""
    w = 2.0 * math.pi / route["period"]
    phase_e, phase_n, phase_u = route["phase_e"], route["phase_n"], route["phase_u"]
    e = route["east_amp"] * math.sin(w * t + phase_e)
    n = route["north_amp"] * math.sin(0.5 * w * t + phase_n)
    alt = route["alt_base"] + route["alt_amp"] * math.sin(0.25 * w * t + phase_u)
    ve = route["east_amp"] * w * math.cos(w * t + phase_e)
    vn = route["north_amp"] * 0.5 * w * math.cos(0.5 * w * t + phase_n)
    ae = -route["east_amp"] * w * w * math.sin(w * t + phase_e)
    an = -route["north_amp"] * 0.25 * w * w * math.sin(0.5 * w * t + phase_n)
    au = -route["alt_amp"] * 0.0625 * w * w * math.sin(0.25 * w * t + phase_u)
    return e, n, alt, ve, vn, ae, an, au


def generate_rows(runs=30, duration_s=120, rate_hz=2, seed=20260927):
    if runs < len(SCENARIOS):
        raise ValueError(f"runs must be at least {len(SCENARIOS)} to include every scenario")
    if duration_s < 15 or rate_hz < 1 or rate_hz > 20:
        raise ValueError("duration_s must be >=15 and rate_hz must be between 1 and 20")
    rng = random.Random(seed)
    count = int(duration_s * rate_hz) + 1
    for run in range(runs):
        scenario = SCENARIOS[run % len(SCENARIOS)]
        run_seed = seed + run * 7919
        local_rng = random.Random(run_seed)
        route = {
            "east_amp": local_rng.uniform(14.0, 22.0),
            "north_amp": local_rng.uniform(8.0, 16.0),
            "alt_base": local_rng.uniform(12.0, 20.0),
            "alt_amp": local_rng.uniform(0.8, 2.0),
            "period": local_rng.uniform(65.0, 115.0),
            "phase_e": local_rng.uniform(-math.pi, math.pi),
            "phase_n": local_rng.uniform(-math.pi, math.pi),
            "phase_u": local_rng.uniform(-math.pi, math.pi),
        }
        activation_s = duration_s * local_rng.uniform(0.36, 0.50)
        gps_bias_e = local_rng.uniform(-0.5, 0.5)
        gps_bias_n = local_rng.uniform(-0.5, 0.5)
        for index in range(count):
            t = index / rate_hz
            truth_e, truth_n, truth_alt, ve, vn, ae, an, au = _flight_state(t, route)
            active = scenario != "normal" and t >= activation_s
            gps_e = truth_e + local_rng.gauss(0.0, 0.55) + gps_bias_e
            gps_n = truth_n + local_rng.gauss(0.0, 0.55) + gps_bias_n
            gps_alt = truth_alt + local_rng.gauss(0.0, 0.45)
            odom_e = truth_e + local_rng.gauss(0.0, 0.35)
            odom_n = truth_n + local_rng.gauss(0.0, 0.35)
            baro_alt = truth_alt + local_rng.gauss(0.0, 0.20)
            command_authorized = 1
            command_code = 16  # MAV_CMD_NAV_WAYPOINT, represented as a benign command class.
            msg_rate = max(0.0, 10.0 + local_rng.gauss(0.0, 0.6))
            heartbeat_gap = max(0.02, 0.10 + local_rng.gauss(0.0, 0.025))
            packet_drop = min(0.15, max(0.0, local_rng.gauss(0.025, 0.015)))
            delay_ms = max(2.0, 35.0 + local_rng.gauss(0.0, 7.0))
            firmware_ok = 1
            if active and scenario == "gps_spoof":
                ramp = min(1.0, (t - activation_s) / 18.0)
                gps_e += 8.0 * ramp
                gps_n -= 5.0 * ramp
            elif active and scenario == "command_injection":
                command_authorized = 0
                command_code = 999  # Synthetic unknown/unapproved command token.
            elif active and scenario == "telemetry_tampering":
                gps_alt += 18.0
            elif active and scenario == "communication_dos":
                msg_rate = max(0.0, 0.8 + local_rng.gauss(0.0, 0.25))
                heartbeat_gap = 3.0 + local_rng.random() * 0.5
                packet_drop = 0.82 + local_rng.random() * 0.15
                delay_ms = 800.0 + local_rng.random() * 300.0
            elif active and scenario == "firmware_integrity":
                firmware_ok = 0
            truth_label = scenario if active else "normal"
            yield {
                "run_id": f"run_{run:04d}", "seed": run_seed, "time_s": round(t, 3),
                "attack_start_s": round(activation_s, 3),
                "scenario": scenario, "label": truth_label, "is_attack": int(active),
                "truth_e_m": round(truth_e, 5), "truth_n_m": round(truth_n, 5),
                "truth_alt_m": round(truth_alt, 5), "truth_v_e_mps": round(ve, 5),
                "truth_v_n_mps": round(vn, 5), "gps_e_m": round(gps_e, 5),
                "gps_n_m": round(gps_n, 5), "gps_alt_m": round(gps_alt, 5),
                "odom_e_m": round(odom_e, 5), "odom_n_m": round(odom_n, 5),
                "baro_alt_m": round(baro_alt, 5), "imu_acc_e_mps2": round(ae + rng.gauss(0, 0.025), 5),
                "imu_acc_n_mps2": round(an + rng.gauss(0, 0.025), 5),
                "imu_acc_u_mps2": round(au + rng.gauss(0, 0.025), 5),
                "battery_pct": round(max(0.0, 100.0 - 0.06 * t + local_rng.gauss(0, 0.08)), 3),
                "command_authorized": command_authorized, "command_code": command_code,
                "mavlink_msg_rate_hz": round(msg_rate, 4), "heartbeat_gap_s": round(heartbeat_gap, 4),
                "packet_drop_rate": round(packet_drop, 5), "mean_delay_ms": round(delay_ms, 3),
                "firmware_hash_match": firmware_ok,
            }


def write_dataset(path, runs=30, duration_s=120, rate_hz=2, seed=20260927):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(generate_rows(runs, duration_s, rate_hz, seed))
    labels = Counter()
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            labels[row["label"]] += 1
    manifest = {
        "dataset": path.name,
        "generator": "drone_ids.synthetic.generate_rows",
        "generator_version": "0.1.0",
        "seed": seed,
        "runs": runs,
        "duration_s": duration_s,
        "rate_hz": rate_hz,
        "rows": runs * (int(duration_s * rate_hz) + 1),
        "scenarios": list(SCENARIOS),
        "class_counts": dict(sorted(labels.items())),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "truth_and_labels_are_ids_excluded": True,
        "description": "Deterministic synthetic local ENU flight path with noisy sensor and link observations; not field data.",
    }
    path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path
