# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""Agent Simulator — regression testing, comparison, and reporting for agents.

Runs synthetic traffic through digital twins and produces structured reports
with pass/fail analysis, cost estimates, and recommendations.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from chainforge.enterprise.simulator.chaos import ChaosConfig, ChaosInjector
from chainforge.enterprise.simulator.digital_twin import DigitalTwin


@dataclass
class SimulationReport:
    """Structured report produced after running a simulation.

    Attributes:
        total_scenarios: Total number of prompts run.
        pass_rate: Fraction of prompts that passed (0.0–1.0).
        regressed_scenarios: List of scenario identifiers that failed.
        cost_estimate: Total estimated cost in USD.
        recommendation: Human-readable recommendation: 'PASS', 'WARN', or 'FAIL'.
        passed_scenarios: Count of passing scenarios.
        failed_scenarios: Count of failing scenarios.
    """

    total_scenarios: int
    pass_rate: float
    regressed_scenarios: list[str]
    cost_estimate: float
    recommendation: str
    passed_scenarios: int
    failed_scenarios: int

    def to_json(self) -> dict:
        """Serialize the report to a JSON-compatible dictionary.

        Returns:
            A dictionary representation of the report.
        """
        return {
            "total_scenarios": self.total_scenarios,
            "pass_rate": self.pass_rate,
            "regressed_scenarios": self.regressed_scenarios,
            "cost_estimate": self.cost_estimate,
            "recommendation": self.recommendation,
            "passed_scenarios": self.passed_scenarios,
            "failed_scenarios": self.failed_scenarios,
        }

    def __repr__(self) -> str:
        return (
            f"SimulationReport(pass_rate={self.pass_rate:.1%}, "
            f"passed={self.passed_scenarios}/{self.total_scenarios}, "
            f"cost=${self.cost_estimate:.2f}, rec={self.recommendation})"
        )


@dataclass
class SimulationDiff:
    """Result of comparing two agents via simulation.

    Attributes:
        winner: The name of the winning agent ('agent_a', 'agent_b', or 'tie').
        differences: A dictionary describing per-metric differences.
        report_a: The SimulationReport for agent A.
        report_b: The SimulationReport for agent B.
    """

    winner: str
    differences: dict
    report_a: SimulationReport
    report_b: SimulationReport

    def to_json(self) -> dict:
        """Serialize the diff to a JSON-compatible dictionary.

        Returns:
            A dictionary representation of the comparison.
        """
        return {
            "winner": self.winner,
            "differences": self.differences,
            "report_a": self.report_a.to_json(),
            "report_b": self.report_b.to_json(),
        }

    def __repr__(self) -> str:
        return f"SimulationDiff(winner={self.winner}, diffs={len(self.differences)} metrics)"


@dataclass
class AgentSimulator:
    """Orchestrates agent simulation runs.

    Runs synthetic traffic prompts through a digital twin (optionally with
    chaos injection) and produces structured reports.

    Attributes:
        agent: The agent instance to simulate.
        traffic: List of prompt strings to run.
        chaos: Optional chaos configuration for failure injection.
        max_concurrent: Maximum concurrent prompt executions.
    """

    agent: Any
    traffic: list[str]
    chaos: ChaosConfig | None = None
    max_concurrent: int = 10

    async def run(self) -> SimulationReport:
        """Run the full simulation against the configured agent.

        Returns:
            A SimulationReport with pass/fail analysis and cost estimate.
        """
        twin = DigitalTwin(self.agent, sandbox=True)
        chaos_injector = ChaosInjector(self.chaos) if self.chaos else None

        results = await twin.batch_run(self.traffic, max_concurrent=self.max_concurrent)

        passed: list[str] = []
        failed: list[str] = []
        total_cost = 0.0

        for i, result in enumerate(results):
            scenario_id = f"s{i}"

            # Apply chaos if configured.
            if chaos_injector and chaos_injector.apply("any"):
                # Replace output with chaos-injected error.
                result["output"] = chaos_injector.simulate_model_error()
                result["status"] = "chaos_error"
                await chaos_injector.inject_latency()

            if _is_pass(result):
                passed.append(scenario_id)
            else:
                failed.append(scenario_id)

            total_cost += result.get("cost_estimate", 0.0)

        total = len(results)
        pass_rate = len(passed) / max(total, 1)
        recommendation = _compute_recommendation(pass_rate, len(failed))

        return SimulationReport(
            total_scenarios=total,
            pass_rate=round(pass_rate, 4),
            regressed_scenarios=failed,
            cost_estimate=round(total_cost, 4),
            recommendation=recommendation,
            passed_scenarios=len(passed),
            failed_scenarios=len(failed),
        )

    @staticmethod
    async def compare(agent_a: Any, agent_b: Any) -> SimulationDiff:
        """Compare two agents by running them through the same simulation.

        Requires the agents to have a ``traffic`` attribute or the simulator
        must have been configured before calling compare.

        Args:
            agent_a: First agent to compare.
            agent_b: Second agent to compare.

        Returns:
            A SimulationDiff with winner determination and per-metric differences.
        """
        # Run both agents with minimal default traffic if not configured.
        default_traffic = ["hello", "help me", "what is 2+2?", "tell me a joke"]

        sim_a = AgentSimulator(agent=agent_a, traffic=default_traffic)
        sim_b = AgentSimulator(agent=agent_b, traffic=default_traffic)

        report_a, report_b = await asyncio.gather(sim_a.run(), sim_b.run())

        differences: dict = {
            "pass_rate_delta": round(report_b.pass_rate - report_a.pass_rate, 4),
            "cost_delta": round(report_b.cost_estimate - report_a.cost_estimate, 4),
            "passed_delta": report_b.passed_scenarios - report_a.passed_scenarios,
            "failed_delta": report_b.failed_scenarios - report_a.failed_scenarios,
        }

        # Determine winner.
        if report_a.pass_rate > report_b.pass_rate:
            winner = "agent_a"
        elif report_b.pass_rate > report_a.pass_rate:
            winner = "agent_b"
        else:
            # Tie on pass_rate; compare cost (lower is better).
            if report_a.cost_estimate < report_b.cost_estimate:
                winner = "agent_a"
            elif report_b.cost_estimate < report_a.cost_estimate:
                winner = "agent_b"
            else:
                winner = "tie"

        return SimulationDiff(
            winner=winner,
            differences=differences,
            report_a=report_a,
            report_b=report_b,
        )

    def __repr__(self) -> str:
        return (
            f"AgentSimulator(scenarios={len(self.traffic)}, "
            f"chaos={bool(self.chaos)}, concurrent={self.max_concurrent})"
        )


def _is_pass(result: dict) -> bool:
    """Determine whether a single simulation result counts as a pass.

    Criteria:
        - Status is 'ok' (no error raised).
        - Output is non-empty.
        - Output string length > 5 characters.

    Args:
        result: A result dictionary from DigitalTwin.run().

    Returns:
        True if the result passes all criteria.
    """
    if result.get("status") != "ok":
        return False

    output = result.get("output")
    if output is None:
        return False

    output_str = str(output).strip()
    if len(output_str) <= 5:
        return False

    return True


def _compute_recommendation(pass_rate: float, failed_count: int) -> str:
    """Compute a human-readable recommendation based on simulation results.

    Args:
        pass_rate: Fraction of prompts that passed.
        failed_count: Absolute number of failures.

    Returns:
        One of 'PASS', 'WARN', or 'FAIL'.
    """
    if pass_rate >= 0.95:
        return "PASS"
    elif pass_rate >= 0.80:
        return "WARN"
    else:
        return "FAIL"
