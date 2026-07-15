"""Agent-as-Microservice — one-line agent deployment.

Usage:
    from chainforge.deploy import service, serve

    @service(port=8080)
    def my_agent():
        from chainforge import Agent
        from chainforge.providers import OpenAIProvider
        return Agent(llm=OpenAIProvider(model="gpt-4o"))

    # Start server
    serve()  # or: python -m chainforge.deploy
"""

from __future__ import annotations

import inspect
import os
import sys
from typing import Any, Callable

_registry: dict[str, dict[str, Any]] = {}


def service(
    port: int = 8080,
    path: str = "/agent",
    name: str | None = None,
    host: str = "0.0.0.0",
    api_key: str | None = None,
):
    """Decorator that registers an agent factory as a microservice endpoint.

    Usage:
        @service(port=8080, path="/analyze")
        def my_agent():
            return Agent(llm=llm, tools=[search])

    The decorated function is called to create the agent, then served via FastAPI.
    """
    def decorator(fn: Callable) -> Callable:
        agent_name = name or fn.__name__
        _registry[agent_name] = {
            "fn": fn,
            "port": port,
            "path": path,
            "host": host,
            "api_key": api_key,
            "doc": fn.__doc__ or "",
        }
        return fn
    return decorator


def get_registry() -> dict[str, dict[str, Any]]:
    """Return the agent registry. Keys are agent names, values are config dicts."""
    return dict(_registry)


async def _build_agent(name: str) -> Any:
    """Build an agent from the registry by calling its factory function."""
    entry = _registry.get(name)
    if entry is None:
        raise ValueError(f"Unknown agent: {name}")
    result = entry["fn"]()
    if inspect.isawaitable(result):
        result = await result
    return result


def serve(host: str = "0.0.0.0", port: int = 8080):
    """Start the microservice server with all registered agents.

    Each `@service` decorator creates an endpoint at its configured path.

    Requires: pip install 'chainforge[server]' (fastapi + uvicorn)
    """
    try:
        from fastapi import FastAPI, HTTPException
        import uvicorn
    except ImportError:
        print("ERROR: HTTP server requires `fastapi` and `uvicorn`.")
        print("Install with: pip install 'chainforge[server]'")
        sys.exit(1)

    app = FastAPI(title="ChainForge Microservices", version="0.1.0")

    # Register all agents
    for agent_name, config in _registry.items():
        _path = config["path"]
        _agent_name = agent_name
        _api_key = config.get("api_key") or os.environ.get("CHAINFORGE_API_KEY")

        async def _run(prompt: str, thread_id: str | None = None):
            agent = await _build_agent(_agent_name)
            stream = await agent.run(prompt, thread_id=thread_id)
            return await stream.collect_text()

        @app.post(_path)
        async def handle(data: dict, name: str = _agent_name):
            # Simple API key check
            if _api_key:
                req_key = data.get("api_key", "")
                if req_key != _api_key:
                    raise HTTPException(status_code=403, detail="Invalid API key")
            prompt = data.get("prompt", "")
            if not prompt:
                raise HTTPException(status_code=400, detail="Missing 'prompt' field")
            result = await _run(prompt, data.get("thread_id"))
            return {"result": result}

        @app.get(_path + "/openapi.json")
        def openapi():
            return {
                "openapi": "3.1.0",
                "info": {"title": f"Agent: {_agent_name}", "description": config.get("doc", "")},
                "paths": {
                    _path: {
                        "post": {
                            "summary": f"Run {_agent_name}",
                            "requestBody": {
                                "content": {"application/json": {"schema": {
                                    "type": "object",
                                    "properties": {
                                        "prompt": {"type": "string"},
                                        "thread_id": {"type": "string", "nullable": True},
                                    },
                                    "required": ["prompt"],
                                }}}
                            },
                            "responses": {"200": {"description": "Agent response"}},
                        }
                    }
                },
            }

        print(f"  Registered: {_agent_name} -> POST {_path}")

    print(f"\nStarting ChainForge Microservices on {host}:{port}")
    print(f"  Endpoints:")
    for config in _registry.values():
        print(f"    POST {config['path']}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    serve()


__all__ = ["service", "serve", "get_registry"]
