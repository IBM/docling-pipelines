"""Validator for ChunkerOperator configuration parameters."""

from typing import Any

from common.exceptions.error_messages import ValidationCodeMessages, ValidationMessage
from common.util.core.validation import is_value_in_range


class ChunkerValidator:
    """Validator for ChunkerOperator configuration parameters."""

    @staticmethod
    def validate_simple_chunker(
        chunk_size: int,
        chunk_overlap: int,
        chunk_type: str,
        should_validate_field_fn,
        errors: list[Any],
    ) -> None:
        """
        Validate simple chunking configuration with reduced nesting.

        Args:
            chunk_size: Size of each chunk in characters
            chunk_overlap: Overlap between consecutive chunks
            chunk_type: Type of chunking strategy
            should_validate_field_fn: Function to check if field should be validated
            errors: List to append validation errors to
        """
        # Import constants to avoid circular dependency
        from core.operators.functional.chunker import (
            CHUNK_MAX_SIZE,
            CHUNK_MIN_SIZE,
            CHUNK_OVERLAP_MAX_SIZE,
            CHUNK_OVERLAP_MIN_SIZE,
            VALID_CHUNK_TYPES,
        )

        # Validate chunk_size
        if should_validate_field_fn(field_value=chunk_size):
            is_size_invalid = chunk_size is not None and not is_value_in_range(
                value=chunk_size,
                min_value=CHUNK_MIN_SIZE,
                max_value=CHUNK_MAX_SIZE,
            )
            if is_size_invalid:
                errors.append(f"Invalid input: chunk_size must be between {CHUNK_MIN_SIZE} and {CHUNK_MAX_SIZE}.")

        # Validate chunk_overlap
        if should_validate_field_fn(field_value=chunk_overlap):
            is_overlap_invalid = chunk_overlap is not None and not is_value_in_range(
                value=chunk_overlap,
                min_value=CHUNK_OVERLAP_MIN_SIZE,
                max_value=CHUNK_OVERLAP_MAX_SIZE,
            )
            if is_overlap_invalid:
                errors.append(
                    f"Invalid input: chunk_overlap must be between {CHUNK_OVERLAP_MIN_SIZE} and {CHUNK_OVERLAP_MAX_SIZE}."
                )

        # Validate chunk_type
        if should_validate_field_fn(field_value=chunk_type):
            if chunk_type not in VALID_CHUNK_TYPES:
                errors.append(
                    ValidationMessage.create(
                        message=f"Invalid chunk_type: {chunk_type}",
                        message_code=ValidationCodeMessages.CHUNKER_INVALID_CHUNK_TYPE.name,
                        chunk_type=chunk_type,
                    )
                )

    @staticmethod
    def validate_semantic_chunker(
        breakpoint_threshold_type: str,
        breakpoint_threshold_amount: float | None,
        semantic_embeddings_model: str,
        should_validate_field_fn,
        errors: list[Any],
    ) -> None:
        """
        Validate semantic chunking configuration with reduced nesting.

        Args:
            breakpoint_threshold_type: Method for detecting boundaries
            breakpoint_threshold_amount: Threshold value for the method
            semantic_embeddings_model: Ollama model for embeddings
            should_validate_field_fn: Function to check if field should be validated
            errors: List to append validation errors to
        """
        # Import constants to avoid circular dependency
        from core.operators.functional.chunker import (
            VALID_BREAKPOINT_TYPES,
            BreakpointThresholdType,
        )

        # Validate breakpoint threshold type
        if should_validate_field_fn(field_value=breakpoint_threshold_type):
            if breakpoint_threshold_type not in VALID_BREAKPOINT_TYPES:
                errors.append(
                    f"Invalid breakpoint_threshold_type: {breakpoint_threshold_type}. "
                    f"Must be one of: {', '.join(VALID_BREAKPOINT_TYPES)}"
                )

        # Validate breakpoint threshold amount if provided
        if not should_validate_field_fn(field_value=breakpoint_threshold_amount):
            return

        if breakpoint_threshold_amount is None:
            return

        # Validate based on threshold type
        is_percentile = breakpoint_threshold_type == BreakpointThresholdType.PERCENTILE.value
        is_std_dev = breakpoint_threshold_type == BreakpointThresholdType.STANDARD_DEVIATION.value

        if is_percentile:
            is_percentile_invalid = not (0 <= breakpoint_threshold_amount <= 100)
            if is_percentile_invalid:
                errors.append(
                    f"Invalid breakpoint_threshold_amount for percentile: {breakpoint_threshold_amount}. "
                    "Must be between 0 and 100."
                )
        elif is_std_dev:
            if breakpoint_threshold_amount < 0:
                errors.append(
                    f"Invalid breakpoint_threshold_amount for standard_deviation: {breakpoint_threshold_amount}. "
                    "Must be non-negative."
                )

        # Validate semantic embeddings model is not empty
        if should_validate_field_fn(field_value=semantic_embeddings_model):
            is_model_empty = not semantic_embeddings_model or not semantic_embeddings_model.strip()
            if is_model_empty:
                errors.append("semantic_embeddings_model cannot be empty for semantic chunking")

    @staticmethod
    def validate_docling_chunker(
        chunk_size: int,
        chunk_overlap: int,
        docling_tokenizer: str,
        should_validate_field_fn,
        errors: list[Any],
    ) -> None:
        """
        Validate docling chunking configuration with reduced nesting.

        Args:
            chunk_size: Size of each chunk in tokens
            chunk_overlap: Overlap between consecutive chunks
            docling_tokenizer: HuggingFace tokenizer model
            should_validate_field_fn: Function to check if field should be validated
            errors: List to append validation errors to
        """
        # Import constants to avoid circular dependency
        from core.operators.functional.chunker import (
            DOCLING_CHUNK_SIZE_MAX,
            DOCLING_CHUNK_SIZE_MIN,
        )

        # Validate chunk_size for docling chunking (token-based)
        if should_validate_field_fn(field_value=chunk_size):
            is_size_invalid = chunk_size is not None and not is_value_in_range(
                value=chunk_size,
                min_value=DOCLING_CHUNK_SIZE_MIN,
                max_value=DOCLING_CHUNK_SIZE_MAX,
            )
            if is_size_invalid:
                errors.append(
                    f"Invalid input: chunk_size for hybrid chunking must be between {DOCLING_CHUNK_SIZE_MIN} and {DOCLING_CHUNK_SIZE_MAX} tokens."
                )

        # Validate chunk_overlap for docling chunking
        if should_validate_field_fn(field_value=chunk_overlap):
            if chunk_overlap is None:
                return

            if chunk_overlap < 0:
                errors.append("Invalid input: chunk_overlap must be non-negative for hybrid chunking.")
                return

            is_overlap_too_large = chunk_size is not None and chunk_overlap >= chunk_size
            if is_overlap_too_large:
                errors.append("Invalid input: chunk_overlap must be less than chunk_size for hybrid chunking.")

        # Validate tokenizer is not empty
        if should_validate_field_fn(field_value=docling_tokenizer):
            is_tokenizer_empty = not docling_tokenizer or not docling_tokenizer.strip()
            if is_tokenizer_empty:
                errors.append("docling_tokenizer cannot be empty for hybrid chunking")

    @staticmethod
    def validate_summarization(
        enable_summarization: bool,
        summarization_model: str,
        should_validate_field_fn,
        errors: list[Any],
    ) -> None:
        """
        Validate summarization configuration with reduced nesting.

        Args:
            enable_summarization: Whether summarization is enabled
            summarization_model: Ollama model for summarization
            should_validate_field_fn: Function to check if field should be validated
            errors: List to append validation errors to
        """
        if not should_validate_field_fn(field_value=enable_summarization):
            return

        if not enable_summarization:
            return

        if not should_validate_field_fn(field_value=summarization_model):
            return

        is_model_invalid = summarization_model is None or len(summarization_model) == 0
        if is_model_invalid:
            errors.append(
                "Invalid model id. Summarization Model id not provided. "
                "Please select a foundation model from the available models."
            )
