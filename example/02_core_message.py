"""example/02_core_message.py — Message types verification."""
import sys, asyncio
from chainforge.core.message import Message, Role, ToolCall, ContentPart, ContentPartType
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

def test_roles():
    check("r1: Role.system", Role.system.value == "system")
    check("r2: Role.user", Role.user.value == "user")
    check("r3: Role.assistant", Role.assistant.value == "assistant")
    check("r4: Role.tool", Role.tool.value == "tool")

def test_message_factories():
    m1 = Message.system("You are a bot")
    check("m1: role system", m1.role == Role.system)
    check("m2: content set", m1.content == "You are a bot")
    m2 = Message.user("Hello")
    check("m3: role user", m2.role == Role.user)
    check("m4: content", m2.content == "Hello")
    m3 = Message.assistant("Hi there")
    check("m5: role assistant", m3.role == Role.assistant)
    check("m6: content", m3.content == "Hi there")

def test_tool_result():
    mr = Message.tool_result("tc1", "get_weather", "Sunny")
    check("tr1: role tool", mr.role == Role.tool)
    check("tr2: tool_call_id", mr.tool_call_id == "tc1")
    check("tr3: name", mr.name == "get_weather")
    check("tr4: content", mr.content == "Sunny")

def test_tool_call():
    tc = ToolCall(id="c1", name="search", args={"q": "hi"})
    check("tc1: id", tc.id == "c1")
    check("tc2: name", tc.name == "search")
    check("tc3: args", tc.args == {"q": "hi"})

def test_content_part():
    ct = ContentPart.from_text("hello")
    check("cp1: from_text type", ct.type == ContentPartType.text)
    check("cp2: from_text content", ct.text_data == "hello")
    ci = ContentPart.from_image_url("http://example.com/img.png")
    check("cp3: from_image type", ci.type == ContentPartType.image_url)
    check("cp4: from_image url", ci.image_url == "http://example.com/img.png")

def test_message_openai():
    m = Message.user("Hello")
    d = m.model_dump_openai()
    check("oa1: role", d["role"] == "user")
    check("oa2: content", d["content"] == "Hello")

def test_message_assistant_tool_calls():
    tc = ToolCall(id="c1", name="search", args={"q": "test"})
    m = Message.assistant(tool_calls=[tc])
    check("atc1: assistant role", m.role == Role.assistant)
    check("atc2: has tool_calls", m.tool_calls is not None and len(m.tool_calls) == 1)
    check("atc3: content None", m.content is None)

def test_metadata():
    m = Message.user("Hi", metadata={"source": "web"})
    check("md1: metadata set", m.metadata == {"source": "web"})

def main():
    print("=" * 58)
    print("  Core Message \u2014 roles, factories, ToolCall, ContentPart")
    print("=" * 58)
    test_roles(); test_message_factories(); test_tool_result()
    test_tool_call(); test_content_part(); test_message_openai()
    test_message_assistant_tool_calls(); test_metadata()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
