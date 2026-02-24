import json
from typing import Any
import pyarrow as pa
from data_processing.utils import TransformUtils
from langchain_core.documents import Document

from datasift_opensource.backend.common.exceptions.datasift_exceptions import DatasiftException
from datasift_opensource.backend.common.exceptions.error_messages import ValidationMessage, ValidationCodeMessages
from datasift_opensource.backend.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from datasift_opensource.backend.core.operators.operator_utils import OperatorUtils
from datasift_opensource.backend.common.util.common_utils import is_value_in_range
from datasift_opensource.backend.common.util.constants import DatasiftConstants, OperatorConstants, Metrics, ExecutionStatus, \
    AttributeDataTypes
from datasift_opensource.backend.core.operators.universal.ingest.ingest_local_folder import IngestLocalOperator
from datasift_opensource.backend.common.util.log import get_logger
from datasift_opensource.backend.common.util.operator_utils import remove_rows, find_doc_count

SIMPLE_CHUNK_TYPE = "simple"
CHUNK_TYPE_KEY = "chunk_type"
CHUNK_TYPE_DEFAULT = SIMPLE_CHUNK_TYPE
CHUNK_OVERLAP_KEY = "chunk_overlap"
CHUNK_OVERLAP_DEFAULT = 200
RETAIN_ORIGINAL_CONTENT_KEY = "retain_original_content"
RETAIN_ORIGINAL_CONTENT_DEFAULT = True
CHUNK_MIN_SIZE = 500
CHUNK_MAX_SIZE = 5000
CHUNK_OVERLAP_MIN_SIZE = 0
CHUNK_OVERLAP_MAX_SIZE = 512
logger = get_logger()
VALID_CHUNK_TYPES = [SIMPLE_CHUNK_TYPE]


