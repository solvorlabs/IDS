"""Small standard-library classification metrics."""

from collections import Counter


def classification_report(truth, predicted, labels=None):
    truth = list(truth)
    predicted = list(predicted)
    if len(truth) != len(predicted):
        raise ValueError("truth and predicted must have the same length")
    labels = list(labels or sorted(set(truth) | set(predicted)))
    matrix = {actual: Counter() for actual in labels}
    for actual, guess in zip(truth, predicted):
        matrix.setdefault(actual, Counter())[guess] += 1
    per_class = {}
    for label in labels:
        tp = matrix.get(label, Counter()).get(label, 0)
        support = sum(matrix.get(label, Counter()).values())
        predicted_count = sum(matrix.get(actual, Counter()).get(label, 0) for actual in matrix)
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
    correct = sum(actual == guess for actual, guess in zip(truth, predicted))
    macro_f1 = sum(item["f1"] for item in per_class.values()) / len(per_class) if per_class else 0.0
    return {
        "samples": len(truth),
        "accuracy": correct / len(truth) if truth else 0.0,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": {actual: {guess: matrix.get(actual, Counter()).get(guess, 0) for guess in labels} for actual in labels},
    }
