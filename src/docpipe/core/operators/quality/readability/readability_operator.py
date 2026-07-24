"""Readability operator implementation using pyphen-based metrics."""

from typing import Any

import pyarrow as pa

from docpipe.core.constants.constants import (
    AttributeDataTypes,
    DocpipeConstants,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.core.operators.quality.readability.readability_metrics import ReadabilityMetrics
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

DEFAULT_READABILITY_SCORES = [
    OperatorConstants.Columns.FLESCH_READING_EASE,
    OperatorConstants.Columns.FLESCH_KINCAID_GRADE,
    OperatorConstants.Columns.GUNNING_FOG,
    OperatorConstants.Columns.SMOG_INDEX,
    OperatorConstants.Columns.COLEMAN_LIAU_INDEX,
    OperatorConstants.Columns.AUTOMATED_READABILITY_INDEX,
    OperatorConstants.Columns.DALE_CHALL_READABILITY_SCORE,
    OperatorConstants.Columns.DIFFICULT_WORDS,
    OperatorConstants.Columns.LINSEAR_WRITE_FORMULA,
    OperatorConstants.Columns.TEXT_STANDARD,
    OperatorConstants.Columns.SPACHE_READABILITY,
    OperatorConstants.Columns.MCALPINE_EFLAW,
    OperatorConstants.Columns.READING_TIME,
]

SCORE_LIST_PARAM = "readability_score_list"


class ReadabilityOperator(AbstractOperator):
    """
    Transform class that implements readability scores for each document based on its content.
    Uses custom pyphen-based implementation for accurate syllable counting.
    """

    short_name: str = "readability"
    category: OperatorCategory = OperatorCategory.Quality
    owner: str | None = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config=config)
        self.contents_column_name: str = config.get(
            OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        )
        self.score_list: list[str] = config.get(SCORE_LIST_PARAM, DEFAULT_READABILITY_SCORES)
        if isinstance(self.score_list, str):
            self.score_list = [self.score_list]
        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }
        self.metrics_calculator = ReadabilityMetrics()

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: ReadabilityOperator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: ReadabilityOperator.is_available(),
            OperatorConstants.Misc.LABEL: "Readability Operator",
            OperatorConstants.Config.DESCRIPTION: "Compute readability scores for document content (Flesch-Kincaid, Gunning Fog, SMOG, and more).",
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.Columns.FLESCH_READING_EASE: {
                    OperatorConstants.Misc.NAME: "Flesch Reading Ease",
                    OperatorConstants.Config.DESCRIPTION: "Rates text on a 0-100 scale where higher scores mean easier reading.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.FLESCH_KINCAID_GRADE: {
                    OperatorConstants.Misc.NAME: "Flesch Kincaid Grade",
                    OperatorConstants.Config.DESCRIPTION: "Estimates the U.S. school grade level needed to understand the text.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.GUNNING_FOG: {
                    OperatorConstants.Misc.NAME: "Gunning Fog",
                    OperatorConstants.Config.DESCRIPTION: "Estimates the grade level needed based on long sentences and difficult words.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.SMOG_INDEX: {
                    OperatorConstants.Misc.NAME: "Smog Index",
                    OperatorConstants.Config.DESCRIPTION: "Shows the grade level needed, based mainly on how many hard words the text has.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.COLEMAN_LIAU_INDEX: {
                    OperatorConstants.Misc.NAME: "Coleman Liau Index",
                    OperatorConstants.Config.DESCRIPTION: "Estimates reading grade level using letter counts instead of syllables.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.AUTOMATED_READABILITY_INDEX: {
                    OperatorConstants.Misc.NAME: "Automated Readability Index",
                    OperatorConstants.Config.DESCRIPTION: "Gives the school grade level needed using characters per word and words per sentence.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.DALE_CHALL_READABILITY_SCORE: {
                    OperatorConstants.Misc.NAME: "Dale Chall Readability Score",
                    OperatorConstants.Config.DESCRIPTION: "Estimates the grade level by checking how many uncommon words are used.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.DIFFICULT_WORDS: {
                    OperatorConstants.Misc.NAME: "Difficult Words",
                    OperatorConstants.Config.DESCRIPTION: "Returns the count of words that are not commonly used, which make the text harder for readers.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.LINSEAR_WRITE_FORMULA: {
                    OperatorConstants.Misc.NAME: "Linsear Write Formula",
                    OperatorConstants.Config.DESCRIPTION: "Computes grade level based on easy vs. hard words and sentence length.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.TEXT_STANDARD: {
                    OperatorConstants.Misc.NAME: "Text Standard",
                    OperatorConstants.Config.DESCRIPTION: "Provides an overall grade-level estimate by combining multiple readability formulas.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.SPACHE_READABILITY: {
                    OperatorConstants.Misc.NAME: "Spache Readability",
                    OperatorConstants.Config.DESCRIPTION: "Estimates reading grade level for texts aimed at young children up to 4th grade.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.MCALPINE_EFLAW: {
                    OperatorConstants.Misc.NAME: "Mcalpine Eflaw",
                    OperatorConstants.Config.DESCRIPTION: "Rates readability for learners of English, focusing on short 'miniwords' and sentence length.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                OperatorConstants.Columns.READING_TIME: {
                    OperatorConstants.Misc.NAME: "Reading Time",
                    OperatorConstants.Config.DESCRIPTION: "The reading time of the given text. Assumes 14.69ms per character.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                SCORE_LIST_PARAM: {
                    OperatorConstants.Misc.NAME: "Readability Scores",
                    OperatorConstants.Config.DESCRIPTION: "Select which readability scores to compute for your documents.",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: DEFAULT_READABILITY_SCORES,
                    OperatorConstants.Config.VALID_VALUES: DEFAULT_READABILITY_SCORES,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                }
            },
        }

    @staticmethod
    def get_static_required_features() -> list[str]:
        return [OperatorConstants.Columns.DOC_COLUMN_DEFAULT]

    @staticmethod
    def get_required_features() -> list[str]:
        return [OperatorConstants.Columns.DOC_COLUMN_DEFAULT]

    def _calculate_scores_for_text(self, *, text: str) -> dict[str, float]:
        if not text:
            return dict.fromkeys(self.score_list, 0.0)
        stats = self.metrics_calculator.text_stats(text=text)
        scores = {}
        for score in self.score_list:
            method = getattr(self.metrics_calculator, score)
            scores[score] = method(stats=stats)
        return scores

    def _process_all_rows(self, *, content_column: pa.Array) -> dict[str, list[float]]:
        score_columns: dict[str, list[float]] = {score: [] for score in self.score_list}
        content_list = content_column.to_pylist()
        for text in content_list:
            text = text if text is not None else ""
            scores = self._calculate_scores_for_text(text=text)
            for score in self.score_list:
                score_columns[score].append(scores[score])
        return score_columns

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """Transform function for readability scores - calculates only requested metrics"""
        if self.contents_column_name not in table.column_names:
            raise ValueError(f"Content column '{self.contents_column_name}' not found in table")
        content_column = table.column(self.contents_column_name)
        score_columns = self._process_all_rows(content_column=content_column)
        new_columns = []
        new_fields = []
        for score in self.score_list:
            new_columns.append(pa.array(score_columns[score], type=pa.float64()))
            new_fields.append(pa.field(score, pa.float64()))
        transformed_table = table.append_column(new_fields[0], new_columns[0])
        for i in range(1, len(new_fields)):
            transformed_table = transformed_table.append_column(new_fields[i], new_columns[i])
        metadata = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=table))
        metadata[Metrics.External.PROCESSED_DOCS] = table.num_rows
        return [transformed_table], metadata

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
        if not self.score_list:
            warnings.append("At least one readability score must be selected")
        elif not set(self.score_list).issubset(set(DEFAULT_READABILITY_SCORES)):
            warnings.append("Invalid readability scores provided.")
