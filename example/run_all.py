"""example/run_all.py — Run all verification examples."""
import sys, subprocess, os
D = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(os.path.dirname(D), ".venv", "bin", "python3")
EX = [
    "01_core_tool.py","02_core_message.py","03_core_stream.py",
    "04_core_pipeline.py","05_core_dag.py","06_core_state.py",
    "07_core_structured_output.py","08_core_middleware.py",
    "09_testing_mock.py","10_parsers.py","11_memory_buffer.py",
    "12_reasoning.py","13_guardrails.py","14_orchestration_swarm.py",
    "15_tracing.py",
    "16_time_travel.py","17_consensus.py","18_self_evolving.py",
    "19_tool_synthesis.py","20_liquid_memory.py","21_guardrail_injection.py",
]
tp=0;tf=0;failures=[]
for ex in EX:
    path=os.path.join(D,ex)
    print(f"\\n  >>> Running {ex}...")
    r=subprocess.run([PY,"-u",path],capture_output=True,text=True,timeout=30,cwd=D)
    print(r.stdout)
    if r.stderr: print(f"  STDERR:\\n{r.stderr}")
    if r.returncode!=0: failures.append(ex)
    for line in r.stdout.split('\\n'):
        line=line.strip()
        if line.startswith('Results:'):
            parts=line.replace('Results: ','').split(', ')
            for p in parts:
                try:
                    v=int(p.split()[0])
                    if 'passed' in p: tp+=v
                    if 'failed' in p: tf+=v
                except: pass
print("="*58)
print("  OVERALL RESULTS")
print("="*58)
print(f"  Total: {tp} passed, {tf} failed")
if failures: print(f"  Failed: {', '.join(failures)}")
else: print("  All passed! \u2705")
sys.exit(0 if tf==0 else 1)
