from datetime import UTC, datetime
import unittest

from agentops import IdempotencyConflict, RunRequest, analyze_telemetry, configure_tracing, execute, replay_telemetry


class AgentOpsTests(unittest.TestCase):
    def test_tracing_is_safe_without_an_exporter(self):
        configure_tracing()

    def test_golden_signals_are_detected(self):
        now = datetime.now(UTC)
        expected = {
            "failed": {"failed"},
            "slow": {"slow"},
            "stale": {"stale"},
            "over_budget": {"over_budget"},
            "approval_bottleneck": {"stale", "approval_bottleneck"},
            "healthy": set(),
        }
        for scenario, codes in expected.items():
            found = {item.code for item in analyze_telemetry(replay_telemetry(scenario, now), now)}
            self.assertEqual(codes, found, scenario)

    def test_same_idempotency_key_replays_but_rejects_new_input(self):
        key = "unittest-idempotency-0001"
        first = execute(RunRequest(scenario="failed", idempotency_key=key))
        second = execute(RunRequest(scenario="failed", idempotency_key=key))
        self.assertEqual(first.run_id, second.run_id)
        with self.assertRaises(IdempotencyConflict):
            execute(RunRequest(scenario="slow", idempotency_key=key))


if __name__ == "__main__":
    unittest.main()
