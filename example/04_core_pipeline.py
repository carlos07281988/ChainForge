"""example/04_core_pipeline.py — Pipeline composition verification."""
import sys, asyncio
from chainforge.core.pipeline import Pipeline
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

async def test_pipeline_run():
    pipe = Pipeline(name="test", steps=[
        lambda x: x.upper(),
        lambda x: f"[{x}]",
    ])
    result = await pipe.run("hello")
    check("p1: run transforms", result == "[HELLO]")
    check("p2: name correct", pipe.name == "test")

async def test_pipeline_identity():
    pipe = Pipeline(name="id", steps=[lambda x: x])
    check("p3: identity returns input", await pipe.run(42) == 42)

async def test_pipeline_composition():
    add_one = Pipeline(name="add", steps=[lambda x: x + 1])
    double = Pipeline(name="double", steps=[lambda x: x * 2])
    combined = add_one >> double
    check("p4: composed >>", combined.name == "add >> double")
    check("p5: composition result", await combined.run(5) == 12)

async def test_pipeline_sync():
    pipe = Pipeline(name="test", steps=[lambda x: x * 2])
    result = await pipe.run(21)
    check("p6: sync call (via run)", result == 42)

async def test_pipeline_stream():
    pipe = Pipeline(name="test", steps=[lambda x: x.upper()])
    stream = pipe.stream("hello")
    events = await stream.collect()
    check("p7: stream has events", len(events) >= 2)
    check("p8: stream ends with done", events[-1].type.value == "done")

async def test_pipeline_empty_steps():
    pipe = Pipeline(name="empty")
    check("p9: empty pipeline returns input", await pipe.run(42) == 42)

async def main():
    print("=" * 58)
    print("  Core Pipeline \u2014 composition, stream, >> operator")
    print("=" * 58)
    await test_pipeline_run(); await test_pipeline_identity()
    await test_pipeline_composition(); await test_pipeline_sync()
    await test_pipeline_stream(); await test_pipeline_empty_steps()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
