# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""DriftDetector — compares current agent behavior against a baseline fingerprint."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from chainforge.enterprise.drift.fingerprint import BehaviorFingerprint

# ---------------------------------------------------------------------------
# DimensionDrift
# ---------------------------------------------------------------------------


@dataclass
class DimensionDrift:
    """Per-dimension drift measurement."""

    dimension_name: str
    current_value: float
    baseline_value: float
    drift_score: float

    def to_dict(self) -> dict:
        return {
            "dimension_name": self.dimension_name,
            "current_value": self.current_value,
            "baseline_value": self.baseline_value,
            "drift_score": self.drift_score,
        }


# ---------------------------------------------------------------------------
# DriftReport
# ---------------------------------------------------------------------------


@dataclass
class DriftReport:
    """Full drift detection report."""

    overall_drift: float
    dimension_drifts: list[dict]
    likely_causes: list[str]
    recommendation: str
    severity: str  # none / mild / moderate / significant / severe

    def to_json(self) -> dict:
        return {
            "overall_drift": self.overall_drift,
            "dimension_drifts": self.dimension_drifts,
            "likely_causes": self.likely_causes,
            "recommendation": self.recommendation,
            "severity": self.severity,
        }


# ---------------------------------------------------------------------------
# DriftDetector
# ---------------------------------------------------------------------------


class DriftDetector:
    """Monitors agent behavior for drift relative to a baseline window.

    Samples are collected via the middleware() hook or added directly
    via ``add_sample()``.  The baseline is computed from samples that
    fall within ``baseline_window_days`` days.
    """

    def __init__(self, baseline_window_days: int = 7):
        self._baseline_window_secs = baseline_window_days * 86400
        self._samples: list[dict] = []

    # ---- sample collection -------------------------------------------------

    def add_sample(self, sample: dict) -> None:
        """Record a raw sample dict."""
        if "timestamp" not in sample:
            sample["timestamp"] = time.time()
        self._samples.append(sample)

    def middleware(self):
        """Return a callable middleware suitable for wrapping agent calls.

        Usage::

            detector = DriftDetector()
            wrapped = detector.middleware()

            result = wrapped(original_handler, **kwargs)
        """

        def _middleware(handler, *args, **kwargs):
            t0 = time.time()
            try:
                result = handler(*args, **kwargs)
            except Exception as exc:
                elapsed = (time.time() - t0) * 1000
                self.add_sample({
                    "output_length": 0,
                    "tool_names": [],
                    "is_refusal": True,
                    "sentiment_score": 0.0,
                    "latency_ms": elapsed,
                    "tokens": 0,
                })
                raise exc

            elapsed = (time.time() - t0) * 1000
            output = result if isinstance(result, str) else str(result)
            tools = kwargs.get("tool_names", []) or []

            self.add_sample({
                "output_length": len(output),
                "tool_names": list(tools),
                "is_refusal": _is_refusal_text(output),
                "sentiment_score": 0.0,  # placeholder — wire in real sentiment
                "latency_ms": elapsed,
                "tokens": kwargs.get("token_count", 0),
            })
            return result

        return _middleware

    # ---- fingerprints ------------------------------------------------------

    def current_fingerprint(self) -> BehaviorFingerprint:
        """Fingerprint from all collected samples."""
        return BehaviorFingerprint.from_samples(self._samples)

    def baseline_fingerprint(self) -> BehaviorFingerprint:
        """Fingerprint from samples within the baseline window only."""
        now = time.time()
        cutoff = now - self._baseline_window_secs
        baseline_samples = [s for s in self._samples if s.get("timestamp", 0) >= cutoff]
        return BehaviorFingerprint.from_samples(baseline_samples)

    # ---- detection ---------------------------------------------------------

    def detect(self, current: BehaviorFingerprint | None = None) -> DriftReport:
        """Compare current behavior against the baseline and return a report.

        If *current* is not provided it is derived from all collected samples.
        """
        current_fp = current or self.current_fingerprint()
        baseline_fp = self.baseline_fingerprint()

        overall = current_fp.distance(baseline_fp)

        # Per-dimension drifts
        dims = _build_dimension_drifts(current_fp, baseline_fp)

        # Causes
        causes = _infer_causes(dims)

        # Recommendation + severity
        severity, recommendation = _classify(overall)

        return DriftReport(
            overall_drift=round(overall, 4),
            dimension_drifts=[d.to_dict() for d in dims],
            likely_causes=causes,
            recommendation=recommendation,
            severity=severity,
        )


# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------

_REFUSAL_PATTERNS = [
    "I cannot", "I'm unable", "I can't", "I'm sorry",
    "unable to", "cannot assist", "against my guidelines",
    "not appropriate", "against policy",
]


def _is_refusal_text(text: str) -> bool:
    lower = text.lower()
    return any(p.lower() in lower for p in _REFUSAL_PATTERNS)


def _build_dimension_drifts(current: BehaviorFingerprint, baseline: BehaviorFingerprint) -> list[DimensionDrift]:
    """Compare each numeric dimension between current and baseline."""
    from chainforge.enterprise.drift.fingerprint import _tool_freq_distance  # type: ignore[import-untyped]

    dims: list[DimensionDrift] = []

    dims.append(DimensionDrift("output_length_mean", current.output_length_mean, baseline.output_length_mean,
                               _dim_score(current.output_length_mean, baseline.output_length_mean, 500.0)))
    dims.append(DimensionDrift("output_length_std", current.output_length_std, baseline.output_length_std,
                               _dim_score(current.output_length_std, baseline.output_length_std, 200.0)))
    dims.append(DimensionDrift("tool_call_freq", 1.0, 1.0,
                               _tool_freq_distance(current.tool_call_freq, baseline.tool_call_freq)))
    dims.append(DimensionDrift("refusal_rate", current.refusal_rate, baseline.refusal_rate,
                               _dim_score(current.refusal_rate, baseline.refusal_rate, 0.1)))
    dims.append(DimensionDrift("sentiment_score_mean", current.sentiment_score_mean, baseline.sentiment_score_mean,
                               _dim_score(current.sentiment_score_mean + 1.0, baseline.sentiment_score_mean + 1.0, 0.5)))
    dims.append(DimensionDrift("latency_ms_mean", current.latency_ms_mean, baseline.latency_ms_mean,
                               _dim_score(current.latency_ms_mean, baseline.latency_ms_mean, 1000.0)))
    dims.append(DimensionDrift("tokens_per_call_mean", current.tokens_per_call_mean, baseline.tokens_per_call_mean,
                               _dim_score(current.tokens_per_call_mean, baseline.tokens_per_call_mean, 500.0)))

    return dims


def _dim_score(current: float, baseline: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return min(abs(current - baseline) / scale, 1.0)


def _infer_causes(dims: list[DimensionDrift]) -> list[str]:
    """Heuristic inference of likely causes from the most-drifted dimensions."""
    causes: list[str] = []
    for d in sorted(dims, key=lambda x: x.drift_score, reverse=True):
        if d.drift_score <= 0.1:
            continue
        name = d.dimension_name
        cur = d.current_value
        base = d.baseline_value
        if name == "refusal_rate" and cur > base:
            causes.append("Increase in refusal rate — possible prompt safety filter changes")
        elif name == "latency_ms_mean" and cur > base:
            causes.append("Elevated latency — possible model endpoint degradation or rate limiting")
        elif name == "tool_call_freq":
            causes.append("Tool usage pattern shift — possible prompt or capability change")
        elif name == "sentiment_score_mean" and cur < base:
            causes.append("Sentiment decline — possible model version or temperature change")
        elif name == "tokens_per_call_mean" and cur > base:
            causes.append("Token usage increase — possible verbosity or prompt bloat")
        if len(causes) >= 3:
            break
    return causes if causes else ["No clear cause identified — review dimension drifts manually"]


def _classify(overall: float) -> tuple[str, str]:
    """Map overall drift score to severity + recommended action."""
    if overall < 0.05:
        return "none", "none"
    elif overall < 0.10:
        return "mild", "monitor"
    elif overall < 0.20:
        return "moderate", "run_benchmarks"
    elif overall < 0.35:
        return "significant", "recommend_rollback"
    else:
        return "severe", "recommend_rollback"
