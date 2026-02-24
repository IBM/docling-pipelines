import os
from typing import Any
import pyarrow as pa
from pypdf import PdfReader

from datasift_opensource.backend.common.util.incremental_update_util import IncrementalUpdateUtil
from datasift_opensource.backend.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from datasift_opensource.backend.common.util.constants import OperatorConstants, Metrics, DatasiftConstants, ExecutionStatus, \
    AttributeDataTypes
from datasift_opensource.backend.common.util.log import get_logger
from datasift_opensource.backend.core.operators.universal.ingest.ingest_utils import get_filter_extensions, filter_based_on_extension, \
    is_doc_previously_processed

INPUT_FOLDER_NAME_KEY = "input_folder"
INCLUDE_FILTER_KEY = "include_filter"
EXCLUDE_FILTER_KEY = "exclude_filter"
DOC_COLUMN_NAME_KEY = "doc_column"
MAX_FILES_KEY = "max_files"
MAX_FILES_DEFAULT_VALUE = 100
MAX_FILE_SIZE_KEY = "max_file_size"
MAX_FILE_SIZE_DEFAULT_VALUE = 100

MB = 1024 * 1024

logger = get_logger()


class IngestLocalOperator(AbstractOperator):
    """
    Implements loading the contents of files from a local folder. Recursive traversal and
    filtering documents based on extensions (such as *.pdf) are supported.
    Note: Currently only PDF files are supported.
    """

    short_name = OperatorConstants.INGEST_LOCAL
    category = OperatorCategory.Ingest

    def __init__(self, config: dict[str, Any]):
        """
        Initialize based on the dictionary of configuration information. 
        Expected parameters are:
        - input folder
        - column name where the doc content to be stored
        - filename include filter
        - filename exclude filter
        - max number of files to be ingested
        - max file size in MB, exceeding which the file will be skipped
        """
        # Make sure that the param name corresponds to the name used in apply_input_params method
        super().__init__(config)
        self.input_folder = config.get(INPUT_FOLDER_NAME_KEY, "../test-data/input")
        self.max_files = config.get(MAX_FILES_KEY, MAX_FILES_DEFAULT_VALUE)
        self.max_file_size = MB * config.get(MAX_FILE_SIZE_KEY, MAX_FILE_SIZE_DEFAULT_VALUE)
        self.doc_column = config.get(OperatorConstants.DOC_COLUMN, OperatorConstants.DOC_COLUMN_DEFAULT)
        self.included_extensions = get_filter_extensions(config.get(INCLUDE_FILTER_KEY, None))
        self.excluded_extensions = get_filter_extensions(config.get(EXCLUDE_FILTER_KEY, None))
        self.doc_column: str = config.get(OperatorConstants.DOC_COLUMN, OperatorConstants.DOC_COLUMN_DEFAULT)
        self.doc_id_hash = config.get(OperatorConstants.DOC_ID_HASH, OperatorConstants.DOC_ID_HASH_DEFAULT)
        self.common_log_arguments = {DatasiftConstants.JOB_ID: self.job_id, DatasiftConstants.JOB_RUN_ID: self.job_run_id}
        self.force_ingest = config.get(DatasiftConstants.FORCE_INGEST, False)
        self.retain_deleted_docs = config.get(DatasiftConstants.RETAIN_DELETED_DOCS, DatasiftConstants.RETAIN_DELETED_DOCS_DEFAULT)

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Operator-specific logic to convert one input Table to 0 or more output tables. 
        In this case, crawl through the given folder, find all the files matchng the 
        "include_filter", skip the files matching the "exclude_filter" and add the content
        to a new column named "content" in the table. The output 
        column name is configurable using the "config" dictionary.
        """
        incremental_update_util = IncrementalUpdateUtil()
        # get all previously processed doc IDs with modification time
        self.previously_processed_docs_dict = None if self.force_ingest else incremental_update_util.get_all_processed_docs(
            job_id=self.context_id)

        doc_data, metadata = self.process_files(self.input_folder)
        if table is None:
            table = pa.Table.from_pylist(doc_data)
        else:
            table = pa.Table.from_pylist(doc_data)
            # TODO: Fix this, doc_data contains multiple columns
            #temp_table = pa.Table.from_pylist(doc_data)
            #col_names = temp_table.column_names
            #i = 0
            #for col in temp_table.columns:
            #    table.append_column(field_=col_names[i], column=[col])
            #    i += 1

        # Return the resulting pyarrow table and metadata
        node_status = ExecutionStatus.COMPLETED.value
        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_ERRORS.value
        elif metadata[Metrics.External.SKIPPED_DOCS_COUNT] > 0:
            node_status = ExecutionStatus.COMPLETED_WITH_WARNINGS.value
        metadata[Metrics.External.NODE_STATUS] = node_status
        return [table], metadata

    def process_files(self, root_folder: str) -> tuple[list, dict[str, Any]]:
        data = []
        file_count = 0
        processed_count = 0

        # Initialize metadata
        metadata = self.create_base_metadata(total_docs_count=0)
        
        for (root, dirs, files) in os.walk(root_folder, topdown=True):
            if files and dirs:
                logger.info('>>> %s/%s/%s', root, dirs[0], files[0], extra=self.common_log_arguments)
            elif files:
                logger.info('>>> %s/%s', root, files[0], extra=self.common_log_arguments)
            elif dirs:
                logger.info('No files found in: %s', root, extra=self.common_log_arguments)
            else:
                logger.info('No files or subdirectories found in: %s', root, extra=self.common_log_arguments)

            for file in files:
                file_count += 1
                doc = self.process_file(root, file, metadata, file_count)
                if doc:
                    processed_count += 1
                    data.append(doc)

        # Update total docs and processed count
        metadata[Metrics.External.TOTAL_DOCS] = file_count
        metadata[Metrics.External.PROCESSED_DOCS] = processed_count
        
        return data, metadata

    def process_file(self, root, file, metadata, file_count):
        abs_path = os.path.join(root, file)
        stats = os.stat(abs_path)
        if not self.check_constraints(file=file, file_stats=stats, abs_path=abs_path, metadata=metadata,
                                      file_count=file_count):
            return None
        doc_id = str(stats.st_ino)
        modified_time = round(stats.st_mtime)
        if is_doc_previously_processed(previously_processed_docs_dict=self.previously_processed_docs_dict,
                                       doc_id=doc_id, modified_time=modified_time):
            logger.info(f">>> Skipping ingesting already processed document : {doc_id}",
                        extra=self.common_log_arguments)
            return None

        doc = {
            "id": doc_id,
            "name": abs_path,
            "size": stats.st_size,
            "created_time": round(stats.st_ctime),
            "modified_time": modified_time
        }

        if self.extract_content(file=file, file_stats=stats, file_abs_path=abs_path, doc=doc, metadata=metadata):
            return doc

    def read_pdf(self, filename):
        reader = PdfReader(filename)

        content = ''
        for page in reader.pages:
            text = page.extract_text()
            if text:
                content += "\n" + text.strip()

        return content
    
    def read_textf(self, filename):
        content = ''
        with open(filename) as f: 
            content = f.read()
        return content

    def extract_content(self,file,file_stats,file_abs_path,doc:dict[str,str],metadata:dict[str,Any])-> bool:
        logger.info("Extracting content from: " + file_abs_path, extra={DatasiftConstants.JOB_ID: self.job_id,
                                                                                            DatasiftConstants.JOB_RUN_ID: self.job_run_id})
        extn = file.split('.')[-1]
        try:
            if extn == 'pdf':
                doc[self.doc_column] = self.read_pdf(file_abs_path)
            elif extn == 'txt':
                doc[self.doc_column] = self.read_textf(file_abs_path)
            return True
        except Exception as exc:
            logger.error(f"An error occurred while extracting the content from: {file_abs_path}", extra=self.common_log_arguments)
            self.record_failed_document(metadata=metadata, doc_id=str(file_stats.st_ino), doc_name=file_abs_path,
                                       reason=f"Couldn't able to extract the content from the file {file_abs_path} due to {str(exc)}")
            return False
            
    def check_constraints(self,file,file_stats,abs_path,metadata:dict[str,Any],file_count) -> bool:
        if file_stats.st_size >= self.max_file_size:
            logger.warn("File size exceeded max permitted size %s", file_stats.st_size, extra=self.common_log_arguments)
            self.record_skipped_document(metadata=metadata, doc_id=str(file_stats.st_ino), doc_name=abs_path,
                                        reason=f"File Size exceeded max permitted size for the file {abs_path} with the file size {file_stats.st_size}")
            return False

        elif file_count > self.max_files:
            logger.info("File count exceeded max files permitted", self.max_files, extra=self.common_log_arguments)
            self.record_skipped_document(metadata=metadata, doc_id=str(file_stats.st_ino), doc_name=abs_path,
                                        reason="File count exceeded max files permitted")
            return False

        elif filter_based_on_extension(file, self.excluded_extensions, self.included_extensions):
            logger.info(f">>> Skipping based on Filter : {file}", extra=self.common_log_arguments)
            self.record_skipped_document(metadata=metadata, doc_id=str(file_stats.st_ino), doc_name=abs_path,
                                        reason=f"Skipping the file {abs_path} due to the extension filter. The file has the extension {file.split('.')[-1]}.")
            return False
        else:
            return True
    def get_metadata(self):
        metadata_features = {} #get_common_metadata_features()
        metadata_features.update({
            self.doc_column: {
                OperatorConstants.NAME: "Document Content",
                OperatorConstants.DESCRIPTION: "The content of the document",
                OperatorConstants.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.TYPE: OperatorConstants.TYPE_STRING
            },
            self.doc_id_hash: {
                OperatorConstants.NAME: "Hash ID",
                OperatorConstants.DESCRIPTION: "Hash ID of the row",
                OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.TYPE: OperatorConstants.TYPE_STRING,
                OperatorConstants.IS_PRIMARY: True,
                OperatorConstants.TAGS: [OperatorConstants.MANDATORY, OperatorConstants.PRIMARY]
            }
        })
        return {
            OperatorConstants.CATEGORY: self.category.value,
            OperatorConstants.FEATURES: metadata_features,
            OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.ATTRIBUTES: {
                OperatorConstants.MAX_FILE_SIZE: {
                    OperatorConstants.NAME : "Max File Size",
                    OperatorConstants.DESCRIPTION: "If the document is larger than the given max file size, then it will be skipped",
                    OperatorConstants.DEFAULT: 100,
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.TYPE: AttributeDataTypes.INTEGER
                },
                OperatorConstants.INCLUDE_FILTER_KEY: {
                    OperatorConstants.NAME: "Include File Type",
                    OperatorConstants.DESCRIPTION: "File types to be included",
                    OperatorConstants.DEFAULT: "pdf,txt,md",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.TYPE: AttributeDataTypes.LIST
                }
            }
        }


# used for unit testing only
def main():   # pragma: no cover
    
    # 1. Construct the operators with the required configuration and input parameters
    operator = IngestLocalOperator({ 
        "doc_column": "content", 
        "input_folder": "cliapp/test/input_docs",
        "include_filter": "pdf,txt" })
    print(operator)

    # 2. Create an in-memory py-arrow table, as the input
    input_table = None
    
    # 3. Run the operators
    table_list, metadata = operator.transform(input_table)

    # 4. Inspect and print the results after the operators is completed
    print(">>> completed the operators", operator)
    print(f"\noutput table has {table_list[0].num_rows} rows")

    table = table_list[0]
    # print(f"\noutput table: {table}")  # too much content
    print(f"output metadata : {metadata}")
    if table_list[0].num_rows: # avoid printing if table is empty
        print("Found docs: ", table["name"], table["size"])

# main entry point into the program; used for unit testing only
if __name__ == '__main__':   # pragma: no cover
    main()
