import csv
import tempfile
import unittest
from pathlib import Path

from src.drone_ids.detector import DroneIDS
from src.drone_ids.metrics import classification_report
from src.drone_ids.synthetic import SCENARIOS, generate_rows, write_dataset


class SyntheticGeneratorTests(unittest.TestCase):
    def test_seed_reproduces_rows(self):
        self.assertEqual(list(generate_rows(runs=6, duration_s=20, rate_hz=1, seed=7)),
                         list(generate_rows(runs=6, duration_s=20, rate_hz=1, seed=7)))

    def test_all_scenarios_are_generated_and_labels_are_separate(self):
        rows = list(generate_rows(runs=6, duration_s=20, rate_hz=1, seed=8))
        self.assertEqual({row["scenario"] for row in rows}, set(SCENARIOS))
        self.assertTrue(all("truth_e_m" in row and "label" in row for row in rows))
        self.assertEqual({row["label"] for row in rows if not row["is_attack"]}, {"normal"})

    def test_csv_dataset_is_written_and_reloaded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_dataset(Path(folder) / "rows.csv", runs=6, duration_s=20, rate_hz=1, seed=9)
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 6 * 21)
            self.assertIn("firmware_hash_match", rows[0])
            manifest = path.with_suffix(".manifest.json")
            self.assertTrue(manifest.exists())


class DetectorTests(unittest.TestCase):
    def test_detects_every_injected_attack(self):
        ids = DroneIDS()
        rows = list(generate_rows(runs=6, duration_s=60, rate_hz=1, seed=10))
        for scenario in SCENARIOS[1:]:
            row = [r for r in rows if r["scenario"] == scenario and r["is_attack"]][-1]
            labels = {a["attack_type"] for a in ids.inspect(row)}
            self.assertIn(scenario, labels, scenario)

    def test_benign_rows_not_flagged(self):
        ids = DroneIDS()
        rows = list(generate_rows(runs=6, duration_s=90, rate_hz=2, seed=11))
        benign = [r for r in rows if r["scenario"] == "normal"]
        self.assertTrue(benign)
        self.assertEqual(sum(bool(ids.inspect(row)) for row in benign), 0)

    def test_labels_and_simulation_truth_do_not_change_detector_result(self):
        ids = DroneIDS()
        row = next(r for r in generate_rows(runs=6, duration_s=60, rate_hz=1, seed=12)
                   if r["scenario"] == "gps_spoof" and r["is_attack"])
        expected = ids.inspect(row)
        altered = dict(row, label="normal", truth_e_m=999999, scenario="normal")
        self.assertEqual(expected, ids.inspect(altered))


class MetricTests(unittest.TestCase):
    def test_classification_metrics(self):
        result = classification_report(["a", "a", "b"], ["a", "b", "b"], ["a", "b"])
        self.assertEqual(result["samples"], 3)
        self.assertAlmostEqual(result["accuracy"], 2 / 3)
        self.assertAlmostEqual(result["per_class"]["a"]["recall"], 0.5)


if __name__ == "__main__":
    unittest.main()
