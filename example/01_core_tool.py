"""example/01_core_tool.py — Tool protocol verification."""
import sys, asyncio
from chainforge.core.tool import tool, FunctionTool, BaseTool
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok:
        passed += 1; print(f"  \u2705 {n}")
    else:
        failed += 1; print(f"  \u274c {n}")

async def t1():
    @tool
    def greet(name: str) -> str:
        """Greet someone warmly."""
        return f"Hello, {name}!"
    assert isinstance(greet, FunctionTool)
    check("1a: @tool returns FunctionTool", True)
    check("1b: name='greet'", greet.spec.name == "greet")
    check("1c: has desc", "Greet" in greet.spec.description)
    check("1d: has name param", "name" in greet.spec.parameters["properties"])
    check("1e: type string", greet.spec.parameters["properties"]["name"]["type"] == "string")
    check("1f: required", "name" in greet.spec.parameters["required"])
    check("1g: run works", await greet.run(name="World") == "Hello, World!")

async def t2():
    @tool(name="custom_calc", description="Calc")
    def calc(a: int, b: int) -> str:
        return str(a + b)
    check("2a: custom name", calc.spec.name == "custom_calc")
    check("2b: custom desc", calc.spec.description == "Calc")
    check("2c: int param", calc.spec.parameters["properties"]["a"]["type"] == "integer")

async def t3():
    @tool
    def bare(): pass
    check("3a: no desc", bare.spec.description == "")
    check("3b: name bare", bare.spec.name == "bare")

async def t4():
    @tool
    def search(q: str, limit: int = 10) -> str:
        """Search."""
        return f"S: {q} / {limit}"
    check("4a: q required", "q" in search.spec.parameters["required"])
    check("4b: limit not required", "limit" not in search.spec.parameters["required"])
    check("4c: run works", await search.run(q="hi", limit=5) == "S: hi / 5")

async def t5():
    class D(BaseTool):
        name = "doubler"
        description = "Double int"
        def _run(self, x: int) -> str:
            return str(x * 2)
    d = D()
    check("5a: name", d.spec.name == "doubler")
    check("5b: desc", d.spec.description == "Double int")
    check("5c: run", await d.run(x=21) == "42")

async def main():
    print("=" * 58)
    print("  Core Tool \u2014 @tool, ToolSpec, schema, execution")
    print("=" * 58)
    await t1(); await t2(); await t3(); await t4(); await t5()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

asyncio.run(main())
