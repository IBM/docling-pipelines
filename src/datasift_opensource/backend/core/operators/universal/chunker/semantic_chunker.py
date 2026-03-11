import json
from typing import Any

import pyarrow as pa
from data_processing.utils import TransformUtils
from langchain_core.documents import Document

from common.exceptions.datasift_exceptions import DatasiftException
from common.exceptions.error_messages import ValidationCodeMessages, ValidationMessage
from common.util.common_utils import is_value_in_range
from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
    OperatorConstants,
)
from common.util.log import get_logger
from common.util.operator_utils import find_doc_count, remove_rows
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.operator_utils import OperatorUtils
from core.operators.universal.ingest.ingest_local_folder import IngestLocalOperator

SIMPLE_CHUNK_TYPE: str = "simple"
CHUNK_TYPE_KEY: str = "chunk_type"
CHUNK_TYPE_DEFAULT: str = SIMPLE_CHUNK_TYPE
CHUNK_OVERLAP_KEY: str = "chunk_overlap"
CHUNK_OVERLAP_DEFAULT: int = 200
RETAIN_ORIGINAL_CONTENT_KEY: str = "retain_original_content"
RETAIN_ORIGINAL_CONTENT_DEFAULT: bool = True
CHUNK_MIN_SIZE: int = 500
CHUNK_MAX_SIZE: int = 5000
CHUNK_OVERLAP_MIN_SIZE: int = 0
CHUNK_OVERLAP_MAX_SIZE: int = 512
logger = get_logger()
VALID_CHUNK_TYPES: list[str] = [SIMPLE_CHUNK_TYPE]


