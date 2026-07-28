"""ChainForge Enterprise: Agent Observability 2.0 example.

Usage:
    python examples/enterprise/observe_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.observe import (
    AnomalyDetector, MetricsCollector, AlertRule, AlertChannel,
    RootCauseAnalyzer,
)

async def main():
    print("=== Agent Observability 2.0 ===\n")

    # 1. Metrics Collector -- simulate agent traffic
    metrics = MetricsCollector()
    for i in range(100):
        success = i < 95  # 95% success rate
        metrics.record(
            success=success,
            latency_ms=100 + (50 if not success else 0),
            tokens=500,
            cost=0.002,
            tool_names=["query_db", "send_email"] if i % 5 != 0 else ["query_db"],
        )
    # Inject anomalies
    for i in range(15):
        metrics.record(success=False, latency_ms=5000, tokens=3000, cost=0.05,
            tool_names=["delete_file"])  # New, suspicious tool

    print("1. Metrics Snapshot:")
    s = metrics.stats
    print(f"   Total calls: {s['total_calls']}")
    print(f"   Failure rate: {s['failure_rate']:.1%}")
    print(f"   Avg latency: {s['avg_latency_ms']:.0f}ms")
    print(f"   Tokens/call: {s['tokens_per_call']:.0f}")
    print(f"   Tools seen: {s['tools_seen']}")

    # 2. Anomaly Detector (has its own internal metrics via middleware;
    #    here we show rule configuration and stats)
    detector = AnomalyDetector(baseline_window_hours=24)
    detector.add_rule(AlertRule(
        name="delete_tool_alert",
        condition="new_tool",
        severity="critical",
        message_template="Suspicious tool detected: {last_tool}",
        cooldown_minutes=5,
    ))
    print(f"\n2. Anomaly Detector: built-in rules + 1 custom rule")
    print(f"   Stats: {detector.stats['total_calls']} calls tracked")

    # 3. Root Cause Analysis
    analyzer = RootCauseAnalyzer()

    # Failure rate spike
    report1 = analyzer.analyze({
        "id": "ano-001", "type": "failure_rate_spike",
        "severity": "critical",
        "metrics_snapshot": {"failure_rate": 0.13},
    })
    print(f"\n3. Root Cause Analysis:")
    print(f"   Anomaly: {report1.anomaly_type}")
    print(f"   Root cause: {report1.root_cause}")
    print(f"   Recommendations: {report1.recommendations[:2]}")
    print(f"   Confidence: {report1.confidence:.0%}")

    # New tool detected
    report2 = analyzer.analyze({
        "id": "ano-002", "type": "new_tool_detected",
        "severity": "high",
    })
    print(f"\n   Anomaly: {report2.anomaly_type}")
    print(f"   Root cause: {report2.root_cause}")

    # Token spike
    report3 = analyzer.analyze({
        "id": "ano-003", "type": "token_spike",
        "severity": "medium",
    })
    print(f"\n   Anomaly: {report3.anomaly_type}")
    print(f"   Root cause: {report3.root_cause}")

    # 4. Alert channels
    slack_ch = AlertChannel.slack("https://hooks.slack.com/services/xxx")
    pd_ch = AlertChannel.pagerduty("pd-routing-key-xxx")
    print(f"\n4. Alert Channels:")
    print(f"   Slack webhook: {slack_ch.type}")
    print(f"   PagerDuty: {pd_ch.type}")

if __name__ == "__main__":
    asyncio.run(main())
