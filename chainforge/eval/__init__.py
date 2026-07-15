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
"""ChainForge Evaluation Framework — test, benchmark, and report agent performance."""

from chainforge.eval.case import EvalCase, EvalMetric, ExpectedBehavior
from chainforge.eval.suite import EvalSuite
from chainforge.eval.runner import EvalRunner, EvalResult, EvalRun
from chainforge.eval.metrics import MetricsCollector, builtin_metrics
from chainforge.eval.report import EvalReport, format_report
from chainforge.eval.benchmarks import BFCLRunner, BFCLCase, BFCLResult, bfcl_cases
from chainforge.eval.judge import LLMJudgeEval, PairwiseEval, JudgeResult, PairwiseResult

__all__ = [
    "EvalCase", "EvalMetric", "ExpectedBehavior",
    "EvalSuite",
    "EvalRunner", "EvalResult", "EvalRun",
    "MetricsCollector", "builtin_metrics",
    "EvalReport", "format_report",
    "LLMJudgeEval", "PairwiseEval",
    "JudgeResult", "PairwiseResult",
    "BFCLRunner", "BFCLCase", "BFCLResult", "bfcl_cases",
]
