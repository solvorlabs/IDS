"""Gaussian Naive Bayes baseline for the public UAVIDS-2025 flow table."""

import csv
import math
from collections import defaultdict
from pathlib import Path

FEATURES = (
    "FlowDuration/s", "TxPackets", "RxPackets", "LostPackets", "TxBytes", "RxBytes",
    "TxPacketRate/s", "RxPacketRate/s", "TxByteRate/s", "RxByteRate/s",
    "MeanDelay/s", "MeanJitter/s", "Throughput/Kbps", "MeanPacketSize",
    "PacketDropRate", "AverageHopCount",
)


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        yield from csv.DictReader(stream)


def _vector(row):
    values = []
    for feature in FEATURES:
        value = float(row[feature])
        if not math.isfinite(value):
            raise ValueError(f"non-finite feature {feature}")
        values.append(value)
    return values


class GaussianNB:
    def __init__(self):
        self.classes = []
        self.stats = {}
        self.total = 0

    def fit(self, rows):
        sums, sums2, counts = defaultdict(lambda: [0.0] * len(FEATURES)), defaultdict(lambda: [0.0] * len(FEATURES)), defaultdict(int)
        for row in rows:
            label = row["label"].strip()
            vector = _vector(row)
            counts[label] += 1
            for i, value in enumerate(vector):
                sums[label][i] += value
                sums2[label][i] += value * value
        if not counts:
            raise ValueError("cannot fit on an empty dataset")
        self.total = sum(counts.values())
        self.classes = sorted(counts)
        self.stats = {}
        for label in self.classes:
            n = counts[label]
            means = [s / n for s in sums[label]]
            variances = []
            for i, mean in enumerate(means):
                var = max(0.0, sums2[label][i] / n - mean * mean)
                variances.append(max(var, max(1e-12, mean * mean * 1e-9)))
            self.stats[label] = {"count": n, "means": means, "variances": variances}
        return self

    def predict_one(self, row):
        vector = _vector(row)
        best, best_score = None, -math.inf
        for label in self.classes:
            stats = self.stats[label]
            score = math.log(stats["count"] / self.total)
            for value, mean, variance in zip(vector, stats["means"], stats["variances"]):
                delta = value - mean
                score -= 0.5 * (math.log(2.0 * math.pi * variance) + delta * delta / variance)
            if score > best_score:
                best, best_score = label, score
        return best

    def predict(self, rows):
        return [self.predict_one(row) for row in rows]


def evaluate(path):
    # FlowID modulo 5 creates a deterministic 20% holdout without using IP/ID
    # columns as model features. This is a row-level benchmark, not a held-out
    # capture/day split; correlated flows may make it optimistic.
    rows = list(read_rows(path))
    train = [r for r in rows if int(r["FlowID"]) % 5 != 0]
    test = [r for r in rows if int(r["FlowID"]) % 5 == 0]
    model = GaussianNB().fit(train)
    predictions = model.predict(test)
    from .metrics import classification_report
    report = classification_report([r["label"].strip() for r in test], predictions, model.classes)
    report.update({"dataset": "UAVIDS-2025", "split": "FlowID mod 5 held-out rows",
                   "train_samples": len(train), "test_samples": len(test),
                   "features": list(FEATURES), "model": "Gaussian Naive Bayes (standard-library implementation)"})
    return report, list(zip(test, predictions))
