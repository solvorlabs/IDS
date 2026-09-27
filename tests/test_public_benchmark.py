import unittest
from pathlib import Path

from src.drone_ids.public_benchmark import evaluate


DATA = Path(__file__).resolve().parents[1] / "data" / "external" / "UAVIDS-2025.csv"


@unittest.skipUnless(DATA.exists(), "downloaded public benchmark is not present")
class PublicBenchmarkTests(unittest.TestCase):
    def test_benchmark_runs_and_has_all_classes(self):
        report, predictions = evaluate(DATA)
        self.assertGreater(report["samples"], 1000)
        self.assertEqual(set(report["per_class"]), {
            "Normal Traffic", "Blackhole Attack", "Flooding Attack", "Sybil Attack", "Wormhole Attack"
        })
        self.assertEqual(len(predictions), report["test_samples"])
        self.assertGreater(report["accuracy"], 0.50)


if __name__ == "__main__":
    unittest.main()
