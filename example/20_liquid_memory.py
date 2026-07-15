"""example/20_liquid_memory.py — LiquidMemory verification."""
import sys, asyncio, time
from chainforge.memory.liquid import LiquidMemory, LiquidItem
passed=0;failed=0
def c(n,o):
    global passed,failed
    if o: passed+=1; print(f"  \u2705 {n}")
    else: failed+=1; print(f"  \u274c {n}")

li = LiquidItem(content="test", weight=1.0, tags=["demo"])
c("item created", li.content == "test")
c("weight 1.0", li.weight == 1.0)
old = li.weight
li.decay(0.1, time.time() + 10)
c("decay works", li.weight < old)
li.boost(2.0)
c("boost works", li.weight > 0.01)
c("access tracked", li.access_count > 0)

mem = LiquidMemory(decay_rate=0.05, frequency_boost=2.0)
c("mem config", mem.decay_rate == 0.05)

async def t():
    await mem.add("Python is a language", tags=["lang"])
    await mem.add("Dark mode preferred", tags=["preference"])
    ctx = await mem.get_context(top_k=10)
    c("context has items", len(ctx) >= 2)
    q = await mem.query("Python", top_k=5)
    c("query finds Python", any("Python" in r["content"] for r in q))
    st = await mem.stats()
    c("stats total_items", st["total_items"] >= 2)
    tg = await mem.get_by_tags(["preference"])
    c("tag query", len(tg) >= 1)
    await mem.clear()
    c("clear empties", len(await mem.get_context()) == 0)
asyncio.run(t())

print(f"\n  Results: {passed} passed, {failed} failed")
sys.exit(0 if failed==0 else 1)
