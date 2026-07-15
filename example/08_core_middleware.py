"""example/08_core_middleware.py — Middleware protocol verification."""
import sys, asyncio
from collections.abc import AsyncIterator
from chainforge.core.middleware import Middleware, MiddlewareChain
from chainforge.core.message import Message
from chainforge.core.stream import StreamEvent, EventType
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

async def test_middleware_creation():
    async def my_mw(messages, ctx, next_handler):
        async for e in next_handler(messages, ctx):
            yield e
    mw = Middleware(my_mw, name="test_mw")
    check("mw1: has name", mw.name == "test_mw")

async def test_middleware_chain():
    """Build a middleware chain and verify it processes events."""
    async def logger_mw(messages, ctx, next_handler):
        ctx["logged"] = True
        async for e in next_handler(messages, ctx):
            yield e

    async def final_handler(messages, ctx):
        yield StreamEvent.text("hello from final")

    chain = MiddlewareChain([logger_mw])
    ctx = {}
    results = []
    async for e in chain.run([Message.user("hi")], ctx, final_handler):
        results.append(e)
    check("chain1: event received", len(results) == 1)
    check("chain2: text event", results[0].type == EventType.text)
    check("chain3: ctx modified", ctx.get("logged") is True)

async def test_middleware_empty_chain():
    chain = MiddlewareChain([])
    async def final(messages, ctx):
        yield StreamEvent.done()
    results = []
    async for e in chain.run([], {}, final):
        results.append(e)
    check("chain4: empty chain passes through", len(results) == 1)

async def test_middleware_transform():
    """Middleware that modifies events."""
    async def transform_mw(messages, ctx, next_handler):
        async for e in next_handler(messages, ctx):
            if e.type == EventType.text and e.content:
                yield StreamEvent.text(e.content.upper())
            else:
                yield e

    async def final(messages, ctx):
        yield StreamEvent.text("hello")

    chain = MiddlewareChain([transform_mw])
    results = []
    async for e in chain.run([], {}, final):
        results.append(e)
    check("chain4: transformed to upper", results[0].content == "HELLO")

async def main():
    print("=" * 58)
    print("  Core Middleware \u2014 Middleware, MiddlewareChain")
    print("=" * 58)
    await test_middleware_creation(); await test_middleware_chain()
    await test_middleware_empty_chain(); await test_middleware_transform()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
