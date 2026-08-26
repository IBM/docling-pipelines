"""Tests for LLM JSON parser utility."""

import pytest

from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.llm.json_parser import parse_llm_json_response


class TestParseJSONResponse:
    """Test cases for parse_llm_json_response function."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON directly."""
        response = '{"key": "value", "number": 42}'
        result = parse_llm_json_response(response)
        assert result == {"key": "value", "number": 42}

    def test_parse_json_with_whitespace(self):
        """Test parsing JSON with leading/trailing whitespace."""
        response = '  \n  {"key": "value"}  \n  '
        result = parse_llm_json_response(response)
        assert result == {"key": "value"}

    def test_parse_json_in_markdown_code_block(self):
        """Test extracting JSON from markdown code block."""
        response = """Here's the result:
```json
{"key": "value", "number": 42}
```
That's it!"""
        result = parse_llm_json_response(response)
        assert result == {"key": "value", "number": 42}

    def test_parse_json_in_code_block_without_language(self):
        """Test extracting JSON from code block without language specifier."""
        response = """```
{"key": "value"}
```"""
        result = parse_llm_json_response(response)
        assert result == {"key": "value"}

    def test_parse_json_with_text_before_and_after(self):
        """Test extracting JSON when surrounded by text."""
        response = 'Some text before {"key": "value", "number": 42} some text after'
        result = parse_llm_json_response(response)
        assert result == {"key": "value", "number": 42}

    def test_parse_nested_json(self):
        """Test parsing nested JSON structures."""
        response = '{"outer": {"inner": {"deep": "value"}}, "array": [1, 2, 3]}'
        result = parse_llm_json_response(response)
        assert result == {"outer": {"inner": {"deep": "value"}}, "array": [1, 2, 3]}

    def test_parse_json_with_special_characters(self):
        """Test parsing JSON with special characters."""
        response = '{"text": "Line 1\\nLine 2", "quote": "He said \\"hello\\""}'
        result = parse_llm_json_response(response)
        assert result == {"text": "Line 1\nLine 2", "quote": 'He said "hello"'}

    def test_parse_json_array(self):
        """Test parsing JSON array."""
        response = '[{"id": 1}, {"id": 2}]'
        result = parse_llm_json_response(response)
        assert result == [{"id": 1}, {"id": 2}]

    def test_parse_json_with_multiple_code_blocks(self):
        """Test extracting JSON from first code block when multiple exist."""
        response = """First block:
```json
{"first": "block"}
```
Second block:
```json
{"second": "block"}
```"""
        result = parse_llm_json_response(response)
        assert result == {"first": "block"}

    def test_parse_malformed_json_raises_exception(self):
        """Test that malformed JSON raises DocpipeException."""
        response = '{"key": "value", "incomplete"'
        with pytest.raises(DocpipeException) as exc_info:
            parse_llm_json_response(response)
        assert exc_info.value.error_code == ErrorCode.INVALID_RESPONSE

    def test_parse_empty_string_raises_exception(self):
        """Test that empty string raises DocpipeException."""
        with pytest.raises(DocpipeException) as exc_info:
            parse_llm_json_response("")
        assert exc_info.value.error_code == ErrorCode.INVALID_RESPONSE

    def test_parse_whitespace_only_raises_exception(self):
        """Test that whitespace-only string raises DocpipeException."""
        with pytest.raises(DocpipeException) as exc_info:
            parse_llm_json_response("   \n   \t   ")
        assert exc_info.value.error_code == ErrorCode.INVALID_RESPONSE

    def test_parse_no_json_content_raises_exception(self):
        """Test that text without JSON raises DocpipeException."""
        response = "This is just plain text without any JSON"
        with pytest.raises(DocpipeException) as exc_info:
            parse_llm_json_response(response)
        assert exc_info.value.error_code == ErrorCode.INVALID_RESPONSE

    def test_parse_invalid_json_in_code_block_raises_exception(self):
        """Test that invalid JSON in code block raises DocpipeException."""
        response = """```json
{"key": "value", invalid}
```"""
        with pytest.raises(DocpipeException) as exc_info:
            parse_llm_json_response(response)
        assert exc_info.value.error_code == ErrorCode.INVALID_RESPONSE

    def test_parse_json_with_comments_raises_exception(self):
        """Test that JSON with comments raises DocpipeException."""
        response = """{
    // This is a comment
    "key": "value"
}"""
        with pytest.raises(DocpipeException) as exc_info:
            parse_llm_json_response(response)
        assert exc_info.value.error_code == ErrorCode.INVALID_RESPONSE

    def test_log_on_error_parameter(self):
        """Test that log_on_error parameter is accepted."""
        response = '{"key": "value"}'
        result = parse_llm_json_response(response, log_on_error=False)
        assert result == {"key": "value"}

    def test_log_level_parameter(self):
        """Test that log_level parameter is accepted."""
        response = '{"key": "value"}'
        result = parse_llm_json_response(response, log_level="info")
        assert result == {"key": "value"}

    def test_parse_json_with_unicode(self):
        """Test parsing JSON with unicode characters."""
        response = '{"text": "Hello 世界 🌍", "emoji": "😀"}'
        result = parse_llm_json_response(response)
        assert result == {"text": "Hello 世界 🌍", "emoji": "😀"}

    def test_parse_json_with_null_values(self):
        """Test parsing JSON with null values."""
        response = '{"key": null, "number": 0, "empty": ""}'
        result = parse_llm_json_response(response)
        assert result == {"key": None, "number": 0, "empty": ""}

    def test_parse_json_with_boolean_values(self):
        """Test parsing JSON with boolean values."""
        response = '{"true_val": true, "false_val": false}'
        result = parse_llm_json_response(response)
        assert result == {"true_val": True, "false_val": False}

    def test_parse_json_with_numeric_values(self):
        """Test parsing JSON with various numeric values."""
        response = '{"int": 42, "float": 3.14, "negative": -10, "scientific": 1.5e-10}'
        result = parse_llm_json_response(response)
        assert result == {"int": 42, "float": 3.14, "negative": -10, "scientific": 1.5e-10}

    def test_parse_json_between_braces_fallback(self):
        """Test fallback to extracting content between first { and last }."""
        response = 'Some text {"key": "value"} more text'
        result = parse_llm_json_response(response)
        assert result == {"key": "value"}

    def test_parse_json_with_multiple_objects_extracts_first(self):
        """Test that when multiple JSON objects exist, first complete one is extracted."""
        response = 'Text before {"first": "object"} middle text'
        result = parse_llm_json_response(response)
        assert result == {"first": "object"}

    def test_parse_json_skips_non_json_code_blocks(self):
        """Test parser skips non-JSON code blocks and finds valid JSON in a later block."""
        response = """First block contains Python:
```python
def hello():
    print("world")
```
Second block contains JSON:
```json
{"key": "value"}
```"""
        result = parse_llm_json_response(response)
        assert result == {"key": "value"}

    def test_parse_json_with_nested_braces_in_strings(self):
        """Test parsing JSON with nested braces inside string values."""
        response = '{"template": "use {placeholder} here", "nested": {"a": 1}}'
        result = parse_llm_json_response(response)
        assert result == {"template": "use {placeholder} here", "nested": {"a": 1}}

    def test_parse_json_with_escaped_quotes(self):
        """Test parsing JSON with escaped quotes inside string values."""
        response = '{"message": "She said \\"hello\\" to him", "valid": true}'
        result = parse_llm_json_response(response)
        assert result == {"message": 'She said "hello" to him', "valid": True}

    def test_parse_json_with_trailing_text_after_closing_brace(self):
        """Test that valid JSON followed by prose/explanation text is parsed correctly.

        LLMs often append explanation text after the JSON object, causing json.loads
        to fail with 'Extra data'. The brace-depth fallback must find the matching
        closing brace rather than the last } in the string.
        """
        response = (
            '{"invoice_id": "0298878900", "line_items": [{"amount": 5630, "quantity": 10}]}\n\n'
            "The above JSON contains the extracted invoice data. Note that some fields are null."
        )
        result = parse_llm_json_response(response)
        assert result == {"invoice_id": "0298878900", "line_items": [{"amount": 5630, "quantity": 10}]}

    def test_parse_json_with_trailing_brace_in_prose(self):
        """Test that prose containing } characters after the JSON does not confuse the parser."""
        response = '{"key": "value"} (see schema definition in config/schema.json}'
        result = parse_llm_json_response(response)
        assert result == {"key": "value"}

    def test_parse_json_with_invalid_escape_sequences(self):
        """Test that invalid JSON escape sequences emitted by LLMs are sanitized.

        LLMs sometimes emit raw backslashes inside string values that are not valid
        JSON escape sequences (e.g. Windows-style paths or address abbreviations like
        l\\IC). json.loads rejects these with 'Invalid \\escape'. The sanitizer
        strips the backslash so the string becomes parseable.
        """
        response = '{"vendor_address": "1056 STRATFORD COURT GOLDSBORO l\\IC 27530", "invoice_id": "0298878900"}'
        result = parse_llm_json_response(response)
        assert result["invoice_id"] == "0298878900"
        assert "GOLDSBORO" in result["vendor_address"]

    def test_parse_json_invalid_escape_in_nested_value(self):
        """Test sanitization works on invalid escapes inside nested objects."""
        response = '{"items": [{"path": "C:\\Users\\admin\\docs"}]}'
        result = parse_llm_json_response(response)
        assert "Users" in result["items"][0]["path"]
