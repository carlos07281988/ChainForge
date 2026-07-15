"""example/14_orchestration.py — Swarm and orchestration verification."""
import sys, asyncio
from chainforge.orchestration import Swarm, SwarmMode
from chainforge.core.agent import Agent
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

from chainforge.core.llm import LLM    
from typing import Any
from collections.abc import AsyncIterator

class FakeLLM(LLM):
    model: str = "fake"
    def __init__(self):
        pass
    async def generate(self, messages, tools=None, **kwargs):
        from chainforge.core.llm import LLMResponse
        return LLMResponse(content="test response")
    async def stream_generate(self, messages, tools=None, **kwargs) -> AsyncIterator[str]:
        yield "test"

def test_swarm_creation():
    swarm = Swarm(agents=[], name="test")
    check("sw1: swarm name", swarm.name == "test")
    check("sw2: no agents", len(swarm.agents) == 0)

def test_swarm_with_agents():
    agents = [Agent(llm=FakeLLM()), Agent(llm=FakeLLM())]
    swarm = Swarm(agents=agents)
    check("sw3: 2 agents", len(swarm.agents) == 2)

def test_swarm_default_mode():
    swarm = Swarm(agents=[])
    check("sw4: default sequential", swarm.mode == SwarmMode.sequential)

def test_swarm_modes():
    check("sw5: parallel", SwarmMode.parallel.value == "parallel")
    check("sw6: sequential", SwarmMode.sequential.value == "sequential")
    check("sw7: conference", SwarmMode.conference.value == "conference")

async def test_swarm_async_run():
    agent = Agent(llm=FakeLLM())
    swarm = Swarm(agents=[agent], name="test")
    stream = await swarm.run("hello")
    events = await stream.collect()
    check("sw8: events produced", len(events) > 0)
    has_done = any(e.type.value == "done" for e in events)
    check("sw9: ends with done", has_done)

async def main():
    print("=" * 58)
    print("  Orchestration \u2014 Swarm, SwarmMode, multi-agent")
    print("=" * 58)
    test_swarm_creation(); test_swarm_with_agents()
    test_swarm_default_mode(); test_swarm_modes()
    await test_swarm_async_run()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
