import os
from typing import Any

import pyarrow as pa
from dpk_doc_quality.transform import DocQualityTransform

from common.constants.constants import AttributeDataTypes, Metrics
from common.constants.operator_constants import OperatorConstants
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.operator_utils import OperatorUtils

logger = get_logger()
DOC_CONTENT_COLUMN_KEY: str = "doc_content_column"
TEXT_LANG_KEY: str = "text_lang"
DEFAULT_TEXT_LANG: str = "en"
BAD_WORD_FILEPATH_KEY: str = "bad_word_filepath"
BASE_PATH: str = os.path.dirname(__file__)
BAD_WORD_FILEPATH_VALUE: str = os.path.join(BASE_PATH, "en")
if os.getenv("RUNTIME") == "CLOUD" and os.getenv("IS_SPARK_RUNTIME"):
    BAD_WORD_FILEPATH_VALUE = BAD_WORD_FILEPATH_VALUE.replace(
        "/datasift_core.zip/datasift_core/operators/language/readability", ""
    )


class DocQuality(DocQualityTransform, AbstractOperator):
    """
    Importing the DocQualityTransform class from dpk_doc_quality_transform_python package
    Refer Link: https://github.com/IBM/data-prep-kit/blob/dev/transforms/language/doc_quality/python/README.md

    Badwordfile is currently stored at same location as source folder.
    """

    short_name: str = OperatorConstants.Operators.DOC_QUALITY
    category: OperatorCategory = OperatorCategory.Quality

    def __init__(self, config: dict[str, Any]) -> None:
        normalized_bad_word_filepath: str = BAD_WORD_FILEPATH_VALUE.replace(
            "./datasift.zip", "/datasift/storage/job-assets"
        )
        config.update({BAD_WORD_FILEPATH_KEY: normalized_bad_word_filepath})
        super().__init__(config)
        self.doc_column_name: str = config.get(
            OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        )
        self.doc_content_column: str = config.get(DOC_CONTENT_COLUMN_KEY, "content")
        self.text_lang: str = config.get(TEXT_LANG_KEY, DEFAULT_TEXT_LANG)
        self.bad_word_filepath: str = config.get(BAD_WORD_FILEPATH_KEY, normalized_bad_word_filepath)

    def get_metadata(self) -> dict[str, Any]:
        return {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Misc.LABEL: "Document Quality",
            OperatorConstants.Config.FEATURES: {
                "docq_total_words": {
                    OperatorConstants.Misc.NAME: "Total Words",
                    OperatorConstants.Config.DESCRIPTION: "The total number of words",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "docq_mean_word_len": {
                    OperatorConstants.Misc.NAME: "Mean word length",
                    OperatorConstants.Config.DESCRIPTION: "The mean of words' lengths",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                "docq_symbol_to_word_ratio": {
                    OperatorConstants.Misc.NAME: "Symbol to Word Ratio",
                    OperatorConstants.Config.DESCRIPTION: "The ratio of symbol-to-word ratio (Reference for symbols like emojis:",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                "docq_sentence_count": {
                    OperatorConstants.Misc.NAME: "Sentence Count",
                    OperatorConstants.Config.DESCRIPTION: "The number of sentences",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "docq_lorem_ipsum_ratio": {
                    OperatorConstants.Misc.NAME: "Lorem Ipsum Ratio",
                    OperatorConstants.Config.DESCRIPTION: """The ratio between the number of occurrences of lorem ipsum over the text length. 
                        Lorem ipsum, or lipsum as it is sometimes known, is dummy text used in laying out print, graphic or web designs.""",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                "docq_contain_bad_word": {
                    OperatorConstants.Misc.NAME: "Bad words present",
                    OperatorConstants.Config.DESCRIPTION: "whether text contains bad words",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                "docq_bullet_point_ratio": {
                    OperatorConstants.Misc.NAME: "Bullet Point Ratio",
                    OperatorConstants.Config.DESCRIPTION: "the ratio of lines starting with a bullet point",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                "docq_curly_bracket_ratio": {
                    OperatorConstants.Misc.NAME: "Curly Bracket Ratio",
                    OperatorConstants.Config.DESCRIPTION: "The ratio between the number of occurrences of { or } over the text length",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                "docq_ellipsis_line_ratio": {
                    OperatorConstants.Misc.NAME: "Ellipsis Line Ratio",
                    OperatorConstants.Config.DESCRIPTION: "the ratio of lines ending with an ellipsis",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                "docq_alphabet_word_ratio": {
                    OperatorConstants.Misc.NAME: "Alphabet to Word Ratio",
                    OperatorConstants.Config.DESCRIPTION: "the ratio of words having at least one alphabetic character",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
                "docq_contain_common_en_words": {
                    OperatorConstants.Misc.NAME: "Common English Words",
                    OperatorConstants.Config.DESCRIPTION: "whether the given text contains common English words like the, and, to, that, of, with, be, and have",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.DOUBLE,
                },
            },
        }

    def get_required_features(self) -> list[str]:
        return [self.doc_column_name]

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Operator-specific logic to convert one input Table to 0 or more output tables.
        Calling the DocQualityTransform() transform() method.
        In this case, the transform() from DocQualityTransform() foe each row in the content column
        generates document statistics and adds a column for each statistic.
        """

        transformed_table: pa.Table = super().transform(table)[0][0]

        total_docs: int = OperatorUtils.find_doc_count(table=table)
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=total_docs)
        metadata[Metrics.External.PROCESSED_DOCS] = total_docs
        metadata[Metrics.External.PROCESSED_ROWS] = transformed_table.num_rows

        return [transformed_table], metadata
