from typing import Any

import pyarrow as pa
from dpk_readability.common import (
    contents_column_name_cli_param,
    score_list_cli_param,
    score_list_default,
    short_name,
)
from dpk_readability.transform import ReadabilityTransform

from datasift.core.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    Metrics,
)
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from datasift.core.operators.operator_utils import OperatorUtils
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger()

FLESCH_EASE: str = "flesch_ease"
FLESCH_KINCAID: str = "flesch_kincaid"
GUNNING_FOG: str = "gunning_fog"
SMOG_INDEX: str = "smog_index"
COLEMAN_LIAU_INDEX: str = "coleman_liau_index"
AUTOMATED_READABILITY_INDEX: str = "automated_readability_index"
DALE_CHALL_READABILITY_SCORE: str = "dale_chall_readability_score"
DIFFICULT_WORDS: str = "difficult_words"
LINSEAR_WRITE_FORMULA: str = "linsear_write_formula"
TEXT_STANDARD: str = "text_standard"
SPACHE_READABILITY: str = "spache_readability"
MCALPINE_EFLAW: str = "mcalpine_eflaw"
READING_TIME: str = "reading_time"

DEFAULT_READABILITY_SCORES: list[str] = [
    FLESCH_EASE,
    FLESCH_KINCAID,
    GUNNING_FOG,
    SMOG_INDEX,
    COLEMAN_LIAU_INDEX,
    AUTOMATED_READABILITY_INDEX,
    DALE_CHALL_READABILITY_SCORE,
    DIFFICULT_WORDS,
    LINSEAR_WRITE_FORMULA,
    TEXT_STANDARD,
    SPACHE_READABILITY,
    MCALPINE_EFLAW,
    READING_TIME,
]


class ReadabilityOperator(ReadabilityTransform, AbstractOperator):
    """
    Transform class that implements readability scores for each document based on its content
    """

    short_name: str = short_name
    category: OperatorCategory = OperatorCategory.Quality
    owner = DatasiftConstants.OWNER_DATASIFT

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config=config)
        self.contents_column_name: str = config.get(
            contents_column_name_cli_param, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        )
        self.score_list: list[str] = config.get(score_list_cli_param, score_list_default)
        if isinstance(self.score_list, str):
            self.score_list = [self.score_list]
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: ReadabilityOperator.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: ReadabilityOperator.is_available(),
            OperatorConstants.Misc.LABEL: "Readability Operator",
            OperatorConstants.Config.FEATURES: {
                FLESCH_EASE: {
                    OperatorConstants.Misc.NAME: "Flesch Reading Ease",
                    OperatorConstants.Config.DESCRIPTION: "Rates text on a 0 to 100 scale where higher scores mean easier reading.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                FLESCH_KINCAID: {
                    OperatorConstants.Misc.NAME: "Flesch Kincaid Grade",
                    OperatorConstants.Config.DESCRIPTION: "Estimates the U.S. school grade level needed to understand the text.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                GUNNING_FOG: {
                    OperatorConstants.Misc.NAME: "Gunning Fog",
                    OperatorConstants.Config.DESCRIPTION: "Estimates the grade level needed based on long sentences and difficult words.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                SMOG_INDEX: {
                    OperatorConstants.Misc.NAME: "Smog Index",
                    OperatorConstants.Config.DESCRIPTION: "Shows the grade level needed, based mainly on how many hard words the text has.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                COLEMAN_LIAU_INDEX: {
                    OperatorConstants.Misc.NAME: "Coleman Liau Index",
                    OperatorConstants.Config.DESCRIPTION: "Estimates reading grade level using letter counts instead of syllables.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                AUTOMATED_READABILITY_INDEX: {
                    OperatorConstants.Misc.NAME: "Automated Readability Index",
                    OperatorConstants.Config.DESCRIPTION: "Gives the school grade level needed using characters per word and words per sentence.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                DALE_CHALL_READABILITY_SCORE: {
                    OperatorConstants.Misc.NAME: "Dale Chall Readability Score",
                    OperatorConstants.Config.DESCRIPTION: "Estimates the grade level by checking how many uncommon words are used.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                DIFFICULT_WORDS: {
                    OperatorConstants.Misc.NAME: "Difficult Words",
                    OperatorConstants.Config.DESCRIPTION: "Returns the count of words that are not commonly used, which make the text harder for readers.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                LINSEAR_WRITE_FORMULA: {
                    OperatorConstants.Misc.NAME: "Linsear Write Formula",
                    OperatorConstants.Config.DESCRIPTION: "Computes grade level based on easy vs. hard words and sentence length.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                TEXT_STANDARD: {
                    OperatorConstants.Misc.NAME: "Text Standard",
                    OperatorConstants.Config.DESCRIPTION: "Provides an overall grade-level estimate by combining multiple readability formulas.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                SPACHE_READABILITY: {
                    OperatorConstants.Misc.NAME: "Spache Readability",
                    OperatorConstants.Config.DESCRIPTION: "Estimates reading grade level for texts aimed at young children up to 4th grade.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                MCALPINE_EFLAW: {
                    OperatorConstants.Misc.NAME: "Mcalpine Eflaw",
                    OperatorConstants.Config.DESCRIPTION: "Rates readability for learners of English, focusing on short 'miniwords' and sentence length.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                READING_TIME: {
                    OperatorConstants.Misc.NAME: "Reading Time",
                    OperatorConstants.Config.DESCRIPTION: "The reading time of the given text. Assumes 14.69ms per character.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                "readability_score_list": {
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

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """Transform function for readability scores"""
        self.score_list = [s if s.endswith("_textstat") else f"{s}_textstat" for s in self.score_list]
        transformed_table: pa.Table = super().transform(table=table)[0][0]

        # Casting large_string returned by the dpk_readability transform to string for Python runtime compatibility
        for i, field in enumerate(transformed_table.schema):
            if pa.types.is_large_string(field.type):
                column: pa.ChunkedArray = transformed_table.column(i)
                casted_column: pa.ChunkedArray = column.cast(pa.string())
                transformed_table = transformed_table.set_column(i, field.name, casted_column)
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=OperatorUtils.find_doc_count(table=table))
        metadata[Metrics.External.PROCESSED_DOCS] = table.num_rows
        return [transformed_table], metadata

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
        if not self.score_list:
            warnings.append("At least one readability score must be selected")
        elif not set(self.score_list).issubset(set(DEFAULT_READABILITY_SCORES)):
            warnings.append("Invalid readability scores provided.")