class SemanticChunkerOperator(AbstractOperator):
    """
    Chunks the text based on semantic similarity.
    """
    short_name = OperatorConstants.CHUNKER
    category = OperatorCategory.Functional

    def __init__(self, config: dict[str, Any]):
        """
        Initialize based on the dictionary of configuration information. 
        Expected parameters are:
        - name of the column that has doc content
        """
        super().__init__(config)
        self.doc_column = config.get(OperatorConstants.DOC_COLUMN, OperatorConstants.DOC_COLUMN_DEFAULT)
        self.chunk_type = config.get(CHUNK_TYPE_KEY, CHUNK_TYPE_DEFAULT)
        self.chunk_size = config.get(OperatorConstants.CHUNK_SIZE, OperatorConstants.CHUNK_SIZE_DEFAULT)
        self.chunk_overlap = config.get(CHUNK_OVERLAP_KEY, CHUNK_OVERLAP_DEFAULT)
        self.retain_original_content = config.get(RETAIN_ORIGINAL_CONTENT_KEY, RETAIN_ORIGINAL_CONTENT_DEFAULT)
        self.common_log_arguments = {DatasiftConstants.JOB_ID: self.job_id,
                                     DatasiftConstants.JOB_RUN_ID: self.job_run_id}
        # if not is_parameterized_field(field=self.chunk_size) and isinstance(self.chunk_size, str):
        self.chunk_size = int(self.chunk_size)

    def get_metadata(self):
        operator_metadata = {
            OperatorConstants.SDK: True,
            OperatorConstants.CATEGORY: self.category.value,
            OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.LABEL: "Chunking",
            OperatorConstants.FEATURES: {
                OperatorConstants.CHUNK_SEQUENCE_NUMBER: {
                    OperatorConstants.NAME: "Chunk Sequence number",
                    OperatorConstants.DESCRIPTION: "Sequential chunk number for each text chunk, representing its position within a larger document",
                    OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.TAGS: [OperatorConstants.MANDATORY, OperatorConstants.INTERNAL_FEATURE],
                    OperatorConstants.TYPE: OperatorConstants.TYPE_INT64
                },
                OperatorConstants.START_INDEX: {
                    OperatorConstants.NAME: "Start Index",
                    OperatorConstants.DESCRIPTION: "Chunk starting token position in the source document",
                    OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.TAGS: [OperatorConstants.MANDATORY, OperatorConstants.INTERNAL_FEATURE],
                    OperatorConstants.TYPE: OperatorConstants.TYPE_INT64
                },
                OperatorConstants.CHUNKED_CONTENT: {
                    OperatorConstants.NAME: "Chunked Content",
                    OperatorConstants.DESCRIPTION: "Content containing segmented portions of larger text data.",
                    OperatorConstants.TAGS : [OperatorConstants.MANDATORY],
                    OperatorConstants.TYPE: AttributeDataTypes.LIST
                }
            },
            OperatorConstants.ATTRIBUTES: {
                CHUNK_TYPE_KEY: {
                    OperatorConstants.NAME: "Chunk Type",
                    OperatorConstants.DESCRIPTION: "Type of Chunker model being used",
                    OperatorConstants.REQUIRED: True,
                    OperatorConstants.DEFAULT: CHUNK_TYPE_DEFAULT,
                    OperatorConstants.VALID_VALUES: VALID_CHUNK_TYPES,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING
                },
                OperatorConstants.CHUNK_SIZE: {
                    OperatorConstants.NAME: "Chunk Size",
                    OperatorConstants.DESCRIPTION: "Chunk Size defined by user",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: OperatorConstants.CHUNK_SIZE_DEFAULT,
                    OperatorConstants.MIN_VALUE: CHUNK_MIN_SIZE,
                    OperatorConstants.MAX_VALUE: CHUNK_MAX_SIZE,
                    OperatorConstants.TYPE: AttributeDataTypes.INTEGER
                },
                CHUNK_OVERLAP_KEY: {
                    OperatorConstants.NAME: "Chunk Overlap",
                    OperatorConstants.DESCRIPTION: "If consecutive chunks share overlapping portions to retain context across boundaries",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: CHUNK_OVERLAP_DEFAULT,
                    OperatorConstants.MIN_VALUE: CHUNK_OVERLAP_MIN_SIZE,
                    OperatorConstants.MAX_VALUE: CHUNK_OVERLAP_MAX_SIZE,
                    OperatorConstants.TYPE: AttributeDataTypes.INTEGER
                }
            }
        }

        return operator_metadata

    def get_required_features(self):
        return [self.doc_column]

    def _validate_standard_chunker(self, errors: list):
        """
        Validate configuration for standard chunking (non-semantic).
        
        Args:
            errors: List to append validation errors to
        """
        if self.should_validate_field(field_value=self.chunk_size):
            if self.chunk_size is not None and not is_value_in_range(value=self.chunk_size, min_value=CHUNK_MIN_SIZE, max_value=CHUNK_MAX_SIZE):
                errors.append(f"Invalid input: chunk_size must be between {CHUNK_MIN_SIZE} and {CHUNK_MAX_SIZE}.")

        if self.should_validate_field(field_value=self.chunk_overlap):
            if self.chunk_overlap is not None and not is_value_in_range(value=self.chunk_overlap, min_value=CHUNK_OVERLAP_MIN_SIZE, max_value=CHUNK_OVERLAP_MAX_SIZE):
                errors.append(f"Invalid input: chunk_overlap must be between {CHUNK_OVERLAP_MIN_SIZE} and {CHUNK_OVERLAP_MAX_SIZE}.")

        if self.should_validate_field(field_value=self.chunk_type):
            if self.chunk_type not in VALID_CHUNK_TYPES:
                errors.append(ValidationMessage.create(message=f"Invalid chunk_type: {self.chunk_type}", message_code=ValidationCodeMessages.CHUNKER_INVALID_CHUNK_TYPE.name, chunk_type=self.chunk_type))

    def validate(self, errors: list, warnings: list, available_features: list):
        super().validate(errors, warnings, available_features)
        if OperatorConstants.EMBEDDINGS_COLUMN_DEFAULT in available_features:
            errors.append(ValidationMessage.create(message=ValidationCodeMessages.CHUNKER_OPERATOR_MISPLACED.value, message_code=ValidationCodeMessages.CHUNKER_OPERATOR_MISPLACED.name))

        self._validate_standard_chunker(errors)

    def simple_split_text(self, content: str):
        from langchain_text_splitters import CharacterTextSplitter

        doc = Document(page_content=content, metadata={"source": "parameter"})
        text_splitter = CharacterTextSplitter(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap, separator=".")
        return text_splitter.split_documents([doc])

    def _split_text(self, content):
        chunk_type = self.chunk_type.lower()

        if chunk_type == SIMPLE_CHUNK_TYPE:
            return self.simple_split_text(content)
        else:
            raise DatasiftException(f"Invalid chunk type: {self.chunk_type}")

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        logger.info(f"Using {self.chunk_type} for generating chunks", extra=self.common_log_arguments)

        input_doc_data = table.to_pylist()
        chunked_content_column = []
        metadata = self.create_base_metadata(total_docs_count=find_doc_count(table=table))
        remove_row_idx = []
        for idx, doc in enumerate(input_doc_data):
            try:
                logger.debug(f"Creating chunks for the document {doc.get(OperatorConstants.NAME, doc.get(OperatorConstants.ID))} with {self.chunk_type.lower()} chunk type",
                    extra=self.common_log_arguments)
                content = doc[self.doc_column]
                if not content:
                    raise DatasiftException(f"The column '{self.doc_column}' was not found in the input data. This may be due to the use of the merge operator with the 'columns' merge type. For this flow, please use the 'rows' merge type instead.")
                chunks = self._split_text(content)
            except Exception as exc:
                logger.error(f"An error occurred while creating chunking for the document {doc.get(OperatorConstants.NAME,doc.get(OperatorConstants.ID))} : \n {str(exc)}",exc_info=True,stack_info=True)
                self.record_failed_document(metadata=metadata, doc_id=doc.get(OperatorConstants.ID),
                                            doc_name=doc.get(OperatorConstants.NAME),
                                            reason=f"Failed to create a data chunk for the document '{doc.get(OperatorConstants.NAME)}' due to the following error: {getattr(exc, 'message', str(exc)) if getattr(exc, 'message', str(exc)) else getattr(exc, 'message', repr(exc))}")
                metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(metadata[Metrics.External.NODE_STATUS],
                                                                                    ExecutionStatus.COMPLETED_WITH_ERRORS.value)
                remove_row_idx.append(idx)
                continue
            chunked_content = []
            for chunk in chunks:
                chunked_content.append({
                    OperatorConstants.CHUNK: chunk.page_content,
                    OperatorConstants.START_INDEX: chunk.metadata.get(OperatorConstants.START_INDEX, 0) if chunk.metadata else 0
                })

            chunked_content_column.append(chunked_content)
            metadata[Metrics.External.PROCESSED_DOCS] += 1

        table = remove_rows(table=table, remove_row_idx=remove_row_idx)
        if chunked_content_column:
            table = TransformUtils.add_column(table=table, name=OperatorConstants.CHUNKED_CONTENT, content=chunked_content_column)

        # Add the hash column to the pyarrow table
        if table.columns:
            logger.info(f"Dropping original content column: {self.doc_column} from pyarrow table", extra=self.common_log_arguments)
            # table_list, _ = DocIdHashOperator({}).transform(table)
            # table = table_list[0]

        # If original content is not to be retained then drop the content column.
        if table.columns and not self.retain_original_content:
            table = table.drop_columns([self.doc_column])

        return [table], metadata


