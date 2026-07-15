"""example/10_parsers.py — Output parsers verification."""
import sys
from pydantic import BaseModel
from chainforge.parsers import JSONOutputParser, PydanticOutputParser
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

def test_json_parser_valid():
    parser = JSONOutputParser()
    result = parser.parse('{"name": "Alice", "age": 30}')
    check("jp1: parsed correctly", result.parsed == {"name": "Alice", "age": 30})
    check("jp2: no error", result.error is None)
    check("jp3: raw preserved", result.raw == '{"name": "Alice", "age": 30}')

def test_json_parser_array():
    parser = JSONOutputParser()
    result = parser.parse('[1, 2, 3]')
    check("jp4: array parsed", result.parsed == [1, 2, 3])

def test_json_parser_invalid():
    parser = JSONOutputParser()
    result = parser.parse("not json")
    check("jp5: error on invalid", result.error is not None)
    check("jp6: parsed is None", result.parsed is None)

def test_pydantic_parser():
    class Person(BaseModel):
        name: str
        age: int
    parser = PydanticOutputParser(pydantic_model=Person)
    result = parser.parse('{"name": "Alice", "age": 30}')
    check("pp1: parsed is Person", isinstance(result.parsed, Person))
    check("pp2: name correct", result.parsed.name == "Alice")
    check("pp3: age correct", result.parsed.age == 30)

def test_pydantic_invalid():
    class Person(BaseModel):
        name: str
        age: int
    parser = PydanticOutputParser(pydantic_model=Person)
    result = parser.parse('{"name": "Alice"}')  # missing age
    check("pp4: error on invalid", result.error is not None)

def test_format_instructions():
    class Item(BaseModel):
        id: int
        label: str
    parser = JSONOutputParser()
    instructions = parser.format_instructions()
    check("fi1: has instructions", len(instructions) > 0)

def main():
    print("=" * 58)
    print("  Parsers \u2014 JSONOutputParser, PydanticOutputParser")
    print("=" * 58)
    test_json_parser_valid(); test_json_parser_array()
    test_json_parser_invalid(); test_pydantic_parser()
    test_pydantic_invalid(); test_format_instructions()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
