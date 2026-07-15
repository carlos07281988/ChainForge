"""example/11_memory_buffer.py — BufferMemory verification."""
import sys, asyncio
from chainforge.memory import BufferMemory
from chainforge.core.message import Message
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

async def test_memory_empty():
    mem = BufferMemory()
    history = await mem.load()
    check("mem1: empty on init", history == [])

async def test_memory_add():
    mem = BufferMemory()
    await mem.save([Message.user("Hello")])
    history = await mem.load()
    check("mem2: one message", len(history) == 1)
    check("mem3: content correct", history[0].content == "Hello")
    check("mem4: role user", history[0].role.value == "user")

async def test_memory_window():
    mem = BufferMemory(max_messages=2)
    await mem.save([Message.user("A"), Message.user("B"), Message.user("C")])
    history = await mem.load()
    check("mem5: window size", len(history) == 2)
    check("mem6: last in window", history[-1].content == "C")

async def test_memory_clear():
    mem = BufferMemory()
    await mem.save([Message.user("Test")])
    mem.clear()
    history = await mem.load()
    check("mem7: after clear", history == [])

async def test_memory_get_history():
    mem = BufferMemory()
    mem.add(Message.user("Hi"))
    mem.add(Message.assistant("Hello!"))
    history = mem.get_history()
    check("mem8: get_history size", len(history) == 2)
    check("mem9: has assistant", history[1].content == "Hello!")

async def test_memory_multiple_saves():
    mem = BufferMemory()
    await mem.save([Message.user("Q1")])
    await mem.save([Message.assistant("A1")])
    await mem.save([Message.user("Q2")])
    history = await mem.load()
    check("mem10: multiple saves", len(history) == 3)

async def test_memory_default_max():
    mem = BufferMemory()
    check("mem11: default max 50", mem.max_messages == 50)

async def main():
    print("=" * 58)
    print("  Memory Buffer \u2014 BufferMemory, save, load, clear")
    print("=" * 58)
    await test_memory_empty(); await test_memory_add()
    await test_memory_window(); await test_memory_clear()
    await test_memory_get_history(); await test_memory_multiple_saves()
    await test_memory_default_max()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
