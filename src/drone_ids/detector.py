"""Explainable streaming rules for synthetic cyber-physical UAV traces."""

import math
from .synthetic import IDS_FEATURES


class DroneIDS:
    def __init__(self, gps_consistency_m=3.5, altitude_residual_m=5.0,
                 heartbeat_gap_s=1.5, packet_drop_rate=0.60):
        self.thresholds = {
            "gps_consistency_m": gps_consistency_m,
            "altitude_residual_m": altitude_residual_m,
            "heartbeat_gap_s": heartbeat_gap_s,
            "packet_drop_rate": packet_drop_rate,
        }

    @staticmethod
    def _num(row, key, default=0.0):
        try:
            return float(row.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    def inspect(self, row):
        # Guard against accidental label/truth leakage by reading only the whitelist.
        observed = {key: row.get(key) for key in IDS_FEATURES}
        alerts = []

        residual = math.hypot(
            self._num(observed, "gps_e_m") - self._num(observed, "odom_e_m"),
            self._num(observed, "gps_n_m") - self._num(observed, "odom_n_m"),
        )
        if residual > self.thresholds["gps_consistency_m"]:
            alerts.append(self._alert(row, "gps_spoof", "GPS/odometry disagreement", residual,
                                      self.thresholds["gps_consistency_m"], "high"))

        altitude_residual = abs(self._num(observed, "gps_alt_m") - self._num(observed, "baro_alt_m"))
        if altitude_residual > self.thresholds["altitude_residual_m"]:
            alerts.append(self._alert(row, "telemetry_tampering", "GPS/barometer altitude disagreement",
                                      altitude_residual, self.thresholds["altitude_residual_m"], "high"))

        if self._num(observed, "command_authorized", 1) < 1:
            alerts.append(self._alert(row, "command_injection", "Unapproved command observed",
                                      self._num(observed, "command_code"), "authorized command", "critical"))

        gap = self._num(observed, "heartbeat_gap_s")
        drop = self._num(observed, "packet_drop_rate")
        if gap > self.thresholds["heartbeat_gap_s"] or drop > self.thresholds["packet_drop_rate"]:
            alerts.append(self._alert(row, "communication_dos", "Heartbeat/link degradation",
                                      max(gap / self.thresholds["heartbeat_gap_s"],
                                          drop / self.thresholds["packet_drop_rate"]),
                                      "heartbeat or packet-loss threshold", "high"))

        if self._num(observed, "firmware_hash_match", 1) < 1:
            alerts.append(self._alert(row, "firmware_integrity", "Firmware measurement mismatch",
                                      0, "hash match required", "critical"))
        return alerts

    @staticmethod
    def _alert(row, attack_type, rule, observed, threshold, severity):
        return {
            "run_id": row.get("run_id", "unknown"),
            "time_s": row.get("time_s", ""),
            "attack_type": attack_type,
            "rule": rule,
            "observed": observed,
            "threshold": threshold,
            "severity": severity,
            "explanation": f"{rule}: observed {observed}, expected {threshold}",
        }


def detector_features():
    return list(IDS_FEATURES)
