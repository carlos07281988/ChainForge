"""ChainForge Enterprise: Agent Federation Protocol example.

Usage:
    python examples/enterprise/federation_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.federation import (
    InteropProtocol, InteropRequest, InteropResponse, FederatedAgent, AgentExport,
)

async def main():
    print("=== Agent Federation Protocol ===\n")

    # 1. Interop Protocol — standard wire format
    print("1. Interop Protocol v1:")
    schema = InteropProtocol.request_schema()
    print(f"   Schema: {list(schema['properties'].keys())}")
    print(f"   Required: {schema['required']}")
    frameworks = InteropProtocol.compatible_frameworks()
    print(f"   Compatible: {', '.join(frameworks)}")

    # 2. Build an interop request
    req = InteropRequest(
        messages=[
            {"role": "system", "content": "You are a helpful agent."},
            {"role": "user", "content": "What is the weather in Tokyo?"},
        ],
        tools=[{
            "type": "function",
            "function": {"name": "get_weather", "description": "Get weather for a city",
                        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}},
        }],
        context={"run_id": "run-abc", "parent_agent": "orchestrator"},
    )
    print(f"\n2. Interop Request:")
    print(f"   Messages: {len(req.messages)}")
    print(f"   Tools: {len(req.tools)}")
    print(f"   Context: {req.context}")

    # 3. Interop response
    resp = InteropResponse(
        content="The weather in Tokyo is sunny, 22°C.",
        finish_reason="stop",
        usage={"prompt_tokens": 50, "completion_tokens": 12, "total_tokens": 62},
        model="gpt-4o",
    )
    print(f"\n3. Interop Response:")
    print(f"   Content: {resp.content}")
    print(f"   Tokens: {resp.usage.get('total_tokens')}")
    print(f"   Model: {resp.model}")

    # 4. Import external agent as ChainForge LLM
    external = FederatedAgent(
        endpoint="https://langchain-agent.internal/agent",
        protocol="chainforge-interop-v1",
    )
    print(f"\n4. FederatedAgent (import):")
    print(f"   Endpoint: {external.endpoint}")
    print(f"   Model: {external.model}")
    print(f"   Capabilities: {external.capabilities}")

    # 5. Export ChainForge agent as HTTP endpoint
    print(f"\n5. AgentExport (export):")
    print(f"   Use AgentExport(agent).as_handler() for custom framework integration")
    print(f"   Or AgentExport(agent).serve(port=9100) for standalone HTTP server")
    print(f"   POST http://0.0.0.0:9100/agent")
    print(f"   GET  http://0.0.0.0:9100/health")

if __name__ == "__main__":
    asyncio.run(main())
