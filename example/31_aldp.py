"""example/31_aldp.py — ALDP debug protocol verification."""
import sys, asyncio
from chainforge.aldp import ALDPMessageType, encode_event, decode_message
from chainforge.aldp import event_state, event_tool_call, event_tool_result
from chainforge.aldp import event_llm_response, event_paused, event_done, event_error
from chainforge.aldp import ALDPServer
from chainforge.core.agent_aldp import AldpDebugSession
from chainforge.core.agent import Agent
from chainforge.testing import MockLLM, MockResponse
p=0;f2=0
def c(n,o):
    global p,f2
    if o: p+=1; print(f"  \u2705 {n}")
    else: f2+=1; print(f"  \u274c {n}")

# Protocol tests
msg = encode_event("state", {"state": "thinking"})
c("encode bytes", isinstance(msg, bytes))

decoded = decode_message(msg)
c("decode dict", isinstance(decoded, dict))
c("has event", "event" in decoded)
c("has data", "data" in decoded)

c("event_state", b"thinking" in event_state("thinking"))
c("event_tool_call", b"search" in event_tool_call("search", {"q":"t"}))
c("event_tool_result", b"ok" in event_tool_result("s", "ok"))
c("event_llm", b"hi" in event_llm_response("hi"))
c("event_paused", b"paused" in event_paused("tool_call"))
c("event_done", b"done" in event_done("done"))
c("event_error", b"err" in event_error("err"))

# Server tests
s = ALDPServer(host="127.0.0.1", port=0)
c("server created", s._host == "127.0.0.1")
c("not paused", not s.paused)
s._paused = True
c("can pause", s.paused)

# Session tests
agent = Agent(llm=MockLLM(responses=[MockResponse(content="test")]))
session = AldpDebugSession(agent)
c("session created", isinstance(session, AldpDebugSession))

print(f"\n  Results: {p} passed, {f2} failed")
sys.exit(0 if f2==0 else 1)
