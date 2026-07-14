# Copyright 2024 ChainForge Contributors
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
"""EvalReport — format evaluation results as JSON, Markdown, or HTML."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chainforge.eval.metrics import BUILTIN_METRICS
from chainforge.eval.runner import EvalResult


class EvalReport:
    """Formats evaluation results for human or machine consumption."""

    def __init__(self, result: EvalResult):
        self.result = result

    def to_json(self, path: str | Path | None = None) -> str:
        """Serialize results to JSON."""
        data = {
            "suite": self.result.suite_name,
            "agent": self.result.agent_name,
            "total_time_s": self.result.total_time_s,
            "total_cases": self.result.total_cases,
            "passed": self.result.total_passed,
            "pass_rate": round(self.result.pass_rate * 100, 1),
            "avg_score": round(self.result.avg_score, 3),
            "runs": [
                {
                    "case": r.case_name,
                    "passed": r.passed,
                    "score": round(r.score, 3),
                    "metrics": r.metrics,
                    "checks": r.checks,
                    "error": r.error,
                    "duration_s": r.duration_s,
                    "output_preview": r.output[:200] if r.output else "",
                }
                for r in self.result.runs
            ],
        }
        text = json.dumps(data, indent=2, ensure_ascii=False)
        if path:
            Path(path).write_text(text)
        return text

    def to_markdown(self) -> str:
        """Generate a Markdown report."""
        r = self.result
        lines = [
            f"# Eval Report: {r.suite_name}",
            f"",
            f"**Agent:** {r.agent_name}  ",
            f"**Total time:** {r.total_time_s}s  ",
            f"**Pass rate:** {r.total_passed}/{r.total_cases} ({round(r.pass_rate * 100, 1)}%)  ",
            f"**Avg score:** {round(r.avg_score, 3)}  ",
            f"",
            f"## Results",
            f"",
            f"| Case | Pass | Score | Time (s) | Tool Calls | Iterations | Checks |",
            f"|------|------|-------|----------|------------|------------|--------|",
        ]
        for run in r.runs:
            m = run.metrics
            tc = m.get("tool_call_count", "-")
            it = m.get("iterations", "-")
            dur = run.duration_s
            checks_str = ", ".join(f"{k}={v}" for k, v in run.checks.items()) if run.checks else "-"
            lines.append(
                f"| {run.case_name} | {'✅' if run.passed else '❌'} | {round(run.score, 2)} | {dur} | {tc} | {it} | {checks_str} |"
            )

        lines.extend([
            f"",
            f"## Summary",
            f"",
            f"- **Cases passed:** {r.total_passed}/{r.total_cases}",
            f"- **Pass rate:** {round(r.pass_rate * 100, 1)}%",
            f"- **Average score:** {round(r.avg_score, 3)}",
            f"- **Total duration:** {r.total_time_s}s",
        ])

        return "\n".join(lines)

    def to_html(self) -> str:
        """Generate a standalone HTML report."""
        r = self.result
        rows_html = ""
        for run in r.runs:
            m = run.metrics
            tc = m.get("tool_call_count", "-")
            it = m.get("iterations", "-")
            dur = round(run.duration_s, 3)
            checks_str = ", ".join(f"{k}={v}" for k, v in run.checks.items()) if run.checks else "-"
            status = "pass" if run.passed else "fail"
            rows_html += (
                f"<tr class=\"{status}\">"
                f"<td>{run.case_name}</td>"
                f"<td>{'✅' if run.passed else '❌'}</td>"
                f"<td>{round(run.score, 2)}</td>"
                f"<td>{dur}</td>"
                f"<td>{tc}</td>"
                f"<td>{it}</td>"
                f"<td>{checks_str}</td>"
                f"<td>{run.error or ''}</td>"
                f"</tr>"
            )

        return f'''<!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><title>Eval: {r.suite_name}</title>
    <style>
        body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 1000px; margin: 0 auto; padding: 2rem; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
        .summary {{ display: flex; gap: 2rem; margin: 1rem 0; padding: 1rem; background: #f5f5f5; border-radius: 8px; }}
        .summary-item {{ text-align: center; }}
        .summary-item .value {{ font-size: 1.5rem; font-weight: bold; }}
        .summary-item .label {{ font-size: 0.8rem; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ padding: 0.5rem; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f0f0f0; }}
        .pass {{ background: #f0fff0; }}
        .fail {{ background: #fff0f0; }}
    </style>
    </head>
    <body>
    <h1>Eval Report: {r.suite_name}</h1>
    <p><strong>Agent:</strong> {r.agent_name}</p>
    <div class="summary">
        <div class="summary-item"><div class="value">{r.total_passed}/{r.total_cases}</div><div class="label">Passed</div></div>
        <div class="summary-item"><div class="value">{round(r.pass_rate * 100, 1)}%</div><div class="label">Pass Rate</div></div>
        <div class="summary-item"><div class="value">{r.total_time_s}s</div><div class="label">Duration</div></div>
        <div class="summary-item"><div class="value">{round(r.avg_score, 3)}</div><div class="label">Avg Score</div></div>
    </div>
    <table>
    <thead><tr><th>Case</th><th>Pass</th><th>Score</th><th>Time (s)</th><th>Tool Calls</th><th>Iterations</th><th>Checks</th><th>Error</th></tr></thead>
    <tbody>{rows_html}</tbody>
    </table>
    </body></html>'''

    def to_text(self) -> str:
        """Generate a plain-text summary."""
        r = self.result
        lines = [
            f"Eval Report: {r.suite_name}  (agent: {r.agent_name})",
            f"{'=' * 60}",
            f"Passed: {r.total_passed}/{r.total_cases}  ({round(r.pass_rate * 100, 1)}%)",
            f"Avg Score: {round(r.avg_score, 3)}",
            f"Duration: {r.total_time_s}s",
            f"",
        ]
        for run in r.runs:
            status = "PASS" if run.passed else "FAIL"
            lines.append(f"  [{status}] {run.case_name}  (score={round(run.score, 2)}, duration={run.duration_s}s)")
            if run.error:
                lines.append(f"         Error: {run.error}")
        return "\n".join(lines)


def format_report(result: EvalResult, fmt: str = "text", path: str | None = None) -> str:
    """Convenience function to format eval results."""
    report = EvalReport(result)
    fmt_map = {
        "json": report.to_json,
        "markdown": report.to_markdown,
        "md": report.to_markdown,
        "html": report.to_html,
        "text": report.to_text,
    }
    formatter = fmt_map.get(fmt, report.to_text)
    output = formatter()
    if path:
        Path(path).write_text(output)
    return output
