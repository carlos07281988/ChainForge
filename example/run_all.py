"""Run all verification examples."""
import sys, subprocess, os
D = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(os.path.dirname(D), ".venv", "bin", "python3")
EX = [f"{i:02d}_{name}.py" for i, name in [(1, 'core_tool'), (2, 'core_message'), (3, 'core_stream'), (4, 'core_pipeline'), (5, 'core_dag'), (6, 'core_state'), (7, 'core_structured_output'), (8, 'core_middleware'), (9, 'testing_mock'), (10, 'parsers'), (11, 'memory_buffer'), (12, 'reasoning'), (13, 'guardrails'), (14, 'orchestration_swarm'), (15, 'tracing'), (16, 'time_travel'), (17, 'consensus'), (18, 'self_evolving'), (19, 'tool_synthesis'), (20, 'liquid_memory'), (21, 'guardrail_injection'), (22, 'provenance_graph'), (23, 'workflow_dsl'), (24, 'multimodal'), (25, 'dream_mode'), (26, 'tech_tree'), (27, 'population'), (28, 'behavior_test'), (29, 'budget'), (30, 'deploy')]]
tp=0;tf=0;fl=[]
for ex in EX:
    path=os.path.join(D,ex)
    print(f"\n  >>> {ex}...")
    r=subprocess.run([PY,"-u",path],capture_output=True,text=True,timeout=30,cwd=D)
    print(r.stdout)
    if r.stderr: print(f"  STDERR:\n{r.stderr}")
    if r.returncode!=0: fl.append(ex)
    for line in r.stdout.split("\n"):
        line=line.strip()
        if line.startswith("Results:"):
            parts=line.replace("Results: ","").split(", ")
            for p in parts:
                try:
                    v=int(p.split()[0])
                    if "passed" in p: tp+=v
                    if "failed" in p: tf+=v
                except: pass
print("="*58)
print(f"  Total: {tp} passed, {tf} failed")
if fl: print(f"  Failed: {', '.join(fl)}")
else: print("  All passed!")
sys.exit(0 if tf==0 else 1)
