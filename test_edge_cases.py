#!/usr/bin/env python3

from nllm.utils import extract_json_from_text

# Test cases for your specific scenarios

# 1. Raw JSON without any markdown ticks
print("=== Case 1: Raw JSON without ticks ===")
raw_json = '''
{
  "analysis": "complete",
  "score": 95,
  "recommendations": ["fix typo", "add tests"]
}
'''
result1 = extract_json_from_text(raw_json)
print(f"Input: {repr(raw_json)}")
print(f"Result: {result1}")
print()

# 2. Code blocks with ticks but NO language specifier
print("=== Case 2: Code blocks without language specifier ===")
no_lang_specifier = '''Here's the analysis result:

```
{
  "status": "success",
  "data": {
    "processed": 42,
    "errors": 0
  }
}
```

Done processing.'''
result2 = extract_json_from_text(no_lang_specifier)
print(f"Input: {repr(no_lang_specifier)}")
print(f"Result: {result2}")
print()

# 3. Multiple code blocks - some with JSON, some without
print("=== Case 3: Mixed code blocks ===")
mixed_blocks = '''First, let's look at the config:

```yaml
name: test
version: 1.0
```

Then here's the result:

```
{"outcome": "passed", "duration": "2.5s"}
```

And some code:

```python
print("hello")
```'''
result3 = extract_json_from_text(mixed_blocks)
print(f"Input: {repr(mixed_blocks)}")
print(f"Result: {result3}")
print()

# 4. JSON embedded in prose without any code blocks
print("=== Case 4: JSON embedded in regular text ===")
embedded_json = '''The API returned {"success": true, "count": 15} which indicates the operation completed successfully.'''
result4 = extract_json_from_text(embedded_json)
print(f"Input: {repr(embedded_json)}")
print(f"Result: {result4}")
print()

# 5. Complex JSON with different markdown styles
print("=== Case 5: Complex nested JSON in plain code block ===")
complex_no_lang = '''```
{
  "review": {
    "status": "approved",
    "findings": [
      {
        "type": "warning",
        "message": "Consider refactoring",
        "line": 42
      }
    ],
    "metrics": {
      "complexity": 7.2,
      "coverage": 0.85
    }
  }
}
```'''
result5 = extract_json_from_text(complex_no_lang)
print(f"Input: {repr(complex_no_lang)}")
print(f"Result: {result5}")
print()

# 6. JSON array without language specifier
print("=== Case 6: JSON array in plain code block ===")
array_no_lang = '''The top issues are:

```
[
  {"id": 1, "severity": "high", "title": "Security vulnerability"},
  {"id": 2, "severity": "medium", "title": "Performance issue"},
  {"id": 3, "severity": "low", "title": "Code style"}
]
```'''
result6 = extract_json_from_text(array_no_lang)
print(f"Input: {repr(array_no_lang)}")
print(f"Result: {result6}")
print()