from typing import Any
import pyarrow as pa
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from common.util.operator_utils import find_doc_count
from common.util.log import get_logger
from common.util.constants import OperatorConstants, Metrics, AttributeDataTypes, DatasiftConstants
from dpk_readability.transform import ReadabilityTransform
from dpk_readability.common import contents_column_name_cli_param, short_name, score_list_cli_param, score_list_default

logger = get_logger()

FLESCH_EASE = "flesch_ease"
FLESCH_KINCAID = "flesch_kincaid"
GUNNING_FOG = "gunning_fog"
SMOG_INDEX = "smog_index"
COLEMAN_LIAU_INDEX = "coleman_liau_index"
AUTOMATED_READABILITY_INDEX = "automated_readability_index"
DALE_CHALL_READABILITY_SCORE = "dale_chall_readability_score"
DIFFICULT_WORDS = "difficult_words"
LINSEAR_WRITE_FORMULA = "linsear_write_formula"
TEXT_STANDARD = "text_standard"
SPACHE_READABILITY = "spache_readability"
MCALPINE_EFLAW = "mcalpine_eflaw"
READING_TIME = "reading_time"

DEFAULT_READABILITY_SCORES = [
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
    READING_TIME
]

class ReadabilityOperator(ReadabilityTransform, AbstractOperator):
    """
    Transform class that implements readability scores for each document based on its content
    """
    short_name = short_name
    category = OperatorCategory.Quality

    def __init__(self, config: dict):
        super().__init__(config=config)
        self.contents_column_name = config.get(contents_column_name_cli_param, OperatorConstants.DOC_COLUMN_DEFAULT)
        self.score_list = config.get(score_list_cli_param, score_list_default)
        if isinstance(self.score_list, str):
            self.score_list = [self.score_list]
        self.common_log_arguments = {DatasiftConstants.JOB_ID: self.job_id,
                                     DatasiftConstants.JOB_RUN_ID: self.job_run_id}

    def get_metadata(self):
        return {
            OperatorConstants.SDK: True,
            OperatorConstants.CATEGORY: ReadabilityOperator.category.value,
            OperatorConstants.IS_OPERATOR_AVAILABLE: ReadabilityOperator.is_available(),
            OperatorConstants.LABEL: "Readability Operator",
            OperatorConstants.FEATURES: {
                FLESCH_EASE: {
                    OperatorConstants.NAME: "Flesch Reading Ease",
                    OperatorConstants.DESCRIPTION: "Rates text on a 0–100 scale where higher scores mean easier reading.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                FLESCH_KINCAID: {
                    OperatorConstants.NAME: "Flesch Kincaid Grade",
                    OperatorConstants.DESCRIPTION: "Estimates the U.S. school grade level needed to understand the text.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                GUNNING_FOG: {
                    OperatorConstants.NAME: "Gunning Fog",
                    OperatorConstants.DESCRIPTION: "Estimates the grade level needed based on long sentences and difficult words.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                SMOG_INDEX: {
                    OperatorConstants.NAME: "Smog Index",
                    OperatorConstants.DESCRIPTION: "Shows the grade level needed, based mainly on how many hard words the text has.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                COLEMAN_LIAU_INDEX: {
                    OperatorConstants.NAME: "Coleman Liau Index",
                    OperatorConstants.DESCRIPTION: "Estimates reading grade level using letter counts instead of syllables.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                AUTOMATED_READABILITY_INDEX: {
                    OperatorConstants.NAME: "Automated Readability Index",
                    OperatorConstants.DESCRIPTION: "Gives the school grade level needed using characters per word and words per sentence.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                DALE_CHALL_READABILITY_SCORE: {
                    OperatorConstants.NAME: "Dale Chall Readability Score",
                    OperatorConstants.DESCRIPTION: "Estimates the grade level by checking how many uncommon words are used.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                DIFFICULT_WORDS: {
                    OperatorConstants.NAME: "Difficult Words",
                    OperatorConstants.DESCRIPTION: "Returns the count of words that are not commonly used, which make the text harder for readers.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                LINSEAR_WRITE_FORMULA: {
                    OperatorConstants.NAME: "Linsear Write Formula",
                    OperatorConstants.DESCRIPTION: "Computes grade level based on easy vs. hard words and sentence length.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                TEXT_STANDARD: {
                    OperatorConstants.NAME: "Text Standard",
                    OperatorConstants.DESCRIPTION: "Provides an overall grade-level estimate by combining multiple readability formulas.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                SPACHE_READABILITY: {
                    OperatorConstants.NAME: "Spache Readability",
                    OperatorConstants.DESCRIPTION: "Estimates reading grade level for texts aimed at young children up to 4th grade.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                MCALPINE_EFLAW: {
                    OperatorConstants.NAME: "Mcalpine Eflaw",
                    OperatorConstants.DESCRIPTION: "Rates readability for learners of English, focusing on short 'miniwords' and sentence length.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                },
                READING_TIME: {
                    OperatorConstants.NAME: "Reading Time",
                    OperatorConstants.DESCRIPTION: "The reading time of the given text. Assumes 14.69ms per character.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: AttributeDataTypes.DOUBLE
                }
            },
            OperatorConstants.ATTRIBUTES: {
                "readability_score_list": {
                    OperatorConstants.NAME: "Readability Scores",
                    OperatorConstants.DESCRIPTION: "Select which readability scores to compute for your documents.",
                    OperatorConstants.REQUIRED: True,
                    OperatorConstants.DEFAULT: DEFAULT_READABILITY_SCORES,
                    OperatorConstants.VALID_VALUES: DEFAULT_READABILITY_SCORES,
                    OperatorConstants.TYPE: AttributeDataTypes.LIST,
                }
            }
        }

    @staticmethod
    def get_static_required_features():
        return [OperatorConstants.DOC_COLUMN_DEFAULT]

    def get_required_features(self):
        return [self.contents_column_name]

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """Transform function for readability scores"""
        self.score_list = [s if s.endswith("_textstat") else f"{s}_textstat" for s in self.score_list]
        transformed_table = super().transform(table=table)[0][0]

        # Casting large_string returned by the dpk_readability transform to string for Python runtime compatibility
        for i, field in enumerate(transformed_table.schema):
            if pa.types.is_large_string(field.type):
                column = transformed_table.column(i)
                casted_column = column.cast(pa.string())
                transformed_table = transformed_table.set_column(i, field.name, casted_column)
        metadata = self.create_base_metadata(total_docs_count=find_doc_count(table=table))
        metadata[Metrics.External.PROCESSED_DOCS] = table.num_rows
        return [transformed_table], metadata

    def validate(self, errors: list, warnings: list, available_features: list):
        if not self.score_list:
            warnings.append("At least one readability score must be selected")
        elif not set(self.score_list).issubset(set(DEFAULT_READABILITY_SCORES)):
            warnings.append("Invalid readability scores provided.")


# Used for unit testing only
def main():  # pragma: no cover
    config = {
        "readability_contents_column_name": "content",
        "readability_score_list": DEFAULT_READABILITY_SCORES
    }
    operator = ReadabilityOperator(config=config)
    print(operator)

    content = pa.array([
        "The cat sat on the mat. It was a sunny day.",
        "Python is a high-level programming language used for web development.",
        "The implementation of sophisticated algorithms necessitates comprehensive understanding."
    ])
    col_names = ["content"]
    input_table = pa.Table.from_arrays([content], names=col_names)

    table_list, metadata = operator.transform(table=input_table)

    print(">>> completed the operator", operator)
    table = table_list[0]
    print(f"total scores added: {table.num_columns}")
    print(f"\noutput table: {table} {metadata} {table.column_names}")

if __name__ == '__main__':  # pragma: no cover
    main()