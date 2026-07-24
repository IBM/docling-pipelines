"""Validator for ChunkerOperator configuration parameters."""

from typing import Any

from docpipe.exceptions.error_messages import ValidationCodeMessages, ValidationMessage
from docpipe.utils.core.validation import is_value_in_range


class ChunkerValidator:
    """Validator for ChunkerOperator configuration parameters."""

    @staticmethod
    def validate_common_chunk_parameters(  # NOSONAR python:S3776
        chunk_size: int,
        chunk_overlap: int,
        chunk_type: str,
        should_validate_field_fn,
        errors: list[Any],
    ) -> None:
        """
        Validate common parameters shared across all chunking strategies.

        This includes type validation and basic range validation for chunk_size,
        chunk_overlap, and chunk_type. These validations are common to simple,
        semantic, and hybrid chunking.

        Args:
            chunk_size: Size of each chunk (characters for simple, tokens for hybrid)
            chunk_overlap: Overlap between consecutive chunks
            chunk_type: Type of chunking strategy
            should_validate_field_fn: Function to check if field should be validated
            errors: List to append validation errors to
        """
        # Import constants to avoid circular dependency
        from docpipe.core.operators.functional.chunker import VALID_CHUNK_TYPES

        # Validate chunk_size type
        if should_validate_field_fn(field_value=chunk_size):
            if chunk_size is not None and not isinstance(chunk_size, int):
                errors.append(
                    ValidationMessage.create(
                        message=f"Invalid type for chunk_size: expected int, got {type(chunk_size).__name__}",
                        message_code="CHUNKER_INVALID_CHUNK_SIZE_TYPE",
                    )
                )

        # Validate chunk_overlap type
        if should_validate_field_fn(field_value=chunk_overlap):
            if chunk_overlap is not None and not isinstance(chunk_overlap, int):
                errors.append(
                    ValidationMessage.create(
                        message=f"Invalid type for chunk_overlap: expected int, got {type(chunk_overlap).__name__}",
                        message_code="CHUNKER_INVALID_CHUNK_OVERLAP_TYPE",
                    )
                )

        # Validate chunk_overlap basic range constraints (common to all chunking types)
        # These are the fundamental constraints that apply regardless of chunking strategy
        if should_validate_field_fn(field_value=chunk_overlap):
            if chunk_overlap is not None and isinstance(chunk_overlap, int):
                # chunk_overlap must be non-negative
                if chunk_overlap < 0:
                    errors.append("Invalid input: chunk_overlap must be non-negative.")

                # chunk_overlap must be less than chunk_size
                # Only check this if chunk_overlap is non-negative to avoid confusing error messages
                if (
                    chunk_overlap >= 0
                    and chunk_size is not None
                    and isinstance(chunk_size, int)
                    and chunk_overlap >= chunk_size
                ):
                    errors.append("Invalid input: chunk_overlap must be less than chunk_size.")

        # Validate chunk_type (common to all chunking strategies)
        if should_validate_field_fn(field_value=chunk_type):
            if chunk_type not in VALID_CHUNK_TYPES:
                valid_types_str = ", ".join(VALID_CHUNK_TYPES)
                errors.append(
                    ValidationMessage.create(
                        message=f"Invalid chunk_type: {chunk_type}. Valid types: {valid_types_str}",
                        message_code=ValidationCodeMessages.CHUNKER_INVALID_CHUNK_TYPE.name,
                        chunk_type=chunk_type,
                    )
                )

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
        from docpipe.core.operators.functional.chunker import (
            CHUNK_MAX_SIZE,
            CHUNK_MIN_SIZE,
            CHUNK_OVERLAP_MAX_SIZE,
        )

        # Validate common type checks first (includes chunk_type validation)
        ChunkerValidator.validate_common_chunk_parameters(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunk_type=chunk_type,
            should_validate_field_fn=should_validate_field_fn,
            errors=errors,
        )

        # Validate chunk_size range (simple chunking specific)
        if should_validate_field_fn(field_value=chunk_size):
            if chunk_size is not None and isinstance(chunk_size, int):
                if not is_value_in_range(
                    value=chunk_size,
                    min_value=CHUNK_MIN_SIZE,
                    max_value=CHUNK_MAX_SIZE,
                ):
                    errors.append(f"Invalid input: chunk_size must be between {CHUNK_MIN_SIZE} and {CHUNK_MAX_SIZE}.")

        # Validate chunk_overlap maximum range (simple chunking specific)
        # Note: Basic validations (non-negative, less than chunk_size) are handled in validate_common_chunk_parameters()
        if should_validate_field_fn(field_value=chunk_overlap):
            if chunk_overlap is not None and isinstance(chunk_overlap, int):
                if chunk_overlap > CHUNK_OVERLAP_MAX_SIZE:
                    errors.append(f"Invalid input: chunk_overlap must not exceed {CHUNK_OVERLAP_MAX_SIZE}.")

    @staticmethod
    def validate_semantic_chunker(  # NOSONAR python:S3776
        breakpoint_threshold_type: str,
        breakpoint_threshold_amount: float | None,
        semantic_embeddings_model: str | None,
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
        from docpipe.core.operators.functional.chunker import (
            VALID_BREAKPOINT_TYPES,
            BreakpointThresholdType,
        )

        # Validate semantic embeddings model is provided and not empty
        if semantic_embeddings_model is None or (
            isinstance(semantic_embeddings_model, str) and not semantic_embeddings_model.strip()
        ):
            errors.append("semantic_embeddings_model is required and cannot be empty for semantic chunking")

        # Validate breakpoint threshold type
        if should_validate_field_fn(field_value=breakpoint_threshold_type):
            if breakpoint_threshold_type not in VALID_BREAKPOINT_TYPES:
                errors.append(
                    f"Invalid breakpoint_threshold_type: {breakpoint_threshold_type}. "
                    f"Must be one of: {', '.join(VALID_BREAKPOINT_TYPES)}"
                )

        # Validate breakpoint threshold amount if provided
        if (
            should_validate_field_fn(field_value=breakpoint_threshold_amount)
            and breakpoint_threshold_amount is not None
        ):
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

        Note: Type validation for chunk_size and chunk_overlap is handled in
        validate_simple_chunker() which is always called first. This method
        only validates hybrid-specific range checks and tokenizer.

        Args:
            chunk_size: Size of each chunk in tokens
            chunk_overlap: Overlap between consecutive chunks
            docling_tokenizer: HuggingFace tokenizer model
            should_validate_field_fn: Function to check if field should be validated
            errors: List to append validation errors to
        """
        # Import constants to avoid circular dependency
        from docpipe.core.operators.functional.chunker import (
            DOCLING_CHUNK_SIZE_MAX,
            DOCLING_CHUNK_SIZE_MIN,
        )

        # Validate chunk_size range for docling chunking (token-based, hybrid-specific)
        if should_validate_field_fn(field_value=chunk_size):
            if chunk_size is not None and isinstance(chunk_size, int):
                if not is_value_in_range(
                    value=chunk_size,
                    min_value=DOCLING_CHUNK_SIZE_MIN,
                    max_value=DOCLING_CHUNK_SIZE_MAX,
                ):
                    errors.append(
                        f"Invalid input: chunk_size for hybrid chunking must be between {DOCLING_CHUNK_SIZE_MIN} and {DOCLING_CHUNK_SIZE_MAX} tokens."
                    )

        # Note: chunk_overlap basic validations (non-negative, less than chunk_size) are now
        # handled in validate_common_chunk_parameters(). No additional hybrid-specific
        # chunk_overlap validations are needed.

        # Validate tokenizer is not empty
        if should_validate_field_fn(field_value=docling_tokenizer):
            is_tokenizer_empty = not docling_tokenizer or not docling_tokenizer.strip()
            if is_tokenizer_empty:
                errors.append("docling_tokenizer cannot be empty for hybrid chunking")

    @staticmethod
    def validate_summarization(  # NOSONAR python:S3776
        enable_summarization: bool,
        summarization_model: str,
        should_validate_field_fn,
        errors: list[Any],
        max_input_tokens: int | None = None,
        summary_sentences: int | None = None,
        summary_max_words: int | None = None,
    ) -> None:
        """
        Validate summarization configuration with reduced nesting.

        Args:
            enable_summarization: Whether summarization is enabled
            summarization_model: Ollama model for summarization
            should_validate_field_fn: Function to check if field should be validated
            errors: List to append validation errors to
            max_input_tokens: Maximum input tokens per summarization request
            summary_sentences: Number of sentences in each summary
            summary_max_words: Maximum words per summary
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

        # Validate max_input_tokens
        if max_input_tokens is not None and should_validate_field_fn(field_value=max_input_tokens):
            if not is_value_in_range(value=max_input_tokens, min_value=1000, max_value=32000):
                errors.append(f"Invalid max_input_tokens: {max_input_tokens}. Must be between 1000 and 32000.")

        # Validate summary_sentences
        if summary_sentences is not None and should_validate_field_fn(field_value=summary_sentences):
            if not is_value_in_range(value=summary_sentences, min_value=1, max_value=5):
                errors.append(f"Invalid summary_sentences: {summary_sentences}. Must be between 1 and 5.")

        # Validate summary_max_words
        if summary_max_words is not None and should_validate_field_fn(field_value=summary_max_words):
            if not is_value_in_range(value=summary_max_words, min_value=10, max_value=100):
                errors.append(f"Invalid summary_max_words: {summary_max_words}. Must be between 10 and 100.")
