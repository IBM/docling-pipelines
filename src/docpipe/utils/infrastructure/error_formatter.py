"""Error formatting utilities for user-friendly error display.

This module provides formatting for docpipe exceptions to display errors
in a clear, actionable format that matches the FlowExecutionReporter style.
"""

from __future__ import annotations

import re
import textwrap
from typing import Any, ClassVar

from docpipe.exceptions.docpipe_exceptions import (
    DocpipeException,
    FlowValidationException,
    ValidationAlert,
)
from docpipe.exceptions.error_messages import ValidationMessage


class ErrorFormatter:
    """Formats docpipe exceptions for user-friendly console display.

    Provides card-based error formatting with clear visual separation,
    operator context, available/valid values, and actionable suggestions.
    Matches the visual style of FlowExecutionReporter (80-char width).
    """

    WIDTH = 80
    SEPARATOR = "=" * WIDTH
    CARD_SEPARATOR = "─" * (WIDTH - 1)

    STANDARD_ERROR_FIELDS: ClassVar[set[str]] = {
        "code",
        "message",
        "message_code",
        "node_id",
        "node_name",
        "operator",
    }

    def format_validation_exception(self, *, exception: FlowValidationException, flow_name: str | None = None) -> str:
        """Format a FlowValidationException with card-based layout."""
        if not exception.errors:
            return self.format_generic_exception(exception=exception)

        return self.format_validation_errors(errors=exception.errors, flow_name=flow_name)

    def format_validation_errors(
        self,
        *,
        errors: list[Any],
        flow_name: str | None = None,
    ) -> str:
        """Format validation errors with card-based layout."""
        if not errors:
            return ""

        lines = ["", self.SEPARATOR]
        lines.extend(self._build_validation_header(flow_name=flow_name, error_count=len(errors)))

        for idx, error in enumerate(errors, start=1):
            lines.extend(self._format_error_card(error=error, error_number=idx))

        lines.append(self.SEPARATOR)
        lines.append("")

        return "\n".join(lines)

    def format_docpipe_exception(self, *, exception: Exception) -> str:
        """Format any DocpipeException with user-friendly display."""
        if isinstance(exception, FlowValidationException):
            return self.format_validation_exception(exception=exception)

        lines = ["", self.SEPARATOR]
        lines.extend(self._build_exception_header(exception=exception))
        lines.extend(self._build_message_block(message=str(exception), indent=" "))

        if isinstance(exception, DocpipeException):
            context_lines = self._extract_exception_context(exception=exception)
            if context_lines:
                lines.extend(context_lines)
                lines.append("")

        lines.append(self.SEPARATOR)
        lines.append("")

        return "\n".join(lines)

    def format_generic_exception(self, *, exception: Exception) -> str:
        """Format a generic exception with card-based display."""
        lines = ["", self.SEPARATOR, " EXECUTION ERROR", self.SEPARATOR, ""]
        lines.append(f" ERROR: {exception.__class__.__name__}")
        lines.append(f" {self.CARD_SEPARATOR}")
        lines.extend(self._build_message_block(message=str(exception), indent=" "))
        lines.append(" Suggestion:")
        lines.extend(
            self._wrap_text(
                text="Review the error message above and check the flow configuration. "
                "For detailed stack trace, set DS_LOG_LEVEL=DEBUG",
                indent="   ",
            )
        )
        lines.append(f" {self.CARD_SEPARATOR}")
        lines.append("")
        lines.append(self.SEPARATOR)
        lines.append("")

        return "\n".join(lines)

    def _build_validation_header(self, *, flow_name: str | None, error_count: int) -> list[str]:
        """Build the validation error header block."""
        flow_context = f" in flow '{flow_name}'" if flow_name else ""
        error_label = "error" if error_count == 1 else "errors"
        return [
            " FLOW VALIDATION FAILED",
            self.SEPARATOR,
            f" Found {error_count} validation {error_label}{flow_context}",
            "",
        ]

    def _build_exception_header(self, *, exception: Exception) -> list[str]:
        """Build the header block for a non-validation exception."""
        exception_name = exception.__class__.__name__.replace("Exception", "").replace("Error", "")
        formatted_name = re.sub(r"(?<!^)(?=[A-Z])", " ", exception_name).strip() or "ERROR"
        return [f" {formatted_name.upper()}", self.SEPARATOR]

    def _extract_exception_context(self, *, exception: Exception) -> list[str]:
        """Extract contextual information from DocpipeException attributes."""
        context = {
            field_name: value
            for field_name, value in vars(exception).items()
            if field_name not in {"args"} and not field_name.startswith("_") and self._has_display_value(value)
        }
        return self._build_details_block(details=context)

    def _format_error_card(self, *, error: Any, error_number: int) -> list[str]:
        """Format a single error as a simple card."""
        raw = self._to_error_dict(error=error)
        operator = str(raw.get("operator") or raw.get("node_name") or "Unknown operator")
        message = str(raw.get("message") or "No error message provided")
        suggestion = raw.get("suggestion")
        details = {
            field: value
            for field, value in raw.items()
            if field not in self.STANDARD_ERROR_FIELDS and field != "suggestion" and self._has_display_value(value)
        }

        lines = [
            f" ERROR {error_number}: {operator} operator",
            f" {self.CARD_SEPARATOR}",
        ]
        lines.extend(self._build_message_block(message=message, indent=" "))
        lines.extend(self._build_details_block(details=details))

        if suggestion:
            lines.append(" Suggestion:")
            lines.extend(self._wrap_text(text=str(suggestion), indent="   "))
            lines.append("")

        lines.append(f" {self.CARD_SEPARATOR}")
        lines.append("")

        return lines

    def _to_error_dict(self, *, error: Any) -> dict[str, Any]:
        """Convert supported error inputs into a plain dictionary."""
        if isinstance(error, ValidationAlert):
            return error.to_dict()
        if isinstance(error, ValidationMessage):
            return error.model_dump()
        if isinstance(error, dict):
            return dict(error)
        return {"message": str(error)}

    def _build_details_block(self, *, details: dict[str, Any]) -> list[str]:
        """Render extra error fields under a single Details section."""
        if not details:
            return []

        lines = ["", " Details:"]
        for field_name, value in details.items():
            lines.extend(self._render_detail_field(field_name=field_name, value=value))
        lines.append("")

        return lines

    def _render_detail_field(self, *, field_name: str, value: Any) -> list[str]:
        """Render a single detail field."""
        label = self._humanize_field_name(field_name)

        if isinstance(value, dict):
            lines = [f"   {label}:"]
            for key, nested_value in value.items():
                lines.extend(
                    self._render_detail_field(
                        field_name=str(key),
                        value=nested_value,
                    )
                )
            return lines

        if isinstance(value, (list, tuple, set)):
            rendered_value = ", ".join(str(item) for item in value)
        else:
            rendered_value = str(value)

        return self._wrap_text(text=rendered_value, indent=f"   {label}: ")

    def _build_message_block(self, *, message: str, indent: str) -> list[str]:
        """Build a wrapped message block while preserving explicit line breaks."""
        if not message:
            return [indent, ""]

        lines: list[str] = []
        for paragraph in message.splitlines():
            if paragraph.strip():
                lines.extend(self._wrap_text(text=paragraph, indent=indent))
            else:
                lines.append(indent)
        lines.append("")

        return lines

    def _wrap_text(self, *, text: str, indent: str = "", max_width: int | None = None) -> list[str]:
        """Wrap text to fit within max width, preserving indentation."""
        if max_width is None:
            max_width = self.WIDTH

        if not text:
            return [indent]

        available_width = max(1, max_width - len(indent))
        wrapped = textwrap.wrap(
            text,
            width=available_width,
            initial_indent=indent,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
            replace_whitespace=False,
            drop_whitespace=True,
        )

        return wrapped or [indent]

    def _humanize_field_name(self, field_name: str) -> str:
        """Convert a field name into a user-friendly label."""
        return field_name.replace("_", " ").strip().title()

    def _has_display_value(self, value: Any) -> bool:
        """Return whether a value should be displayed in formatted output."""
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True


_error_formatter = ErrorFormatter()


def format_validation_exception(*, exception: FlowValidationException, flow_name: str | None = None) -> str:
    """Format a FlowValidationException for display."""
    return _error_formatter.format_validation_exception(exception=exception, flow_name=flow_name)


def format_docpipe_exception(*, exception: Exception) -> str:
    """Format any DocpipeException for display."""
    return _error_formatter.format_docpipe_exception(exception=exception)


def format_generic_exception(*, exception: Exception) -> str:
    """Format a generic (non-Docpipe) exception with card-based display."""
    return _error_formatter.format_generic_exception(exception=exception)
