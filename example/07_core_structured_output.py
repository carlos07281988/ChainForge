"""example/07_core_structured_output.py — Structured output verification."""
import sys, json
from pydantic import BaseModel
from chainforge.core.structured_output import model_to_json_schema, parse_structured_response
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

class Weather(BaseModel):
    city: str
    temperature: float
    condition: str

class Person(BaseModel):
    name: str
    age: int
    email: str | None = None

def test_model_to_schema():
    schema = model_to_json_schema(Weather)
    check("ms1: has properties", "properties" in schema)
    check("ms2: has city", "city" in schema["properties"])
    check("ms3: temp type number", schema["properties"]["temperature"]["type"] == "number")
    schema2 = model_to_json_schema(Person)
    check("ms4: optional field", "email" in schema2["properties"])
    check("ms5: name type", schema2["properties"]["name"]["type"] == "string")

def test_parse_direct_json():
    result = parse_structured_response(
        '{"city": "Beijing", "temperature": 28.0, "condition": "Sunny"}',
        Weather,
    )
    check("ps1: is Weather instance", isinstance(result, Weather))
    check("ps2: city", result.city == "Beijing")
    check("ps3: temperature", result.temperature == 28.0)
    check("ps4: condition", result.condition == "Sunny")

def test_parse_code_block():
    result = parse_structured_response(
        'Here is weather:\n```json\n{"city": "London", "temperature": 15.5, "condition": "Cloudy"}\n```',
        Weather,
    )
    check("ps5: code block parsing", result.city == "London")
    check("ps6: temp correct", result.temperature == 15.5)

def test_person_with_optional():
    result = parse_structured_response(
        '{"name": "Alice", "age": 30}',
        Person,
    )
    check("ps7: person name", result.name == "Alice")
    check("ps8: person age", result.age == 30)
    check("ps9: email None", result.email is None)

def test_parse_error():
    try:
        parse_structured_response("invalid json", Weather)
        check("pe1: should raise error", False)
    except (ValueError, json.JSONDecodeError):
        check("pe1: raises on invalid json", True)

def main():
    print("=" * 58)
    print("  Structured Output \u2014 model_to_json_schema, parse_structured")
    print("=" * 58)
    test_model_to_schema(); test_parse_direct_json()
    test_parse_code_block(); test_person_with_optional()
    test_parse_error()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