class SemanticChunkerOperator(AbstractOperator):
    """
    Chunks the text based on semantic similarity.
    """

    short_name: str = OperatorConstants.Operators.CHUNKER
    category: OperatorCategory = OperatorCategory.Functional

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize based on the dictionary of configuration information.
        Expected parameters are:
        - name of the column that has doc content
        """
        super().__init__(config)
        self.doc_column: str = config.get(OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT)
        self.chunk_type: str = config.get(CHUNK_TYPE_KEY, CHUNK_TYPE_DEFAULT)
        self.chunk_size: int = config.get(OperatorConstants.Processing.CHUNK_SIZE, OperatorConstants.Processing.CHUNK_SIZE_DEFAULT)
        self.chunk_overlap: int = config.get(CHUNK_OVERLAP_KEY, CHUNK_OVERLAP_DEFAULT)
        self.retain_original_content: bool = config.get(RETAIN_ORIGINAL_CONTENT_KEY, RETAIN_ORIGINAL_CONTENT_DEFAULT)
        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }
        # if not is_parameterized_field(field=self.chunk_size) and isinstance(self.chunk_size, str):
        self.chunk_size = int(self.chunk_size)

    def get_metadata(self) -> dict[str, Any]:
        operator_metadata = {
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Misc.LABEL: "Chunking",
            OperatorConstants.Config.FEATURES: {
                OperatorConstants.CHUNK_SEQUENCE_NUMBER: {
                    OperatorConstants.Misc.NAME: "Chunk Sequence number",
                    OperatorConstants.Config.DESCRIPTION: "Sequential chunk number for each text chunk, representing its position within a larger document",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TAGS: [
                        OperatorConstants.Misc.MANDATORY,
                        OperatorConstants.INTERNAL_FEATURE,
                    ],
                    OperatorConstants.Misc.TYPE: OperatorConstants.TYPE_INT64,
                },
                OperatorConstants.START_INDEX: {
                    OperatorConstants.Misc.NAME: "Start Index",
                    OperatorConstants.Config.DESCRIPTION: "Chunk starting token position in the source document",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TAGS: [
                        OperatorConstants.Misc.MANDATORY,
                        OperatorConstants.INTERNAL_FEATURE,
                    ],
                    OperatorConstants.Misc.TYPE: OperatorConstants.TYPE_INT64,
                },
                OperatorConstants.CHUNKED_CONTENT: {
                    OperatorConstants.Misc.NAME: "Chunked Content",
                    OperatorConstants.Config.DESCRIPTION: "Content containing segmented portions of larger text data.",
                    OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY],
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.LIST,
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                CHUNK_TYPE_KEY: {
                    OperatorConstants.Misc.NAME: "Chunk Type",
                    OperatorConstants.Config.DESCRIPTION: "Type of Chunker model being used",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: CHUNK_TYPE_DEFAULT,
                    OperatorConstants.Config.VALID_VALUES: VALID_CHUNK_TYPES,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Processing.CHUNK_SIZE: {
                    OperatorConstants.Misc.NAME: "Chunk Size",
                    OperatorConstants.Config.DESCRIPTION: "Chunk Size defined by user",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Processing.CHUNK_SIZE_DEFAULT,
                    OperatorConstants.Filtering.MIN_VALUE: CHUNK_MIN_SIZE,
                    OperatorConstants.Filtering.MAX_VALUE: CHUNK_MAX_SIZE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                CHUNK_OVERLAP_KEY: {
                    OperatorConstants.Misc.NAME: "Chunk Overlap",
                    OperatorConstants.Config.DESCRIPTION: "If consecutive chunks share overlapping portions to retain context across boundaries",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: CHUNK_OVERLAP_DEFAULT,
                    OperatorConstants.Filtering.MIN_VALUE: CHUNK_OVERLAP_MIN_SIZE,
                    OperatorConstants.Filtering.MAX_VALUE: CHUNK_OVERLAP_MAX_SIZE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
            },
        }

        return operator_metadata

    def get_required_features(self) -> list[str]:
        return [self.doc_column]

    def _validate_standard_chunker(self, errors: list[Any]) -> None:
        """
        Validate configuration for standard chunking (non-semantic).

        Args:
            errors: List to append validation errors to
        """
        if self.should_validate_field(field_value=self.chunk_size):
            if self.chunk_size is not None and not is_value_in_range(
                value=self.chunk_size,
                min_value=CHUNK_MIN_SIZE,
                max_value=CHUNK_MAX_SIZE,
            ):
                errors.append(f"Invalid input: chunk_size must be between {CHUNK_MIN_SIZE} and {CHUNK_MAX_SIZE}.")

        if self.should_validate_field(field_value=self.chunk_overlap):
            if self.chunk_overlap is not None and not is_value_in_range(
                value=self.chunk_overlap,
                min_value=CHUNK_OVERLAP_MIN_SIZE,
                max_value=CHUNK_OVERLAP_MAX_SIZE,
            ):
                errors.append(
                    f"Invalid input: chunk_overlap must be between {CHUNK_OVERLAP_MIN_SIZE} and {CHUNK_OVERLAP_MAX_SIZE}."
                )

        if self.should_validate_field(field_value=self.chunk_type):
            if self.chunk_type not in VALID_CHUNK_TYPES:
                errors.append(
                    ValidationMessage.create(
                        message=f"Invalid chunk_type: {self.chunk_type}",
                        message_code=ValidationCodeMessages.CHUNKER_INVALID_CHUNK_TYPE.name,
                        chunk_type=self.chunk_type,
                    )
                )

    def validate(self, errors: list[Any], warnings: list[Any], available_features: list[str]) -> None:
        super().validate(errors, warnings, available_features)
        if OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT in available_features:
            errors.append(
                ValidationMessage.create(
                    message=ValidationCodeMessages.CHUNKER_OPERATOR_MISPLACED.value,
                    message_code=ValidationCodeMessages.CHUNKER_OPERATOR_MISPLACED.name,
                )
            )

        self._validate_standard_chunker(errors)

    def simple_split_text(self, content: str) -> list[Document]:
        from langchain_text_splitters import CharacterTextSplitter

        doc: Document = Document(page_content=content, metadata={"source": "parameter"})
        text_splitter: CharacterTextSplitter = CharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap, separator="."
        )
        return text_splitter.split_documents([doc])

    def _split_text(self, content: str) -> list[Document]:
        chunk_type: str = self.chunk_type.lower()

        if chunk_type == SIMPLE_CHUNK_TYPE:
            return self.simple_split_text(content)
        else:
            raise DatasiftException(f"Invalid chunk type: {self.chunk_type}")

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        logger.info(
            f"Using {self.chunk_type} for generating chunks",
            extra=self.common_log_arguments,
        )

        input_doc_data: list[dict[str, Any]] = table.to_pylist()
        chunked_content_column: list[list[dict[str, Any]]] = []
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=find_doc_count(table=table))
        remove_row_idx: list[int] = []
        for idx, doc in enumerate(input_doc_data):
            try:
                logger.debug(
                    f"Creating chunks for the document {doc.get(OperatorConstants.Misc.NAME, doc.get(OperatorConstants.Columns.ID))} with {self.chunk_type.lower()} chunk type",
                    extra=self.common_log_arguments,
                )
                content: str = doc[self.doc_column]
                if not content:
                    raise DatasiftException(
                        f"The column '{self.doc_column}' was not found in the input data. This may be due to the use of the merge operator with the 'columns' merge type. For this flow, please use the 'rows' merge type instead."
                    )
                chunks: list[Document] = self._split_text(content)
            except Exception as exc:
                logger.error(
                    f"An error occurred while creating chunking for the document {doc.get(OperatorConstants.Misc.NAME, doc.get(OperatorConstants.Columns.ID))} : \n {exc!s}",
                    exc_info=True,
                    stack_info=True,
                )
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=doc.get(OperatorConstants.Columns.ID),
                    doc_name=doc.get(OperatorConstants.Misc.NAME),
                    reason=f"Failed to create a data chunk for the document '{doc.get(OperatorConstants.Misc.NAME)}' due to the following error: {getattr(exc, 'message', str(exc)) if getattr(exc, 'message', str(exc)) else getattr(exc, 'message', repr(exc))}",
                )
                metadata[Metrics.External.NODE_STATUS] = OperatorUtils.merge_status(
                    metadata[Metrics.External.NODE_STATUS],
                    ExecutionStatus.COMPLETED_WITH_ERRORS.value,
                )
                remove_row_idx.append(idx)
                continue
            chunked_content: list[dict[str, Any]] = []
            for chunk in chunks:
                chunked_content.append(
                    {
                        OperatorConstants.Columns.CHUNK: chunk.page_content,
                        OperatorConstants.START_INDEX: chunk.metadata.get(OperatorConstants.START_INDEX, 0)
                        if chunk.metadata
                        else 0,
                    }
                )

            chunked_content_column.append(chunked_content)
            metadata[Metrics.External.PROCESSED_DOCS] += 1

        table = remove_rows(table=table, remove_row_idx=remove_row_idx)
        if chunked_content_column:
            table = TransformUtils.add_column(
                table=table,
                name=OperatorConstants.CHUNKED_CONTENT,
                content=chunked_content_column,
            )

        # Add the hash column to the pyarrow table
        if table.columns:
            logger.info(
                f"Dropping original content column: {self.doc_column} from pyarrow table",
                extra=self.common_log_arguments,
            )
            # table_list, _ = DocIdHashOperator({}).transform(table)
            # table = table_list[0]

        # If original content is not to be retained then drop the content column.
        if table.columns and not self.retain_original_content:
            table = table.drop_columns([self.doc_column])

        return [table], metadata


def main(runtime: str = "python") -> None:  # pragma: no cover
    ingest_operator: IngestLocalOperator = IngestLocalOperator(
        {
            "doc_column": "content",
            "input_folder": "../../../../test/input_docs/customer_support_docs/",
            "include_filter": "pdf,txt",
        }
    )

    # 2. Create an in-memory py-arrow table, as the input
    input_table: pa.Table | None = None

    # 3. Run the operators
    table_list: list[pa.Table]
    table_list, _ = ingest_operator.transform(input_table)
    table: pa.Table = table_list[0]

    # 4. Run hashing operator
    # hashing_operator = DocIdHashOperator({})

    # table_list, _ = hashing_operator.transform(table)
    # table = table_list[0]
    print(f">>>>>>>>>>>>> Number of rows before chunking: {table.num_rows}")

    # 5. Run chunking operator
    config: dict[str, Any] = {"chunk_size": 200}
    operator: SemanticChunkerOperator
    if runtime == "python":
        operator = SemanticChunkerOperator(config=config)
    else:
        raise ValueError("unknown operator value")
    print(operator)

    metadata: dict[str, Any]
    table_list, metadata = operator.transform(table)
    table = table_list[0]
    print(table.schema)
    print(f">>>>>>>>>>>>> Number of rows after chunking: {table.num_rows}")

    print(f">>>>>>>>>>>>> Meta Data : - \n {json.dumps(metadata, indent=2)}")


if __name__ == "__main__":  # pragma: no cover
    main()
