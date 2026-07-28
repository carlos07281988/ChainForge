# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""RegressionDetector — detect performance regressions between benchmark runs."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from chainforge.enterprise.bench.runner import BenchmarkResult


class RegressionReport(BaseModel):
    """Reports which scenarios regressed vs improved between two benchmark runs."""

    regressed_scenarios: list[str] = Field(default_factory=list)
    improved_scenarios: list[str] = Field(default_factory=list)
    unchanged_scenarios: list[str] = Field(default_factory=list)
    new_failures: list[str] = Field(default_factory=list)
    new_successes: list[str] = Field(default_factory=list)
    summary: str = ""

    def to_json(self) -> dict:
        """Serialize to plain dict."""
        return self.model_dump()


class RegressionDetector:
    """Detect performance regressions between benchmark runs.

    Usage:
        detector = RegressionDetector(baseline=baseline_results)
        report = detector.check(candidate_results)
        if report.regressed_scenarios:
            print("REGRESSION DETECTED — do not deploy!")
    """

    def __init__(self, baseline: str | list[BenchmarkResult] | None = None) -> None:
        self._baseline: dict[str, BenchmarkResult] = {}
        if isinstance(baseline, str):
            data = json.loads(Path(baseline).read_text())
            self._baseline = {r["scenario"]: BenchmarkResult(**r) for r in data}
        elif isinstance(baseline, list):
            self._baseline = {r.scenario: r for r in baseline}

    def set_baseline(self, results: list[BenchmarkResult]) -> None:
        """Set the baseline results for regression comparison."""
        self._baseline = {r.scenario: r for r in results}

    def check(self, candidate: str | list[BenchmarkResult]) -> RegressionReport:
        """Compare candidate results against baseline and produce a regression report."""
        if isinstance(candidate, str):
            data = json.loads(Path(candidate).read_text())
            candidates = [BenchmarkResult(**r) for r in data]
        else:
            candidates = candidate if isinstance(candidate, list) else []

        regressed: list[str] = []
        improved: list[str] = []
        unchanged: list[str] = []
        new_fail: list[str] = []
        new_pass: list[str] = []

        for cr in candidates:
            bl = self._baseline.get(cr.scenario)
            if bl is None:
                continue
            if cr.passed and not bl.passed:
                new_pass.append(cr.scenario)
                improved.append(cr.scenario)
            elif not cr.passed and bl.passed:
                new_fail.append(cr.scenario)
                regressed.append(cr.scenario)
            elif cr.passed and bl.passed:
                score_cr = len(cr.checks_passed)
                score_bl = len(bl.checks_passed)
                if score_cr > score_bl:
                    improved.append(cr.scenario)
                elif score_cr < score_bl:
                    regressed.append(cr.scenario)
                else:
                    unchanged.append(cr.scenario)
            else:
                unchanged.append(cr.scenario)

        summary = (
            f"{len(regressed)} regressed, {len(improved)} improved, "
            f"{len(unchanged)} unchanged"
        )
        if regressed:
            summary += f" — BLOCK deployment: {regressed}"
        return RegressionReport(
            regressed_scenarios=regressed,
            improved_scenarios=improved,
            unchanged_scenarios=unchanged,
            new_failures=new_fail,
            new_successes=new_pass,
            summary=summary,
        )
