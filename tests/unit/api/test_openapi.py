"""Unit tests for the custom OpenAPI schema generator."""

import copy

from docpipe.api.openapi import _remove_nullable_keywords


class TestRemoveNullableKeywords:
    """Tests for _remove_nullable_keywords."""

    def test_removes_nullable_key(self):
        result = _remove_nullable_keywords({"type": "string", "nullable": True})
        assert "nullable" not in result

    def test_collapses_single_item_anyof_null_union(self):
        schema = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        result = _remove_nullable_keywords(schema)
        assert "anyOf" not in result
        assert result["type"] == "string"

    def test_preserves_multi_item_anyof_without_null(self):
        schema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
        result = _remove_nullable_keywords(schema)
        assert result["anyOf"] == [{"type": "string"}, {"type": "integer"}]

    def test_wraps_ref_in_allof_when_collapsing_anyof(self):
        schema = {"anyOf": [{"$ref": "#/components/schemas/Foo"}, {"type": "null"}]}
        result = _remove_nullable_keywords(schema)
        assert "anyOf" not in result
        assert result["allOf"] == [{"$ref": "#/components/schemas/Foo"}]

    def test_recurses_into_nested_dict(self):
        schema = {"properties": {"name": {"type": "string", "nullable": True}}}
        result = _remove_nullable_keywords(schema)
        assert "nullable" not in result["properties"]["name"]

    def test_recurses_into_list_values(self):
        schema = {"allOf": [{"type": "string", "nullable": True}]}
        result = _remove_nullable_keywords(schema)
        assert "nullable" not in result["allOf"][0]

    def test_non_dict_input_returned_unchanged(self):
        assert _remove_nullable_keywords("string") == "string"  # type: ignore[arg-type]

    def test_does_not_mutate_input(self):
        original = {"type": "string", "nullable": True, "properties": {"x": {"nullable": True}}}
        original_copy = copy.deepcopy(original)
        _remove_nullable_keywords(original)
        assert original == original_copy

    def test_does_not_mutate_nested_anyof_input(self):
        original = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        original_copy = copy.deepcopy(original)
        _remove_nullable_keywords(original)
        assert original == original_copy

    def test_result_is_independent_of_input_reference(self):
        # Regression: callers that patch the *result* must not be writing to a stale
        # pre-copy reference. Verify result and input are distinct objects.
        original = {"type": "string", "nullable": True}
        result = _remove_nullable_keywords(original)
        result["injected"] = True
        assert "injected" not in original
