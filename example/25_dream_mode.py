"""example/25_dream_mode.py — Dream Mode verification."""
import sys, asyncio
from chainforge.evolution.dream import DreamConfig, DreamMode, DreamPrediction
p=0;f2=0
def c(n,o):
    global p,f2
    if o: p+=1; print(f"  \u2705 {n}")
    else: f2+=1; print(f"  \u274c {n}")

m = DreamConfig(mode=DreamMode.light)
c("mode light", m.mode == DreamMode.light)
m.record_prediction("s", {}, "a"); m.record_actual("s", {}, "a")
c("exact match", m.predictions[-1].was_accurate == True)
m.record_prediction("s", {}, "x"); m.record_actual("s", {}, "y")
c("mismatch", m.predictions[-1].was_accurate == False)
c("accuracy", m.accuracy() > 0)
c("light pattern", len(m.low_confidence_patterns()) <= 1)
s = m.summary()
c("summary mode", s["mode"] == "light")
pred = DreamPrediction(tool_name="t", predicted_result="r")
c("prediction model", pred.tool_name == "t")
print(f"\n  Results: {p} passed, {f2} failed")
sys.exit(0 if f2==0 else 1)
