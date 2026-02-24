from langdetect import detect_langs
from typing import Any
import pyarrow as pa

from data_processing.utils.transform_utils import TransformUtils
from datasift_opensource.backend.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from datasift_opensource.backend.core.operators.operator_utils import OperatorUtils
from datasift_opensource.backend.common.util.constants import OperatorConstants, Metrics, DatasiftConstants, ExecutionStatus, AttributeDataTypes
from datasift_opensource.backend.common.util.log import get_logger
from datasift_opensource.backend.common.util.operator_utils import find_doc_count, remove_rows

logger = get_logger()


class LanguageDetect(AbstractOperator):
    """
    Detects langauge and score.
    """
    short_name = OperatorConstants.LANG_DETECT
    category = OperatorCategory.Quality

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.doc_column_name = config.get(OperatorConstants.DOC_COLUMN, OperatorConstants.DOC_COLUMN_DEFAULT)
        self.common_log_arguments = {DatasiftConstants.JOB_ID: self.job_id, DatasiftConstants.JOB_RUN_ID: self.job_run_id}
        self.filter_value = config.get(OperatorConstants.FILTER_UNKNOWN_LANGUAGE, False)

    def get_metadata(self):
        operator_metadata = {
            OperatorConstants.SDK: True,
            OperatorConstants.CATEGORY: self.category.value,
            OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.LABEL: "Language Annotator",
            OperatorConstants.ATTRIBUTES:{
                OperatorConstants.FILTER_UNKNOWN_LANGUAGE : {
                    OperatorConstants.NAME: "Filter Unknown Language document",
                    OperatorConstants.DESCRIPTION: "Filters out all documents that have no language detected",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: False,
                    OperatorConstants.TYPE: AttributeDataTypes.BOOLEAN}
            },
            OperatorConstants.FEATURES : {
                OperatorConstants.LANGUAGE_NAME_COLUMN_KEY: {
                    OperatorConstants.NAME: "Language Name",
                    OperatorConstants.DESCRIPTION: "This stores the language of the document",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING
                },
                OperatorConstants.LANGUAGE_SCORE_COLUMN_KEY:{
                    OperatorConstants.NAME: "Language score",
                    OperatorConstants.DESCRIPTION: "Probability score of the language",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.TYPE: OperatorConstants.TYPE_FLOAT
                }
            }
        }

        return operator_metadata

    def get_required_features(self):
        return [self.doc_column_name]

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Detects all the available language and their respective score in the document
        """

        OperatorUtils.validate_columns(table=table, required=[self.doc_column_name], operator_name=self.short_name)

        metadata = self.create_base_metadata(total_docs_count=find_doc_count(table=table))

        new_doc_content = table[self.doc_column_name].to_pylist()
        language_name_column = []
        language_score_column = []
        remove_row_idx = []
        message = ""

        for idx, doc_content in enumerate(new_doc_content):
            file_name = table[OperatorConstants.NAME].to_pandas().to_list()
            try:
                language = detect_langs(doc_content)
                language_name, language_score = str(language[0]).split(":")
                language_name_column.append(language_name)
                language_score_column.append(float(language_score))
            except Exception as e:
                if self.filter_value:
                    logger.error(f"Used defined error for document {file_name}: {e}", extra=self.common_log_arguments)
                    remove_row_idx.append(idx)
                    self.record_failed_document(metadata=metadata, doc_id=table[OperatorConstants.ID][idx].as_py(),
                                                doc_name=file_name,
                                                reason=f"Filter out based on user selection with error: {getattr(e, 'message', str(e)) if getattr(e, 'message', str(e)) else getattr(e, 'message', repr(e))}")
                    metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED_WITH_ERRORS.value
                    if not message:
                        message = "Documents with no language detected are removed from the flow"
                else:
                    language_name = "UNKNOWN"
                    language_score = 0.0
                    metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED_WITH_WARNINGS.value
                    logger.warning(f"Exception for document {file_name}: {e}", extra=self.common_log_arguments)
                    language_name_column.append(language_name)
                    language_score_column.append(float(language_score))
                    if not message:
                        message = "Documents with no language detected are marked as UNKNOWN"

        table = remove_rows(table=table, remove_row_idx=remove_row_idx)

        table = TransformUtils.add_column(table=table, name=OperatorConstants.LANGUAGE_NAME_COLUMN_KEY, content=language_name_column)
        table = TransformUtils.add_column(table=table, name=OperatorConstants.LANGUAGE_SCORE_COLUMN_KEY,content=language_score_column)
        logger.info("Completed Language detect transform function", extra=self.common_log_arguments)

        metadata[Metrics.External.PROCESSED_DOCS] = metadata[Metrics.External.TOTAL_DOCS] - metadata[Metrics.External.FAILED_DOCS_COUNT]
        metadata[Metrics.External.PROCESSED_ROWS] = table.num_rows
        
        if message:
            metadata[Metrics.External.PROCESSING_MESSAGE] = message

        return [table], metadata


# Used for unit testing only
def main():
    # 1. Construct the operator with the required configuration and input parameters
    operator = LanguageDetect({
        "doc_column": "content",
        OperatorConstants.FILTER_UNKNOWN_LANGUAGE: False
    })
    print(operator)

    # 2. Create an in-memory py-arrow table, as the input

    content = pa.array([
        "Contact support team via email: support@ibm.com, or the sales team sales@in.ibm.com, Content Phone Number: 08012345678 ",
        "My personal email id is jj@acm.org, PhoneNumber is: +91 932-123-1234 and +91 9321231234, Amex Card Number: 378734493671000",
        "",
        "8967840594",
        "Hello, world! Bonjour, monde! ¡Hola, mundo!"
    ])
    name = pa.array(["name1", "name2","name3", "name4", "name5"])
    doc_id = pa.array(["1","2","3","4","5"])
    col_names = [OperatorConstants.ID, OperatorConstants.DOC_COLUMN_DEFAULT, OperatorConstants.NAME]
    input_table = pa.Table.from_arrays([doc_id, content,name], names=col_names)

    # 3. Run the operator
    table_list, metadata = operator.transform(input_table)
    # 4. Inspect and print the results after the operator is completed
    print(">>> completed the operator", operator)
    table = table_list[0]
    print(f"\noutput table: {table}, {metadata}")
    return table_list, metadata


# main entry point into the program; used for unit testing only
if __name__ == '__main__':
    main()
