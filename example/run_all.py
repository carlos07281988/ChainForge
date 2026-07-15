"""example/run_all.py — Run all verification examples."""
import sys, subprocess, os

EXAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(os.path.dirname(EXAMPLES_DIR), ".venv", "bin", "python3")

examples = [
    "01_core_tool.py", "02_core_message.py", "03_core_stream.py",
    "04_core_pipeline.py", "05_core_dag.py", "06_core_state.py",
    "07_core_structured_output.py", "08_core_middleware.py",
    "09_testing_mock.py", "10_parsers.py", "11_memory_buffer.py",
    "12_reasoning.py", "13_guardrails.py", "14_orchestration_swarm.py",
    "15_tracing.py",
    "16_time_travel.py", "17_consensus.py", "18_self_evolving.py",
]

total_passed = 0
total_failed = 0
failures = []

for ex in examples:
    path = os.path.join(EXAMPLES_DIR, ex)
    print(f"\n  >>> Running {ex}...")
    result = subprocess.run(
        [VENV_PYTHON, "-u", path],
        capture_output=True, text=True, timeout=30,
        cwd=EXAMPLES_DIR,
    )
    print(result.stdout)
    if result.stderr:
        print(f"  STDERR:\n{result.stderr}")
    if result.returncode != 0:
        failures.append(ex)
    for line in result.stdout.split('\n'):
        line = line.strip()
        if line.startswith('Results:'):
            parts = line.replace('Results: ', '').split(', ')
            for p in parts:
                try:
                    val = int(p.split()[0])
                    if 'passed' in p: total_passed += val
                    if 'failed' in p: total_failed += val
                except ValueError:
                    pass

print("=" * 58)
print("  OVERALL RESULTS")
print("=" * 58)
print(f"  Total tests: {total_passed} passed, {total_failed} failed")
if failures:
    print(f"  Failed scripts: {', '.join(failures)}")
else:
    print("  All examples passed! \u2705")
sys.exit(0 if total_failed == 0 else 1)
