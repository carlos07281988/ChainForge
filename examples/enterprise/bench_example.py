"""ChainForge Enterprise: Agent Benchmarking as Code example.

Usage:
    python examples/enterprise/bench_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.bench import (
    BenchmarkSuite, BenchmarkScenario, BenchmarkExpectation,
    BenchmarkRunner, BenchmarkResult, RegressionDetector,
)

async def main():
    print("=== Agent Benchmarking as Code ===\n")

    # 1. Define benchmark suite programmatically
    suite = BenchmarkSuite(
        name="customer-support-suite",
        version="1.0",
        description="Core customer support scenarios",
        scenarios=[
            BenchmarkScenario(
                name="refund_request", description="User requests a refund",
                input="I want a refund for order #12345",
                expect=BenchmarkExpectation(
                    tool_calls_include=["query_db"],
                    output_contains=["refund"],
                    max_latency_ms=5000,
                    max_cost=0.10,
                ),
                tags=["critical", "revenue"],
                weight=1.5,
            ),
            BenchmarkScenario(
                name="order_inquiry", description="User checks order status",
                input="Where is my order #99999?",
                expect=BenchmarkExpectation(
                    tool_calls_include=["query_db"],
                    output_not_contains=["refund"],
                    max_latency_ms=3000,
                ),
                tags=["common"],
            ),
            BenchmarkScenario(
                name="general_question", description="Simple FAQ",
                input="What are your business hours?",
                expect=BenchmarkExpectation(
                    output_contains=["hours", "open"],
                    max_latency_ms=2000,
                    max_cost=0.02,
                ),
                tags=["common"],
            ),
        ],
    )
    print(f"1. Benchmark Suite: {suite.name} v{suite.version}")
    for s in suite.scenarios:
        print(f"   • {s.name} [{', '.join(s.tags)}] (weight={s.weight})")

    # 2. Run benchmark (simulated results since no real agent)
    print(f"\n2. Benchmark Run (v1 — gpt-4o agent):")
    v1_results = [
        BenchmarkResult(scenario="refund_request", passed=True, latency_ms=850, cost=0.035,
            tool_calls_made=["query_db", "refund_tool"],
            output="I've processed your refund for order #12345. You'll receive $150 within 3-5 business days.",
            checks_passed=["tool_called:query_db", "output_contains:refund", "latency_ok", "cost_ok"],
            checks_failed=[]),
        BenchmarkResult(scenario="order_inquiry", passed=True, latency_ms=620, cost=0.02,
            tool_calls_made=["query_db"],
            output="Order #99999 was shipped on July 20th and is in transit.",
            checks_passed=["tool_called:query_db", "output_excludes:refund", "latency_ok"],
            checks_failed=[]),
        BenchmarkResult(scenario="general_question", passed=True, latency_ms=300, cost=0.005,
            tool_calls_made=[],
            output="Our business hours are Monday-Friday, 9am-6pm EST.",
            checks_passed=["output_contains:hours", "latency_ok", "cost_ok"],
            checks_failed=[]),
    ]
    for r in v1_results:
        print(f"   {'✅' if r.passed else '❌'} {r.scenario}: {r.latency_ms:.0f}ms, ${r.cost:.4f}")

    # 3. v2 results (after agent upgrade)
    print(f"\n3. Benchmark Run (v2 — upgraded agent):")
    v2_results = [
        BenchmarkResult(scenario="refund_request", passed=False, latency_ms=1200, cost=0.08,
            tool_calls_made=["query_db"],
            output="I'll help you with that.",
            checks_passed=["tool_called:query_db", "latency_ok"],
            checks_failed=["output_missing:refund"]),
        BenchmarkResult(scenario="order_inquiry", passed=True, latency_ms=400, cost=0.01,
            tool_calls_made=["query_db"],
            output="Order #99999 was shipped. Expected delivery: July 28, 2026.",
            checks_passed=["tool_called:query_db", "output_excludes:refund", "latency_ok"],
            checks_failed=[]),
        BenchmarkResult(scenario="general_question", passed=True, latency_ms=250, cost=0.004,
            tool_calls_made=[],
            output="We are open Mon-Fri, 9am-6pm EST.",
            checks_passed=["output_contains:hours", "latency_ok", "cost_ok"],
            checks_failed=[]),
    ]
    for r in v2_results:
        print(f"   {'✅' if r.passed else '❌'} {r.scenario}: {r.latency_ms:.0f}ms, ${r.cost:.4f}")

    # 4. Regression detection
    detector = RegressionDetector(baseline=v1_results)
    report = detector.check(v2_results)
    print(f"\n4. Regression Report:")
    print(f"   {report.summary}")
    if report.regressed_scenarios:
        print(f"\n   ⚠️  BLOCK DEPLOYMENT — regressed: {report.regressed_scenarios}")
    if report.improved_scenarios:
        print(f"   📈 Improved: {report.improved_scenarios}")

if __name__ == "__main__":
    asyncio.run(main())
