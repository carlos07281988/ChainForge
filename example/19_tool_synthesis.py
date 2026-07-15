"""example/19_tool_synthesis.py — ToolSynthesizer verification."""
import sys, asyncio
from chainforge.tools.synthesis import ToolSynthesizer, ToolCache, SynthesizedTool
passed=0;failed=0
def c(n,o):
    global passed,failed
    if o: passed+=1; print(f"  \u2705 {n}")
    else: failed+=1; print(f"  \u274c {n}")

synth = ToolSynthesizer()
c("synth created", True)
cache = ToolCache()
c("cache created", True)

code = "def my_tool(query: str) -> str:\n    return f'Result: {query}'"
r = synth._verify_code(code)
c("verify valid code", r["success"])
c("catch syntax error", not synth._verify_code("def broken(")["success"])
name = synth._extract_function_name(code)
c("extract name", name == "my_tool")
fn = synth._code_to_function(code, "my_tool")
c("code to callable", callable(fn))
tool = synth._function_to_tool(fn, "my_tool", "test")
c("to tool name", tool.spec.name == "my_tool")
c("has params", "query" in tool.spec.parameters["properties"])

s = SynthesizedTool(name="t", code=code, is_verified=True)
c("synthesized tool model", s.name == "t")
cache.store("test", s)
found = cache.lookup("test")
c("cache lookup", found is not None)

print(f"\n  Results: {passed} passed, {failed} failed")
sys.exit(0 if failed==0 else 1)
