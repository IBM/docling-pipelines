#!/usr/bin/env python3
"""
Unit tests for classification domain models.
Tests ClassificationRequest, ClassificationResponse, and build_classification_prompt.
"""

import pytest

from docpipe.core.operators.quality.classification.domain.models import (
    ClassificationRequest,
    ClassificationResponse,
    build_classification_prompt,
)


@pytest.mark.unit
class TestClassificationRequest:
    """Test ClassificationRequest domain model."""

    def test_create_request_with_dict_types(self):
        """Test creating request with dictionary of document types."""
        request = ClassificationRequest(
            content="Sample invoice content",
            document_types={
                "invoice": "Business invoice with line items",
                "receipt": "Payment receipt",
            },
            max_content_length=10000,
        )

        assert request.content == "Sample invoice content"
        assert isinstance(request.document_types, dict)
        assert len(request.document_types) == 2
        assert request.max_content_length == 10000

    def test_create_request_with_list_types(self):
        """Test creating request with list of document types."""
        request = ClassificationRequest(
            content="Sample content",
            document_types=["invoice", "receipt", "contract"],
            max_content_length=5000,
        )

        assert isinstance(request.document_types, list)
        assert len(request.document_types) == 3
        assert "invoice" in request.document_types

    def test_content_truncation(self):
        """Test that max_content_length is respected."""
        long_content = "A" * 20000
        request = ClassificationRequest(
            content=long_content,
            document_types=["invoice"],
            max_content_length=10000,
        )

        # The request stores the full content, truncation happens in prompt building
        assert len(request.content) == 20000
        assert request.max_content_length == 10000


@pytest.mark.unit
class TestClassificationResponse:
    """Test ClassificationResponse domain model."""

    def test_create_successful_response(self):
        """Test creating a successful classification response."""
        response = ClassificationResponse(
            document_type="invoice",
            confidence=9,
            reasoning="Contains line items and totals",
            success=True,
            error=None,
        )

        assert response.document_type == "invoice"
        assert response.confidence == 9
        assert response.reasoning == "Contains line items and totals"
        assert response.success is True
        assert response.error is None

    def test_create_error_response(self):
        """Test creating an error response."""
        response = ClassificationResponse(
            document_type="unknown",
            confidence=0,
            reasoning="",
            success=False,
            error="API call failed",
        )

        assert response.document_type == "unknown"
        assert response.confidence == 0
        assert response.success is False
        assert response.error == "API call failed"


@pytest.mark.unit
class TestBuildClassificationPrompt:
    """Test build_classification_prompt function."""

    def test_prompt_with_dict_types(self):
        """Test prompt generation with dictionary of document types."""
        request = ClassificationRequest(
            content="Invoice #12345\nTotal: $1000",
            document_types={
                "invoice": "Business invoice with line items",
                "receipt": "Payment receipt",
                "contract": "Legal contract",
            },
            max_content_length=10000,
        )

        prompt = build_classification_prompt(request=request)

        # Check prompt contains document types
        assert "invoice: Business invoice with line items" in prompt
        assert "receipt: Payment receipt" in prompt
        assert "contract: Legal contract" in prompt

        # Check prompt contains content
        assert "Invoice #12345" in prompt
        assert "Total: $1000" in prompt

        # Check prompt contains instructions
        assert "Classify the following document" in prompt
        assert "document_type" in prompt
        assert "confidence" in prompt
        assert "reasoning" in prompt

    def test_prompt_with_list_types(self):
        """Test prompt generation with list of document types."""
        request = ClassificationRequest(
            content="Sample content",
            document_types=["invoice", "receipt", "contract"],
            max_content_length=10000,
        )

        prompt = build_classification_prompt(request=request)

        # Check prompt contains document types as list items
        assert "- invoice" in prompt
        assert "- receipt" in prompt
        assert "- contract" in prompt

    def test_prompt_content_truncation(self):
        """Test that content is truncated in prompt."""
        long_content = "A" * 20000
        request = ClassificationRequest(
            content=long_content,
            document_types=["invoice"],
            max_content_length=5000,
        )

        prompt = build_classification_prompt(request=request)

        # The prompt should contain truncated content
        # Count 'A's in the prompt to verify truncation
        a_count = prompt.count("A")
        assert a_count <= 5000
        assert a_count > 0  # Some content should be present

    def test_prompt_with_empty_content(self):
        """Test prompt generation with empty content."""
        request = ClassificationRequest(
            content="",
            document_types=["invoice", "receipt"],
            max_content_length=10000,
        )

        prompt = build_classification_prompt(request=request)

        # Prompt should still be generated with instructions
        assert "Classify the following document" in prompt
        assert "invoice" in prompt

    def test_prompt_json_format_instructions(self):
        """Test that prompt includes JSON format instructions."""
        request = ClassificationRequest(
            content="Sample content",
            document_types=["invoice"],
            max_content_length=10000,
        )

        prompt = build_classification_prompt(request=request)

        # Check for JSON format instructions
        assert "JSON object" in prompt or "json" in prompt.lower()
        assert "document_type" in prompt
        assert "confidence" in prompt
        assert "reasoning" in prompt

    def test_prompt_example_response(self):
        """Test that prompt includes an example response."""
        request = ClassificationRequest(
            content="Sample content",
            document_types=["invoice"],
            max_content_length=10000,
        )

        prompt = build_classification_prompt(request=request)

        # Check for example response
        assert "Example" in prompt or "example" in prompt
        assert "{" in prompt  # JSON example should be present
        assert "}" in prompt
