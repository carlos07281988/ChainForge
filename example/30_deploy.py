"""example/30_deploy.py — Agent-as-Microservice verification."""
import sys
from chainforge.deploy import service, get_registry
from chainforge.core.agent import Agent
from chainforge.testing import MockLLM, MockResponse
p=0;f2=0
def c(n,o):
    global p,f2
    if o: p+=1; print(f"  \u2705 {n}")
    else: f2+=1; print(f"  \u274c {n}")

@service(port=8083, path="/api/agent")
def my_agent():
    return Agent(llm=MockLLM(responses=[MockResponse(content="test")]))

reg = get_registry()
c("registered", "my_agent" in reg)
c("port set", reg["my_agent"]["port"] == 8083)
c("path set", reg["my_agent"]["path"] == "/api/agent")
c("doc stored", isinstance(reg["my_agent"].get("doc", ""), str))

@service()
def default_agent():
    return Agent(llm=MockLLM())
reg2 = get_registry()
c("default name", "default_agent" in reg2)
c("default port", reg2["default_agent"]["port"] == 8080)

print(f"\n  Results: {p} passed, {f2} failed")
sys.exit(0 if f2==0 else 1)
