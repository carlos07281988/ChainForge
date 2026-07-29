# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""BehaviorFingerprint — statistical snapshot of agent behavior over a time window."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class BehaviorFingerprint:
    """Statistical fingerprint of agent behavior over a time window.

    Captures key behavioral dimensions that can be compared to detect drift.
    """

    output_length_mean: float
    output_length_std: float
    tool_call_freq: dict[str, float]
    refusal_rate: float
    sentiment_score_mean: float
    latency_ms_mean: float
    tokens_per_call_mean: float
    sample_count: int
    window_start: float
    window_end: float

    @classmethod
    def from_samples(cls, samples: list[dict]) -> BehaviorFingerprint:
        """Create a fingerprint from a list of raw sample dictionaries.

        Each sample dict should contain:
            output_length: int
            tool_names: list[str]
            is_refusal: bool
            sentiment_score: float
            latency_ms: float
            tokens: int

        Window bounds are derived from the first and last sample
        (or set to 0 if samples is empty).
        """
        if not samples:
            return cls(
                output_length_mean=0.0,
                output_length_std=0.0,
                tool_call_freq={},
                refusal_rate=0.0,
                sentiment_score_mean=0.0,
                latency_ms_mean=0.0,
                tokens_per_call_mean=0.0,
                sample_count=0,
                window_start=0.0,
                window_end=0.0,
            )

        n = len(samples)

        # --- output length ---
        output_lengths = [s["output_length"] for s in samples]
        ol_mean = _mean(output_lengths)
        ol_std = _std(output_lengths, ol_mean)

        # --- tool call frequency ---
        tool_counts: dict[str, int] = {}
        for s in samples:
            for t in s.get("tool_names", []):
                tool_counts[t] = tool_counts.get(t, 0) + 1
        total_tool_calls = sum(tool_counts.values())
        tool_freq = (
            {k: v / total_tool_calls for k, v in tool_counts.items()}
            if total_tool_calls > 0
            else {}
        )

        # --- refusal rate ---
        refusal_rate = sum(1 for s in samples if s.get("is_refusal", False)) / n

        # --- sentiment ---
        sentiment_scores = [s.get("sentiment_score", 0.0) for s in samples]
        sentiment_mean = _mean(sentiment_scores)

        # --- latency ---
        latencies = [s["latency_ms"] for s in samples]
        latency_mean = _mean(latencies)

        # --- tokens per call ---
        tokens_list = [s["tokens"] for s in samples]
        tokens_mean = _mean(tokens_list)

        # --- window ---
        window_start = float(samples[0].get("timestamp", 0.0) if "timestamp" in samples[0] else 0.0)
        window_end = float(samples[-1].get("timestamp", 0.0) if "timestamp" in samples[-1] else 0.0)

        return cls(
            output_length_mean=ol_mean,
            output_length_std=ol_std,
            tool_call_freq=tool_freq,
            refusal_rate=refusal_rate,
            sentiment_score_mean=sentiment_mean,
            latency_ms_mean=latency_mean,
            tokens_per_call_mean=tokens_mean,
            sample_count=n,
            window_start=window_start,
            window_end=window_end,
        )

    def distance(self, other: BehaviorFingerprint) -> float:
        """Compute normalized Euclidean distance between two fingerprints.

        Returns a float in [0, 1].  > 0.2 is considered significant drift.
        Each of the 7 dimensions is normalized and equally weighted.
        """
        dims: list[tuple[float, float]] = []

        # 1. output_length_mean  (scale 500 — meaningful threshold)
        dims.append(_norm_pair(self.output_length_mean, other.output_length_mean, 500.0))

        # 2. output_length_std  (scale 200)
        dims.append(_norm_pair(self.output_length_std, other.output_length_std, 200.0))

        # 3. tool_call_freq — Jaccard + cosine hybrid
        dims.append(_tool_freq_distance(self.tool_call_freq, other.tool_call_freq))

        # 4. refusal_rate  (scale 0.1 — tiny rate changes matter)
        dims.append(_norm_pair(self.refusal_rate, other.refusal_rate, 0.1))

        # 5. sentiment_score_mean  (scale 0.5 — range -1..1)
        dims.append(_norm_pair(self.sentiment_score_mean + 1.0, other.sentiment_score_mean + 1.0, 0.5))

        # 6. latency_ms_mean  (scale 1000)
        dims.append(_norm_pair(self.latency_ms_mean, other.latency_ms_mean, 1000.0))

        # 7. tokens_per_call_mean  (scale 500)
        dims.append(_norm_pair(self.tokens_per_call_mean, other.tokens_per_call_mean, 500.0))

        # Euclidean distance across 7 dimensions, normalized by sqrt(7)
        sum_sq = sum(d * d for d in dims)
        return math.sqrt(sum_sq) / math.sqrt(len(dims))

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON reporting."""
        return {
            "output_length_mean": self.output_length_mean,
            "output_length_std": self.output_length_std,
            "tool_call_freq": self.tool_call_freq,
            "refusal_rate": self.refusal_rate,
            "sentiment_score_mean": self.sentiment_score_mean,
            "latency_ms_mean": self.latency_ms_mean,
            "tokens_per_call_mean": self.tokens_per_call_mean,
            "sample_count": self.sample_count,
            "window_start": self.window_start,
            "window_end": self.window_end,
        }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float], mean_val: float | None = None) -> float:
    if len(values) < 2:
        return 0.0
    m = mean_val if mean_val is not None else _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def _norm_pair(a: float, b: float, scale: float) -> float:
    """Normalized absolute difference clamped to [0, 1]."""
    if scale <= 0:
        return 0.0
    return min(abs(a - b) / scale, 1.0)


def _tool_freq_distance(a: dict[str, float], b: dict[str, float]) -> float:
    """Hybrid tool-frequency distance in [0, 1].

    Combines:
      - Cosine similarity of the shared-key vectors (weight 0.7)
      - Jaccard-style coverage penalty for key drift (weight 0.3)
    """
    all_keys = set(a) | set(b)
    if not all_keys:
        return 0.0

    # Cosine similarity over the union key space
    vec_a = [a.get(k, 0.0) for k in all_keys]
    vec_b = [b.get(k, 0.0) for k in all_keys]
    dot = sum(va * vb for va, vb in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(va * va for va in vec_a))
    norm_b = math.sqrt(sum(vb * vb for vb in vec_b))
    cosine = 0.0
    if norm_a > 0 and norm_b > 0:
        cosine = dot / (norm_a * norm_b)
    cosine_dist = (1.0 - cosine) / 2.0  # map [-1,1] → [0,1]

    # Jaccard-style coverage penalty
    shared = set(a) & set(b)
    jaccard = len(shared) / len(all_keys) if all_keys else 1.0
    jaccard_penalty = 1.0 - jaccard

    return 0.7 * cosine_dist + 0.3 * jaccard_penalty
