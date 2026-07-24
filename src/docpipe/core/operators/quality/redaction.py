from typing import Any, Pattern

import pyarrow as pa
import re2 as re

from docpipe.core.constants.constants import (
    AttributeDataTypes,
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.utils.infrastructure.logging import get_logger

TARGET_COLUMN_NAME_KEY = "target_column"
TARGET_COLUMN_NAME_DEFAULT = "redacted_content"
STATS_COLUMN_NAME_KEY = "stats_column"
STATS_COLUMN_NAME_DEFAULT = "redaction_stats"
DEFAULT_MASKING_CHARACTER = "*"

logger = get_logger()


class RedactionOperator(AbstractOperator):
    """
    Implements redacting strings that match a given word or regex pattern. The redacted content is
    stored in a new column specified by "target_column". And the count of redactions for that
    row is stored within a column specified by "stats_column".
    """

    short_name = OperatorConstants.Operators.REDACTION
    category = OperatorCategory.Quality
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]):
        """
        Initialize based on the dictionary of configuration information. Accepted parameters:
        - doc_column: Which column contains the text content.
        - stats_column: Number of redactions in that row.
        - masking_character: The character used for masking.
        - regex: The pattern or word to be masked/redacted.
        """
        super().__init__(config)
        self.doc_column = config.get(OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT)
        self.stats_column = config.get(STATS_COLUMN_NAME_KEY, STATS_COLUMN_NAME_DEFAULT)
        self.masking_character = config.get(
            OperatorConstants.PIIHAP.REDACTION_MASKING_CHARACTER_KEY, DEFAULT_MASKING_CHARACTER
        )

        regex = config.get(OperatorConstants.PIIHAP.REDACTION_REGEX_KEY)
        self.raw_regex: str | None = regex if regex and len(regex) else None
        self.pattern_compile_error: str | None = None
        if self.raw_regex:
            try:
                compiled_regex: Pattern[str] = re.compile(self.raw_regex)
            except re.error as e:
                self.pattern_compile_error = str(e)
                compiled_regex = re.compile(re.escape(self.raw_regex))

            self.pattern: Pattern[Any] | None = compiled_regex
        else:
            self.pattern = None

        self.common_log_arguments = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }

    @staticmethod
    def get_metadata():
        operator_metadata = {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: RedactionOperator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: RedactionOperator.is_available(),
            OperatorConstants.Misc.LABEL: "Redaction",
            OperatorConstants.Config.DESCRIPTION: "Redact text matching a regex pattern from document content and report the number of redactions made.",
            OperatorConstants.Config.FEATURES: {
                STATS_COLUMN_NAME_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Redaction Count",
                    OperatorConstants.Config.DESCRIPTION: "Number of matches found and redacted from the document",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                }
            },
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.PIIHAP.REDACTION_REGEX_KEY: {
                    OperatorConstants.Misc.NAME: "Redaction key",
                    OperatorConstants.Config.DESCRIPTION: "The pattern or word to be masked/redacted.",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.PIIHAP.REDACTION_MASKING_CHARACTER_KEY: {
                    OperatorConstants.Misc.NAME: "Masking Character",
                    OperatorConstants.Config.DESCRIPTION: "Single length masking character chosen by user.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: DEFAULT_MASKING_CHARACTER,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
            },
        }

        return operator_metadata

    def validate(self, errors: list, warnings: list, available_features: list):
        super().validate(errors, warnings, available_features)

        if self.should_validate_field(field_value=self.raw_regex):
            if not self.raw_regex:
                warnings.append("Redaction pattern is empty. Operator will perform no action.")
                return
            if self.pattern_compile_error:
                errors.append(
                    f"Invalid or unsupported regex pattern: {self.pattern_compile_error}. "
                    "Verify the pattern is valid and does not use unsupported constructs such as lookaheads or backreferences."
                )

    def redact(self, matches: list, content: str):
        """
        Redact the given content by replacing the matches with the masking pattern.
        """
        if not matches:
            return content

        pattern = re.compile(r"(?i)" + r"|".join(map(re.escape, matches)))

        return pattern.sub(lambda m: self.masking_character * len(m.group()), content)

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Operator-specific logic to convert one input Table to 0 or more output tables.
        In this case, run the regex matcher against the "content" column, identify the matches,
        and add the results as a JSON array into the "patterns" column. Both input and output
        column names are configurable using the "config" dictionary.
        """

        logger.info("Running transform function.", extra=self.common_log_arguments)
        # Initialize metadata
        metadata = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=table))
        metadata["total_redactions"] = 0

        if self.pattern is None:
            logger.warning(
                "No word or regex pattern provided for redaction, skipping redaction",
                extra=self.common_log_arguments,
            )
            metadata[Metrics.External.PROCESSED_DOCS] = OperatorUtils.find_doc_count(table=table)
            current_status = metadata[Metrics.External.NODE_STATUS]
            metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
                current_status if isinstance(current_status, ExecutionStatus) else ExecutionStatus(current_status),
                ExecutionStatus.COMPLETED_WITH_WARNINGS,
            ).value
            return [table], metadata
        OperatorUtils.validate_columns(table=table, required=[self.doc_column], operator_name=self.short_name)

        logger.info(
            f"Redaction pattern/word: {self.pattern.pattern if self.pattern else None}, Masking Character: {self.masking_character or None}",
            extra=self.common_log_arguments,
        )
        docs = table[self.doc_column]
        redacted_rows = 0
        total_redactions = 0
        redaction_status = [0] * table.num_rows
        updated_content_column = table[self.doc_column].to_pandas().to_list()
        for n in range(table.num_rows):
            content = docs[n].as_py()
            matches = self.pattern.findall(content)
            redacted_content = self.redact(matches, content)
            updated_content_column[n] = redacted_content
            logger.info(
                f"Redaction completed for doc {table['name'][n]}",
                extra=self.common_log_arguments,
            )
            if len(matches) > 0:
                redacted_rows += 1
                total_redactions += len(matches)
                redaction_status[n] = len(matches)

        # Drop the old column and add the updated content
        table = table.drop(self.doc_column)
        table = table.append_column(self.doc_column, pa.array(updated_content_column))
        table = table.append_column(self.stats_column, pa.array(redaction_status))

        metadata[Metrics.External.PROCESSED_DOCS] = redacted_rows
        metadata["total_redactions"] = total_redactions

        return [table], metadata

    @staticmethod
    def get_required_features() -> list[str]:
        return [OperatorConstants.Columns.DOC_COLUMN_DEFAULT]