def main(runtime: str = 'python'): # pragma: no cover

    ingest_operator = IngestLocalOperator({
        "doc_column": "content",
        "input_folder": "../../../../test/input_docs/customer_support_docs/",
        "include_filter": "pdf,txt"})

    # 2. Create an in-memory py-arrow table, as the input
    input_table = None

    # 3. Run the operators
    table_list, _ = ingest_operator.transform(input_table)
    table = table_list[0]

    # 4. Run hashing operator
    # hashing_operator = DocIdHashOperator({})

    # table_list, _ = hashing_operator.transform(table)
    # table = table_list[0]
    print(f">>>>>>>>>>>>> Number of rows before chunking: {table.num_rows}")

    # 5. Run chunking operator
    config = {"chunk_size": 200}
    if runtime == 'python':
        operator = SemanticChunkerOperator(config=config)
    else:
        raise ValueError("unknown operator value")
    print(operator)

    table_list, metadata = operator.transform(table)
    table: pa.Table = table_list[0]
    print(table.schema)
    print(f">>>>>>>>>>>>> Number of rows after chunking: {table.num_rows}")

    print(f">>>>>>>>>>>>> Meta Data : - \n {json.dumps(metadata,indent=2)}")


if __name__ == '__main__':  # pragma: no cover
    main()
