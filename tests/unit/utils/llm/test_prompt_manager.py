"""Tests for PromptManager utility."""

import json
from pathlib import Path

import pytest

from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.llm.prompt_manager import PromptManager


class TestPromptManager:
    """Test cases for PromptManager class."""

    @pytest.fixture
    def temp_prompt_file(self, tmp_path):
        """Create a temporary prompt file for testing."""
        prompt_data = {
            "description": "Test prompt for {task}",
            "examples": [
                {"input": "example 1", "output": "result 1"},
                {"input": "example 2", "output": "result 2"},
            ],
        }
        prompt_file = tmp_path / "test_prompt.json"
        prompt_file.write_text(json.dumps(prompt_data))
        return prompt_file

    @pytest.fixture
    def temp_simple_prompt_file(self, tmp_path):
        """Create a simple prompt file without examples."""
        prompt_data = {"description": "Simple prompt without examples"}
        prompt_file = tmp_path / "simple_prompt.json"
        prompt_file.write_text(json.dumps(prompt_data))
        return prompt_file

    @pytest.fixture
    def temp_format_prompt_file(self, tmp_path):
        """Create a prompt file with format placeholders."""
        prompt_data = {
            "description": "Analyze {document_type} for {purpose} using {method}",
            "examples": [],
        }
        prompt_file = tmp_path / "format_prompt.json"
        prompt_file.write_text(json.dumps(prompt_data))
        return prompt_file

    def test_init_with_valid_file(self, temp_prompt_file):
        """Test initialization with valid prompt file."""
        manager = PromptManager(temp_prompt_file)
        assert manager.prompt_file == temp_prompt_file
        assert not manager.is_cached

    def test_init_with_string_path(self, temp_prompt_file):
        """Test initialization with string path."""
        manager = PromptManager(str(temp_prompt_file))
        assert manager.prompt_file == Path(temp_prompt_file)

    def test_load_prompt_success(self, temp_prompt_file):
        """Test successful prompt loading."""
        manager = PromptManager(temp_prompt_file)
        prompt = manager.load_prompt()
        assert "Test prompt for {task}" in prompt
        assert "example 1" in prompt
        assert "result 1" in prompt
        assert manager.is_cached

    def test_load_prompt_caching(self, temp_prompt_file):
        """Test that prompt is cached after first load."""
        manager = PromptManager(temp_prompt_file)
        prompt1 = manager.load_prompt()
        prompt2 = manager.load_prompt()
        assert prompt1 == prompt2
        assert manager.is_cached

    def test_load_prompt_without_examples(self, temp_simple_prompt_file):
        """Test loading prompt without examples section."""
        manager = PromptManager(temp_simple_prompt_file)
        prompt = manager.load_prompt()
        assert prompt == "Simple prompt without examples"
        assert "Input:" not in prompt

    def test_load_prompt_file_not_found(self, tmp_path):
        """Test loading non-existent prompt file."""
        non_existent = tmp_path / "non_existent.json"
        manager = PromptManager(non_existent)
        with pytest.raises(DocpipeException) as exc_info:
            manager.load_prompt()
        assert exc_info.value.error_code == ErrorCode.INVALID_CONFIGURATION
        assert "not found" in str(exc_info.value).lower()

    def test_load_prompt_invalid_json(self, tmp_path):
        """Test loading file with invalid JSON."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ invalid json }")
        manager = PromptManager(invalid_file)
        with pytest.raises(DocpipeException) as exc_info:
            manager.load_prompt()
        assert exc_info.value.error_code == ErrorCode.INVALID_CONFIGURATION
        assert "invalid json" in str(exc_info.value).lower()

    def test_load_prompt_missing_description(self, tmp_path):
        """Test loading prompt file without description field."""
        no_desc_file = tmp_path / "no_desc.json"
        no_desc_file.write_text(json.dumps({"examples": []}))
        manager = PromptManager(no_desc_file)
        with pytest.raises(DocpipeException) as exc_info:
            manager.load_prompt()
        assert exc_info.value.error_code == ErrorCode.INVALID_CONFIGURATION
        assert "description" in str(exc_info.value).lower()

    def test_format_prompt_with_kwargs(self, temp_format_prompt_file):
        """Test formatting prompt with keyword arguments."""
        manager = PromptManager(temp_format_prompt_file)
        formatted = manager.format_prompt(document_type="PDF", purpose="classification", method="LLM")
        assert "Analyze PDF for classification using LLM" in formatted

    def test_format_prompt_without_loading_first(self, temp_format_prompt_file):
        """Test that format_prompt loads prompt if not cached."""
        manager = PromptManager(temp_format_prompt_file)
        assert not manager.is_cached
        formatted = manager.format_prompt(document_type="PDF", purpose="classification", method="LLM")
        assert manager.is_cached
        assert "Analyze PDF for classification using LLM" in formatted

    def test_format_prompt_missing_placeholder(self, temp_format_prompt_file):
        """Test formatting with missing placeholder raises error."""
        manager = PromptManager(temp_format_prompt_file)
        with pytest.raises(KeyError):
            manager.format_prompt(document_type="PDF", purpose="classification")

    def test_format_prompt_extra_kwargs(self, temp_format_prompt_file):
        """Test formatting with extra kwargs (should be ignored)."""
        manager = PromptManager(temp_format_prompt_file)
        formatted = manager.format_prompt(
            document_type="PDF",
            purpose="classification",
            method="LLM",
            extra_param="ignored",
        )
        assert "Analyze PDF for classification using LLM" in formatted

    def test_clear_cache(self, temp_prompt_file):
        """Test clearing the prompt cache."""
        manager = PromptManager(temp_prompt_file)
        manager.load_prompt()
        assert manager.is_cached
        manager.clear_cache()
        assert not manager.is_cached

    def test_clear_cache_when_not_cached(self, temp_prompt_file):
        """Test clearing cache when nothing is cached."""
        manager = PromptManager(temp_prompt_file)
        assert not manager.is_cached
        manager.clear_cache()  # Should not raise error
        assert not manager.is_cached

    def test_multiple_instances_independent_caches(self, temp_prompt_file):
        """Test that multiple instances have independent caches."""
        manager1 = PromptManager(temp_prompt_file)
        manager2 = PromptManager(temp_prompt_file)

        manager1.load_prompt()
        assert manager1.is_cached
        assert not manager2.is_cached

        manager2.load_prompt()
        assert manager2.is_cached

        manager1.clear_cache()
        assert not manager1.is_cached
        assert manager2.is_cached

    def test_load_prompt_with_empty_examples(self, tmp_path):
        """Test loading prompt with empty examples list."""
        prompt_data = {"description": "Test prompt", "examples": []}
        prompt_file = tmp_path / "empty_examples.json"
        prompt_file.write_text(json.dumps(prompt_data))

        manager = PromptManager(prompt_file)
        prompt = manager.load_prompt()
        assert prompt == "Test prompt"
        assert "Input:" not in prompt

    def test_load_prompt_with_complex_examples(self, tmp_path):
        """Test loading prompt with complex example structures."""
        prompt_data = {
            "description": "Complex prompt",
            "examples": [
                {
                    "input": {"text": "input 1", "metadata": {"type": "test"}},
                    "output": {"result": "output 1", "confidence": 0.9},
                },
            ],
        }
        prompt_file = tmp_path / "complex_examples.json"
        prompt_file.write_text(json.dumps(prompt_data))

        manager = PromptManager(prompt_file)
        prompt = manager.load_prompt()
        assert "Complex prompt" in prompt
        assert "Input:" in prompt
        assert "input 1" in prompt
        assert "output 1" in prompt

    def test_load_prompt_with_multiline_description(self, tmp_path):
        """Test loading prompt with multiline description."""
        prompt_data = {
            "description": "Line 1\nLine 2\nLine 3",
            "examples": [],
        }
        prompt_file = tmp_path / "multiline.json"
        prompt_file.write_text(json.dumps(prompt_data))

        manager = PromptManager(tmp_path / "multiline.json")
        prompt = manager.load_prompt()
        assert "Line 1\nLine 2\nLine 3" in prompt

    def test_format_prompt_with_special_characters(self, tmp_path):
        """Test formatting prompt with special characters in placeholders."""
        prompt_data = {
            "description": "Process {file_name} with {special_chars}",
            "examples": [],
        }
        prompt_file = tmp_path / "special.json"
        prompt_file.write_text(json.dumps(prompt_data))

        manager = PromptManager(prompt_file)
        formatted = manager.format_prompt(file_name="test@file#123.txt", special_chars="!@#$%^&*()")
        assert "test@file#123.txt" in formatted
        assert "!@#$%^&*()" in formatted

    def test_load_prompt_preserves_json_structure(self, tmp_path):
        """Test that JSON structure in examples is preserved."""
        prompt_data = {
            "description": "Test",
            "examples": [{"input": '{"key": "value"}', "output": '{"result": "success"}'}],
        }
        prompt_file = tmp_path / "json_structure.json"
        prompt_file.write_text(json.dumps(prompt_data))

        manager = PromptManager(prompt_file)
        prompt = manager.load_prompt()
        # JSON strings are escaped when dumped, so check for escaped quotes
        assert "key" in prompt and "value" in prompt
        assert "result" in prompt and "success" in prompt

    def test_is_cached_property(self, temp_prompt_file):
        """Test is_cached property behavior."""
        manager = PromptManager(temp_prompt_file)
        assert not manager.is_cached
        manager.load_prompt()
        assert manager.is_cached
        manager.clear_cache()
        assert not manager.is_cached

    def test_prompt_file_property(self, temp_prompt_file):
        """Test prompt_file property returns Path object."""
        manager = PromptManager(temp_prompt_file)
        assert isinstance(manager.prompt_file, Path)
        assert manager.prompt_file == temp_prompt_file
