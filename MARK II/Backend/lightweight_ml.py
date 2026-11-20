"""
Vennela AI - Lightweight Machine Learning Module
Pure Python stubs and implementations replacing scikit-learn in lightweight mode.
"""

from __future__ import annotations
import math
from typing import Any, List, Sequence, Union


class StandardScaler:
    """Lightweight pure-Python stub for sklearn.preprocessing.StandardScaler."""

    def __init__(self, with_mean: bool = True, with_std: bool = True) -> None:
        self.with_mean = with_mean
        self.with_std = with_std
        self.mean_: List[float] = []
        self.scale_: List[float] = []

    def fit(self, X: Sequence[Sequence[float]], y: Any = None) -> StandardScaler:
        if not X or not X[0]:
            return self
        n_features = len(X[0])
        n_samples = len(X)
        self.mean_ = [sum(row[i] for row in X) / n_samples for i in range(n_features)]
        self.scale_ = [
            math.sqrt(sum((row[i] - self.mean_[i]) ** 2 for row in X) / n_samples) or 1.0
            for i in range(n_features)
        ]
        return self

    def transform(self, X: Sequence[Sequence[float]]) -> List[List[float]]:
        if not self.mean_ or not self.scale_:
            return [list(row) for row in X]
        return [
            [(val - self.mean_[i]) / self.scale_[i] for i, val in enumerate(row)]
            for row in X
        ]

    def fit_transform(self, X: Sequence[Sequence[float]], y: Any = None) -> List[List[float]]:
        return self.fit(X, y).transform(X)


class PCA:
    """Lightweight pure-Python stub for sklearn.decomposition.PCA."""

    def __init__(self, n_components: int = 2) -> None:
        self.n_components = n_components

    def fit(self, X: Sequence[Sequence[float]], y: Any = None) -> PCA:
        return self

    def transform(self, X: Sequence[Sequence[float]]) -> List[List[float]]:
        return [list(row[: self.n_components]) for row in X]

    def fit_transform(self, X: Sequence[Sequence[float]], y: Any = None) -> List[List[float]]:
        return self.transform(X)


def cosine_similarity(
    X: Sequence[Sequence[float]],
    Y: Sequence[Sequence[float]] | None = None,
) -> List[List[float]]:
    """Pure-Python cosine similarity computation without numpy or scipy."""
    if Y is None:
        Y = X
    if not X or not Y:
        return [[0.0]]

    results: List[List[float]] = []
    for x_row in X:
        row_scores: List[float] = []
        norm_x = math.sqrt(sum(val * val for val in x_row)) or 1e-9
        for y_row in Y:
            norm_y = math.sqrt(sum(val * val for val in y_row)) or 1e-9
            dot = sum(a * b for a, b in zip(x_row, y_row))
            row_scores.append(dot / (norm_x * norm_y))
        results.append(row_scores)
    return results
