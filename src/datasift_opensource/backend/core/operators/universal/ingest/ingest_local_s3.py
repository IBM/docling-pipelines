from typing import Any

import boto3
import pyarrow as pa

from common.constants.constants import DatasiftConstants, Metrics
from common.constants.operator_constants import OperatorConstants
from common.util.log import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.universal.ingest.ingest_utils import (
    filter_based_on_extension,
    get_filter_extensions,
)

INCLUDE_FOLDER_KEY: str = "include_folder"
MAX_FILES_KEY: str = "max_files"
MAX_FILES_DEFAULT_VALUE: int = 100
MAX_FILE_SIZE_KEY: str = "max_file_size"
MAX_FILE_SIZE_DEFAULT_VALUE: int = 100
INCLUDE_FILTER_KEY: str = "include_filter"
EXCLUDE_FILTER_KEY: str = "exclude_filter"

AWS_ACCESS_ID_KEY: str = "aws_access_id"
AWS_ACCESS_SECRET_KEY: str = "aws_access_secret"
AWS_BUCKET_NAME_KEY: str = "aws_bucket_name"

MB: int = 1024 * 1024

logger = get_logger()


class IngestS3Operator(AbstractOperator):  # pragma: no cover
    """
    Implements loading the contents of files from a local folder. Recursive traversal and
    filtering documents based on extensions (such as *.pdf) are supported.
    Note: Currently only PDF files are supported.
    """

    short_name: str = "ingest_local_s3"
    category: OperatorCategory = OperatorCategory.Ingest

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize based on the dictionary of configuration information.
        Expected parameters are:
        - include filter
        - column name where the doc content to be stored
        - filename include filter
        - filename exclude filter
        - max number of files to be ingested
        - max file size in MB, exceeding which the file will be skipped
        """
        # Make sure that the param name corresponds to the name used in apply_input_params method
        super().__init__(config)
        self.max_files: int = config.get(MAX_FILES_KEY, MAX_FILES_DEFAULT_VALUE)
        self.max_file_size: int = MB * config.get(MAX_FILE_SIZE_KEY, MAX_FILE_SIZE_DEFAULT_VALUE)
        self.included_extensions: list[str] | None = get_filter_extensions(config.get(INCLUDE_FILTER_KEY))
        self.excluded_extensions: list[str] | None = get_filter_extensions(config.get(EXCLUDE_FILTER_KEY))
        self.doc_column: str = config.get(OperatorConstants.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT)
        self.include_folder: str | None = config.get(INCLUDE_FOLDER_KEY)

        self.aws_access_id: str | None = config.get(AWS_ACCESS_ID_KEY)
        self.aws_access_secret: str | None = config.get(AWS_ACCESS_SECRET_KEY)
        self.aws_bucket_name: str | None = config.get(AWS_BUCKET_NAME_KEY)

        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

    @staticmethod
    def is_available() -> bool:
        return True

    def get_metadata(self) -> dict[str, Any]:
        return {OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available()}

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Operator-specific logic to read files from S3
        """

        # connect to S3
        session: Any = boto3.Session(
            aws_access_key_id=self.aws_access_id,
            aws_secret_access_key=self.aws_access_secret,
        )
        s3: Any = session.resource("s3")

        s3_bucket: Any = s3.Bucket(self.aws_bucket_name)
        file_list: list[str] = self.list_files(bucket=s3_bucket, max_files=self.max_files * 50)

        doc_data: list[dict[str, Any]] = []
        processed_count: int = 0

        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=0)

        for file in file_list:
            if processed_count >= self.max_files:
                continue

            if self.include_folder is not None:
                if not file.startswith(self.include_folder):
                    logger.info(
                        f"Skipping file from outside the given folder: {file}",
                        extra=self.common_log_arguments,
                    )
                    self.record_skipped_document(
                        metadata=metadata,
                        doc_id=file,
                        doc_name=file,
                        reason="File is outside the given folder",
                    )
                    continue
                elif filter_based_on_extension(file, self.excluded_extensions, self.included_extensions):
                    self.record_skipped_document(
                        metadata=metadata,
                        doc_id=file,
                        doc_name=file,
                        reason="File extension filtered out",
                    )
                    continue

            file_metadata: dict[str, Any]
            content: str | None
            file_metadata, content = self.get_file(s3=s3, bucket_name=self.aws_bucket_name, file_name=file)
            if content is None:
                logger.info(f"Skipping empty file: {file}", extra=self.common_log_arguments)
                self.record_skipped_document(metadata=metadata, doc_id=file, doc_name=file, reason="Empty file")
            else:
                processed_count += 1
                file_metadata[self.doc_column] = content
                doc_data.append(file_metadata)

        result_table: pa.Table = pa.Table.from_pylist(doc_data)

        # Update total docs and processed count
        metadata[Metrics.External.TOTAL_DOCS] = len(doc_data) + metadata[Metrics.External.SKIPPED_DOCS_COUNT]
        metadata[Metrics.External.PROCESSED_DOCS] = len(doc_data)

        return [result_table], metadata

    def list_files(self, bucket: Any, max_files: int = -1) -> list[str]:
        file_list: list[str] = []
        count: int = 0

        # TBD add pagination using s3 paginator object
        for obj in bucket.objects.all():
            if self.include_folder is not None:
                if not obj.key.startswith(self.include_folder):
                    logger.info(
                        f"Skipping file from outside the given folder: {obj}",
                        extra=self.common_log_arguments,
                    )
                    continue

            file_list.append(obj.key)
            count += 1
            if max_files > 0 and count > max_files:
                break

        return file_list

    def get_file(self, s3: Any, bucket_name: str | None, file_name: str) -> tuple[dict[str, Any], str | None]:
        """Get the contents of a file stored in S3"""
        metadata: dict[str, Any] = {}

        obj: Any = s3.Object(bucket_name, file_name).get()
        logger.info(f"Ingesting file: {obj}", extra=self.common_log_arguments)
        headers: dict[str, Any] = obj["ResponseMetadata"]["HTTPHeaders"]

        size: int = int(headers["content-length"])
        if size > self.max_file_size:
            return {}, None

        binary_content: bytes = obj["Body"].read()
        if len(binary_content) == 0:
            return {}, None

        # Decode binary content to string (assuming UTF-8 encoding for text files)
        try:
            content: str = binary_content.decode('utf-8')
        except UnicodeDecodeError:
            # If not UTF-8, try latin-1 as fallback
            try:
                content = binary_content.decode('latin-1')
            except Exception:
                logger.warning(f"Could not decode file {file_name}, skipping", extra=self.common_log_arguments)
                return {}, None

        # Add required fields for compatibility with other operators
        metadata["id"] = file_name
        metadata["name"] = file_name.split('/')[-1]  # Extract filename from path
        metadata["source_id"] = file_name
        metadata["modified_time"] = int(obj["LastModified"].timestamp())  # Required for incremental updates
        metadata["file-name"] = file_name
        metadata["etag"] = headers["etag"]
        metadata["last-modified"] = headers["last-modified"]
        metadata["content-type"] = headers["content-type"]

        logger.debug(
            f"Metadata: {metadata['etag']}, {metadata['last-modified']}, {metadata['content-type']}",
            extra=self.common_log_arguments,
        )

        return metadata, content

    # used for unit testing only


def main() -> None:  # pragma: no cover
    # 1. Construct the operators with the required configuration and input parameters
    operator: IngestS3Operator = IngestS3Operator(
        {
            "doc_column": "content",
            "max_files": 1,
            "max_file_size": 1,
            "include_folder": "datasift",
            "aws_access_id": "",
            "aws_access_secret": "",  # pragma: allowlist secret
            "aws_bucket_name": "tm-wkc-storage-1",
            "include_filter": "pdf",
        }
    )

    # 2. Create an in-memory py-arrow table, as the input
    input_table: pa.Table | None = None

    # 3. Run the operators
    table_list: list[pa.Table]
    metadata: dict[str, Any]
    table_list, metadata = operator.transform(input_table)

    # 4. Inspect and print the results after the operators is completed
    print(">>> completed the operators", operator)
    print(f"\noutput table has {table_list[0].num_rows} rows")

    table: pa.Table = table_list[0]
    # print(f"\noutput table: {table}")  # too much content
    print(f"output metadata : {metadata}")
    print("Found docs: ", table["file-name"], table["last-modified"])


# main entry point into the program; used for unit testing only
if __name__ == "__main__":  # pragma: no cover
    main()
