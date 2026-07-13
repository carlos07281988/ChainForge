"""Tests for the evaluation framework."""

from __future__ import annotations

import sys
sys.path.insert(0, ".")

from chainforge.eval.case import EvalCase, EvalMetric, ExpectedBehavior, sample_cases
from chainforge.eval.suite import EvalSuite
from chainforge.eval.metrics import MetricsCollector, BUILTIN_METRICS
from chainforge.eval.runner import EvalRunner, EvalResult, EvalRun, _check_output_contains, _check_tool_called, _check_no_errors
from chainforge.eval.report import EvalReport, format_report


def test_eval_case_creation():
    c = EvalCase(name="test1", prompt="Hello", expected=[ExpectedBehavior.contains], expected_contains=["Hello"])
    assert c.name == "test1"
    assert c.prompt == "Hello"
    assert ExpectedBehavior.contains in c.expected
    assert "Hello" in c.expected_contains
    assert c.weight == 1.0


def test_sample_cases():
    cases = sample_cases()
    assert len(cases) == 3
    names = [c.name for c in cases]
    assert "simple_greeting" in names
    assert "tool_usage" in names
    assert "no_errors" in names


def test_eval_suite():
    cases = sample_cases()
    suite = EvalSuite(name="test", cases=cases)
    assert suite.name == "test"
    assert len(suite) == 3
    assert suite.total_weight == 3.0


def test_suite_json_roundtrip():
    cases = sample_cases()
    suite = EvalSuite(name="test", cases=cases)
    json_str = suite.to_json()
    restored = EvalSuite.from_json_str(json_str)
    assert restored.name == "test"
    assert len(restored) == 3
    assert restored.cases[0].name == cases[0].name


def test_suite_filter():
    cases = sample_cases()
    suite = EvalSuite(name="test", cases=cases)
    filtered = suite.filter(tags=["tools"])
    assert len(filtered) == 1
    assert filtered[0].name == "tool_usage"


def test_metrics_collector():
    # Create a mock stream
    from chainforge.core.stream import StreamEvent, Stream
    import asyncio

    async def mock_stream():
        yield StreamEvent.text("Hello world")
        yield StreamEvent.tool_call("get_weather", {"city": "Beijing"})
        yield StreamEvent.tool_result("get_weather", "Sunny")
        yield StreamEvent.done("Hello world")

    collector = MetricsCollector()
    import asyncio
    metrics = asyncio.run(collector.collect(Stream(mock_stream())))

    assert metrics.tool_call_count == 1
    assert metrics.response_length == 11  # "Hello world"
    assert metrics.success is True
    assert metrics.raw_output == "Hello world"


def test_checks():
    output = "Hello, world!"
    events = [
        {"type": "tool_call", "data": {"name": "get_weather"}},
        {"type": "text", "content": "Hello, world!"},
    ]

    assert _check_output_contains(output, ["Hello"]) is True
    assert _check_output_contains(output, ["Goodbye"]) is False
    assert _check_tool_called(events, "get_weather") is True
    assert _check_tool_called(events, "search") is False
    assert _check_no_errors(events) is True

    events_with_error = [{"type": "error", "content": "Something went wrong"}]
    assert _check_no_errors(events_with_error) is False


def test_report_text():
    runs = [
        EvalRun(case_name="test1", passed=True, checks={"contains": True}, metrics={"response_time": 1.0}),
        EvalRun(case_name="test2", passed=False, checks={"contains": False}, metrics={"response_time": 0.5}),
    ]
    result = EvalResult(suite_name="test_suite", agent_name="TestAgent", runs=runs, total_time_s=1.5)
    report = format_report(result, fmt="text")
    assert "test_suite" in report
    assert "TestAgent" in report
    assert "test1" in report
    assert "test2" in report


def test_report_json():
    runs = [EvalRun(case_name="test1", passed=True)]
    result = EvalResult(suite_name="test_suite", agent_name="TestAgent", runs=runs)
    report = format_report(result, fmt="json")
    assert '"passed": true' in report
    assert '"test1"' in report
    import json
    data = json.loads(report)
    assert data["total_cases"] == 1
    assert data["pass_rate"] == 100.0


def test_report_html():
    runs = [EvalRun(case_name="test1", passed=True)]
    result = EvalResult(suite_name="test_suite", agent_name="TestAgent", runs=runs)
    report = format_report(result, fmt="html")
    assert "Eval Report" in report
    assert "test_suite" in report
    assert "TestAgent" in report
    assert "pass" in report


if __name__ == "__main__":
    test_eval_case_creation()
    print("✅ test_eval_case_creation")
    test_sample_cases()
    print("✅ test_sample_cases")
    test_eval_suite()
    print("✅ test_eval_suite")
    test_suite_json_roundtrip()
    print("✅ test_suite_json_roundtrip")
    test_suite_filter()
    print("✅ test_suite_filter")
    test_checks()
    print("✅ test_checks")
    test_metrics_collector()
    print("✅ test_metrics_collector")
    test_report_text()
    print("✅ test_report_text")
    test_report_json()
    print("✅ test_report_json")
    test_report_html()
    print("✅ test_report_html")
    print(f"\n✅ All {sum(1 for _ in range(11))} tests passed!")
