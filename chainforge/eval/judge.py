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
"""LLM-as-judge evaluation — use an LLM to score agent outputs.

Provides:
  - LLMJudgeEval: single-output scoring (1-10) with criteria
  - PairwiseEval: A/B comparison of two agent variants
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.llm import LLM
from chainforge.core.message import Message
from chainforge.eval.runner import EvalRun, EvalResult
from chainforge.eval.suite import EvalSuite
from chainforge.eval.case import EvalCase
from chainforge.logging import get_logger

logger = get_logger("eval.judge")

SCORE_SYSTEM_PROMPT = """You are an expert evaluator. Score the following AI response on a scale of 1-10.
Consider:
1. Accuracy — factual correctness
2. Completeness — covers all aspects
3. Clarity — well-structured and easy to understand
4. Helpfulness — directly addresses the user's needs

Respond with a JSON object:
{"score": <int 1-10>, "reasoning": "<brief explanation>", "strengths": ["..."], "weaknesses": ["..."]}"""

PAIRWISE_SYSTEM_PROMPT = """You are an expert evaluator comparing two AI responses.
Given the user's request, decide which response is better.

Evaluate on:
1. Accuracy — fewer factual errors
2. Completeness — more thorough coverage
3. Clarity — better structure and readability
4. Usefulness — more actionable and relevant

Respond with JSON:
{"winner": "A"|"B"|"tie", "reasoning": "<explanation>", "scores": {"A": <int>, "B": <int>}}"""


# ── LLMJudgeEval ─────────────────────────────────────────────────────────


@dataclass
class JudgeResult:
    """Result from an LLM judge evaluation."""
    score: float = 0.0
    reasoning: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    raw_response: str = ""


class LLMJudgeEval:
    """Evaluate agent outputs using an LLM-as-judge.

    Usage:
        judge = LLMJudgeEval(judge_llm=judge_llm)
        result = await judge.evaluate("What is AI?", "AI is...")
        print(f"Score: {result.score}")
    """

    def __init__(
        self,
        judge_llm: LLM,
        criteria: str | None = None,
    ):
        self._judge_llm = judge_llm
        self._criteria = criteria

    async def evaluate(self, prompt: str, output: str) -> JudgeResult:
        """Score a single agent output."""
        user_msg = f"User request: {prompt}\n\nAI response: {output}"
        if self._criteria:
            user_msg += f"\n\nAdditional criteria: {self._criteria}"

        try:
            resp = await self._judge_llm.generate([
                Message.system(SCORE_SYSTEM_PROMPT),
                Message.user(user_msg),
            ])
            raw = resp.content or "{}"

            # Try to parse JSON from the response
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            data = json.loads(raw) if raw.strip() else {}
            return JudgeResult(
                score=data.get("score", 0),
                reasoning=data.get("reasoning", ""),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                raw_response=raw,
            )
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Judge parsing failed: {e}, raw: {raw[:200]}")
            return JudgeResult(score=0, reasoning=f"Parse error: {e}", raw_response=raw)

    async def evaluate_suite(
        self,
        agent: Any,
        suite: EvalSuite,
    ) -> EvalResult:
        """Evaluate an agent against a suite using LLM-as-judge."""
        from chainforge.eval.runner import EvalRunner, MetricsCollector

        result = EvalResult(suite_name=suite.name, agent_name="judge_eval")
        collector = MetricsCollector()

        for case in suite:
            run = EvalRun(case_name=case.name)
            try:
                stream = await agent.run(case.prompt, context=case.context)
                collected = await collector.collect(stream)

                # LLM-as-judge scoring
                judge_result = await self.evaluate(case.prompt, collected.raw_output)

                run.output = collected.raw_output
                run.metrics = {
                    "response_time": round(collected.response_time, 3),
                    "judge_score": judge_result.score,
                    "judge_reasoning": judge_result.reasoning,
                    "tool_call_count": collected.tool_call_count,
                }
                run.checks = {"judge_quality": judge_result.score >= 5.0}
                run.passed = run.checks["judge_quality"]

            except Exception as e:
                run.passed = False
                run.error = str(e)

            result.runs.append(run)

        return result


# ── PairwiseEval ─────────────────────────────────────────────────────────


@dataclass
class PairwiseResult:
    """Result from a pairwise comparison."""
    winner: str = "tie"  # "A", "B", or "tie"
    scores: dict[str, float] = field(default_factory=lambda: {"A": 0, "B": 0})
    reasoning: str = ""
    raw_response: str = ""


class PairwiseEval:
    """Compare two agent variants (A/B) on the same test cases.

    Usage:
        judge_llm = OpenAIProvider(model="gpt-4o")
        pairwise = PairwiseEval(judge_llm=judge_llm)

        result = await pairwise.compare(
            prompt="Explain quantum computing",
            output_a="Quantum computing uses qubits...",
            output_b="Quantum computers leverage superposition...",
        )
        print(f"Winner: {result.winner}")
    """

    def __init__(self, judge_llm: LLM):
        self._judge_llm = judge_llm

    async def compare(self, prompt: str, output_a: str, output_b: str) -> PairwiseResult:
        """Compare two outputs head-to-head."""
        user_msg = (
            f"User request: {prompt}\n\n"
            f"Response A:\n{output_a}\n\n"
            f"Response B:\n{output_b}"
        )

        try:
            resp = await self._judge_llm.generate([
                Message.system(PAIRWISE_SYSTEM_PROMPT),
                Message.user(user_msg),
            ])
            raw = resp.content or "{}"

            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            data = json.loads(raw) if raw.strip() else {}
            return PairwiseResult(
                winner=data.get("winner", "tie"),
                scores=data.get("scores", {"A": 0, "B": 0}),
                reasoning=data.get("reasoning", ""),
                raw_response=raw,
            )
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Pairwise parse failed: {e}")
            return PairwiseResult(reasoning=f"Parse error: {e}", raw_response=raw)

    async def compare_agents(
        self,
        agent_a: Any,
        agent_b: Any,
        suite: EvalSuite,
        *,
        name: str = "pairwise_eval",
    ) -> dict[str, Any]:
        """Compare two agents on the same test suite.

        Returns summary with win/loss/tie counts and detailed results.
        """
        from chainforge.eval.runner import MetricsCollector

        results: list[dict[str, Any]] = []
        wins_a = 0
        wins_b = 0
        ties = 0
        collector = MetricsCollector()

        for case in suite:
            try:
                stream_a = await agent_a.run(case.prompt, context=case.context)
                collected_a = await collector.collect(stream_a)

                stream_b = await agent_b.run(case.prompt, context=case.context)
                collected_b = await collector.collect(stream_b)

                comparison = await self.compare(
                    case.prompt,
                    collected_a.raw_output,
                    collected_b.raw_output,
                )

                if comparison.winner == "A":
                    wins_a += 1
                elif comparison.winner == "B":
                    wins_b += 1
                else:
                    ties += 1

                results.append({
                    "case": case.name,
                    "winner": comparison.winner,
                    "scores": comparison.scores,
                    "reasoning": comparison.reasoning,
                })

            except Exception as e:
                logger.error(f"Pairwise case {case.name} failed: {e}")
                results.append({"case": case.name, "error": str(e)})

        return {
            "name": name,
            "total_cases": len(suite),
            "agent_a_wins": wins_a,
            "agent_b_wins": wins_b,
            "ties": ties,
            "win_rate_a": round(wins_a / len(suite), 3) if suite else 0,
            "win_rate_b": round(wins_b / len(suite), 3) if suite else 0,
            "results": results,
        }
