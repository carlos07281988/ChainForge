"""example/09_testing_mock.py — MockLLM for testing verification."""
import sys, asyncio
from chainforge.testing import MockLLM, MockResponse, mock_text_response, mock_tool_call_response, mock_agent
from chainforge.core.message import Message, Role
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

async def test_mock_response_defaults():
    r = MockResponse()
    check("mr1: default content empty", r.content == "")
    check("mr2: default tool_calls empty", r.tool_calls == [])
    check("mr3: finish_reason stop", r.finish_reason == "stop")

async def test_mock_text_response():
    r = mock_text_response("Hello!")
    check("mr4: text content", r.content == "Hello!")
    check("mr5: finish_reason stop", r.finish_reason == "stop")

async def test_mock_tool_call():
    r = mock_tool_call_response("calculate", {"x": 1})
    check("mr6: tool_call name", r.tool_calls[0]["name"] == "calculate")
    check("mr7: tool_call args", r.tool_calls[0]["args"] == {"x": 1})
    check("mr8: finish_reason tool_calls", r.finish_reason == "tool_calls")

async def test_mock_llm_generate():
    llm = MockLLM(responses=[MockResponse(content="Hello!")])
    response = await llm.generate([Message(role=Role.user, content="Hi")])
    check("ml1: response content", response.content == "Hello!")
    check("ml2: finish_reason", response.finish_reason == "stop")

async def test_mock_llm_tool_call():
    llm = MockLLM(responses=[
        MockResponse(content="", tool_calls=[{"name": "calc", "args": {"x": 1}}], finish_reason="tool_calls"),
    ])
    response = await llm.generate([Message.user("Calc")])
    check("ml3: empty content", response.content == "")
    check("ml4: has tool_calls", len(response.tool_calls) == 1)
    check("ml5: tool name", response.tool_calls[0]["function"]["name"] == "calc")

async def test_mock_llm_cycle():
    llm = MockLLM(responses=[
        MockResponse(content="First"),
        MockResponse(content="Second"),
    ])
    r1 = await llm.generate([])
    r2 = await llm.generate([])
    check("ml6: first response", r1.content == "First")
    check("ml7: second response", r2.content == "Second")

async def test_mock_llm_reuse():
    llm = MockLLM(responses=[MockResponse(content="Only")])
    await llm.generate([])
    r = await llm.generate([])
    check("ml8: reuses last when exhausted", r.content == "Only")

async def test_mock_agent():
    from chainforge.core.agent import Agent
    result = mock_agent(responses=[MockResponse(content="Test")])
    check("ma1: mock_agent returns tuple", isinstance(result, tuple))
    check("ma2: has agent", len(result) > 0)

async def test_model_property():
    llm = MockLLM()
    check("ml9: model name", llm.model == "mock-llm")
    await llm.generate([])
    check("ml10: call count", llm.total_calls == 1)

async def main():
    print("=" * 58)
    print("  Testing Mock \u2014 MockLLM, MockResponse, mock_agent")
    print("=" * 58)
    await test_mock_response_defaults(); await test_mock_text_response()
    await test_mock_tool_call(); await test_mock_llm_generate()
    await test_mock_llm_tool_call(); await test_mock_llm_cycle()
    await test_mock_llm_reuse(); await test_mock_agent()
    await test_model_property()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
