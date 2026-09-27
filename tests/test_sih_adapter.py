import csv
import math
import tempfile
import unittest
from pathlib import Path

from src.drone_ids.detector import DroneIDS
from src.drone_ids.sih import augment_sih_trace, import_sih_topic_csvs


def _write_topic(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class SihAdapterTests(unittest.TestCase):
    def test_import_and_offline_attack_augmentation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            topics = root / "topics"
            topics.mkdir()
            local_rows, truth_rows, gps_rows, baro_rows = [], [], [], []
            for i in range(51):
                t = i * 500_000
                north, east = i * 0.1, i * 0.05
                lat0, lon0 = 19.0, 73.0
                lat = lat0 + north / 6378137.0 * 180.0 / math.pi
                lon = lon0 + east / (6378137.0 * math.cos(math.radians(lat0))) * 180.0 / math.pi
                base = {"timestamp": t, "x": north, "y": east, "z": -15.0,
                        "vx": 0.2, "vy": 0.1, "ax": 0.0, "ay": 0.0, "az": 0.0}
                local_rows.append(base)
                truth_rows.append(base)
                gps_rows.append({"timestamp": t, "latitude_deg": lat, "longitude_deg": lon,
                                 "altitude_msl_m": 100.0, "fix_type": 3})
                baro_rows.append({"timestamp": t, "pressure": 1000.0})
            local_fields = list(local_rows[0])
            _write_topic(topics / "flight_vehicle_local_position_0.csv", local_fields, local_rows)
            _write_topic(topics / "flight_vehicle_local_position_groundtruth_0.csv", local_fields, truth_rows)
            _write_topic(topics / "flight_sensor_gps_0.csv", list(gps_rows[0]), gps_rows)
            _write_topic(topics / "flight_sensor_baro_0.csv", list(baro_rows[0]), baro_rows)

            nominal = import_sih_topic_csvs(topics, root / "nominal.csv")
            with nominal.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 51)
            self.assertEqual(rows[-1]["label"], "normal")
            self.assertAlmostEqual(float(rows[-1]["odom_n_m"]), 5.0, places=4)

            augmented = augment_sih_trace(nominal, root / "augmented.csv", seed=13)
            with augmented.open(newline="", encoding="utf-8") as stream:
                data = list(csv.DictReader(stream))
            self.assertEqual(len(data), 51 * 6)
            ids = DroneIDS()
            for scenario in ("gps_spoof", "command_injection", "telemetry_tampering", "communication_dos", "firmware_integrity"):
                run = [r for r in data if r["scenario"] == scenario and r["is_attack"] == "1"]
                self.assertTrue(run, scenario)
                found = {a["attack_type"] for a in ids.inspect(run[-1])}
                self.assertIn(scenario, found, scenario)


if __name__ == "__main__":
    unittest.main()
