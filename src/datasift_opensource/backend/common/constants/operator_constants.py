"""
OperatorConstants with nested class organization.

All constants are organized into logical nested classes for better structure
and discoverability. Import and use as:
    from common.constants.operator_constants import OperatorConstants
    index_name = config.get(OperatorConstants.VectorDB.INDEX_NAME)

All constants must be accessed through their nested class structure:
    - OperatorConstants.Operators.* for operator names
    - OperatorConstants.Columns.* for column names
    - OperatorConstants.Config.* for configuration keys
    - OperatorConstants.VectorDB.* for vector database settings
    - OperatorConstants.Types.* for data types
    - OperatorConstants.Extraction.* for extraction settings
    - OperatorConstants.ExtractionModes.* for extraction mode settings
    - OperatorConstants.PIIHAP.* for PII/HAP settings
    - OperatorConstants.Filtering.* for filtering settings
    - OperatorConstants.Processing.* for processing settings
    - OperatorConstants.Metadata.* for metadata keys
    - OperatorConstants.Storage.* for storage settings
    - OperatorConstants.Misc.* for miscellaneous constants
"""

from typing import Final


class OperatorConstants:
    """Main constants class with nested subclasses for organization."""

    class Operators:
        """Operator name constants."""

        # Ingestion Operators
        INGEST: Final[str] = "ingest"
        INGEST_CSV: Final[str] = "ingest_csv"
        INGEST_LOCAL: Final[str] = "ingest_local"

        # Embeddings Operators
        EMBEDDINGS: Final[str] = "embeddings"

        # Extraction Operators
        EXTRACT_OPERATOR: Final[str] = "extract_operator"
        ENTITY_EXTRACT: Final[str] = "extract_entity"
        EXTRACT_JSON: Final[str] = "extract_json"

        # Processing Operators
        BRANCHING: Final[str] = "branching"
        CHUNKER: Final[str] = "chunker"
        DOC_ID_OPERATOR: Final[str] = "doc_id_hash"
        DOC_QUALITY: Final[str] = "doc_quality"
        EDEDUP: Final[str] = "ededup"
        LANG_DETECT: Final[str] = "lang_detect"
        LANG_DETECT_FASTTEXT: Final[str] = "lang_detect_fasttext"
        MERGE: Final[str] = "merge"
        ML_ENRICHMENT: Final[str] = "ml_enrichment"
        READABILITY: Final[str] = "readability"
        REDACTION: Final[str] = "redaction"
        REGEX_ANNOTATOR: Final[str] = "regex_annotator"
        SQL_FILTER: Final[str] = "sql_filter"

        # Storage Operators
        ENTITY_CURATION_OPERATOR: Final[str] = "entity_curation_operator"
        ENTITY_STORE_OPERATOR: Final[str] = "entity_store"
        OPENSEARCH: Final[str] = "opensearch"

        # Utility Operators
        DESIGN_FLOW_OUTPUT_OPERATOR: Final[str] = "design_flow_output"
        NOOP: Final[str] = "noop"

    class Columns:
        """DataFrame column name constants."""

        # Content and Document Columns
        BINARY_CONTENT: Final[str] = "binary_content"
        CHUNK: Final[str] = "chunk"
        CHUNKED_CONTENT: Final[str] = "chunked_content"
        CHUNK_SEQUENCE_NUMBER: Final[str] = "chunk_sequence_number"
        DOC_COLUMN: Final[str] = "doc_column"
        DOC_COLUMN_DEFAULT: Final[str] = "content"
        DOC_ID_COLUMN: Final[str] = "doc_id_column"
        DOC_ID_HASH: Final[str] = "doc_id_hash_column"
        DOC_ID_HASH_DEFAULT: Final[str] = "doc_id_hash"
        DOCLING_DOCUMENT: Final[str] = "docling_document"
        DOCUMENT_TYPE: Final[str] = "document_type"
        ID: Final[str] = "id"
        JSON_CONTENT: Final[str] = "json_content"
        KVP_COLUMN: Final[str] = "kvp_column"
        NAME: Final[str] = "name"
        PATH: Final[str] = "path"
        RAW_TEXT: Final[str] = "raw_text"
        USER_DEFINED_CONTENT_COLUMN: Final[str] = "user_defined_content_column"
        SUMMARY: Final[str] = "summary"

        # Embeddings and Vector Columns
        DENSE_EMBEDDINGS_COLUMN_DEFAULT: Final[str] = "vector_embeddings"
        EMBEDDINGS: Final[str] = "embeddings"
        EMBEDDINGS_COLUMN: Final[str] = "embeddings_column"
        EMBEDDINGS_COLUMN_DEFAULT: Final[str] = "embeddings"
        SPARSE_EMBEDDINGS_COLUMN_DEFAULT: Final[str] = "sparse_embeddings"

        # Entity and Extraction Columns
        DATABASE_TABLES_COLUMN_NAME: Final[str] = "database_tables"
        ENTITY_IDS_COLUMN_NAME: Final[str] = "entity_ids"
        EXTRACTED_DATA: Final[str] = "extracted_data"
        IMAGES: Final[str] = "images"
        PAGE_IMAGES: Final[str] = "page_images"
        PAGES_PROCESSED_COLUMN: Final[str] = "pages_processed"
        STRUCTURED_DATA: Final[str] = "structured_data"
        TABLES: Final[str] = "tables"
        TRANSFORMED_ENTITIES_COLUMN_NAME: Final[str] = "transformed_entities"

        # Language Detection Columns
        LANGUAGE_NAME_COLUMN_KEY: Final[str] = "lang_name"
        LANGUAGE_SCORE_COLUMN_KEY: Final[str] = "lang_score"

        # ML Enrichment Columns
        LANG_COLUMN = "lang_column"
        OUTPUT_COLUMN = "output_column"
        OUTPUT_COLUMN_PREFIX = "output_column_prefix"
        NEWLINE_NORMALIZED_COLUMN_NAME = "newline_normalized_column_name"
        ERROR_COLUMN_NAME = "error_column_name"
        CONTENT_COLUMN_NAME = "content_column_name"
        LANG_COLUMN_NAME = "lang_column_name"

        # Merge and Join Columns
        COLUMN_LIST: Final[str] = "column_list"
        FEATURES: Final[str] = "columns"
        INNER_JOIN_DUPLICATE_COLUMN: Final[str] = "inner_join"

    class Config:
        """Configuration key constants."""

        # Core Configuration Keys
        API_KEY: Final[str] = "api_key"  # pragma: allowlist secret
        ATTRIBUTES: Final[str] = "attributes"
        BATCH_SIZE: Final[str] = "batch_size"
        CONFIG: Final[str] = "config"
        CONFIGURATION: Final[str] = "configuration"
        CUSTOM_SCHEMA: Final[str] = "custom_schema"
        DEFAULT: Final[str] = "default"
        DESCRIPTION: Final[str] = "description"
        GLOBAL_CONFIG: Final[str] = "global_config"
        PARAMETERS: Final[str] = "parameters"
        PROPERTIES: Final[str] = "properties"
        REQUIRED: Final[str] = "required"
        USERNAME: Final[str] = "username"

        # Feature and Schema Configuration
        ALL_SCHEMA_DETAILS: Final[str] = "all_schema_details"
        AVAILABLE_FEATURES: Final[str] = "available_features"
        AVAILABLE_FOR_FILTER: Final[str] = "available_for_filter"
        AVAILABLE_FOR_VECTOR_DB: Final[str] = "available_for_vector_db"
        DEFAULT_FEATURE_MAPPINGS: Final[str] = "default_feature_mappings"
        FEATURE_MAPPINGS: Final[str] = "feature_mappings"
        FEATURES: Final[str] = "features"
        INPUT_FEATURES: Final[str] = "input_features"
        MANDATORY_FOR_VECTOR_DB: Final[str] = "mandatory_for_vector_db"
        NEW_COLLECTION_DEFAULT_FEATURE_MAPPINGS: Final[str] = "new_collection_default_feature_mappings"
        OUTPUT_FEATURES: Final[str] = "output_features"
        VALID_COLUMNS: Final[str] = "valid_columns"
        VALID_VALUES: Final[str] = "valid_values"

        # Extraction Configuration
        EXPAND_EXTRACTED_DATA: Final[str] = "expand_extracted_data"
        EXTRACT_CUSTOM_SCHEMA: Final[str] = "extract_schema"
        EXTRACT_IMAGES: Final[str] = "extract_images"
        EXTRACT_JSON: Final[str] = "extract_json"
        EXTRACT_TABLES: Final[str] = "extract_tables"
        JSON_SCHEMA: Final[str] = "json_schema"
        LANGUAGES: Final[str] = "languages"
        MAX_WORKERS: Final[str] = "max_workers"
        OCR_MODE: Final[str] = "ocr_mode"
        TEMPLATE: Final[str] = "template"
        USE_PROCESSES: Final[str] = "use_processes"
        USE_TEMPLATE: Final[str] = "use_template"
        USE_VLM_PIPELINE: Final[str] = "use_vlm_pipeline"
        VLM_PRESET: Final[str] = "vlm_preset"
        VLM_PRESET_DEFAULT: Final[str] = "granite_docling"
        VLM_ENGINE_TYPE: Final[str] = "vlm_engine_type"
        VLM_ENGINE_TRANSFORMERS: Final[str] = "transformers"
        VLM_ENGINE_MLX: Final[str] = "mlx"
        VLM_ENGINE_API: Final[str] = "api"
        VLM_ENGINE_API_LMSTUDIO: Final[str] = "api_lmstudio"
        VLM_ENGINE_API_OLLAMA: Final[str] = "api_ollama"
        VLM_ENGINE_API_OPENAI: Final[str] = "api_openai"
        VLM_ENGINE_API_WATSONX: Final[str] = "api_watsonx"
        VLM_API_BASE_URL: Final[str] = "vlm_api_base_url"
        VLM_WATSONX_CONTAINER_KIND: Final[str] = "vlm_watsonx_container_kind"
        VLM_WATSONX_CONTAINER_ID: Final[str] = "vlm_watsonx_container_id"
        VLM_MODEL_NAME: Final[str] = "vlm_model_name"
        VLM_API_KEY: Final[str] = "vlm_api_key"
        VLM_PROVIDER_CONFIG: Final[str] = "vlm_provider_config"

        # Docling-Serve Configuration
        USE_DOCLING_SERVE: Final[str] = "use_docling_serve"
        DOCLING_SERVE_BASE_URL: Final[str] = "docling_serve_base_url"
        DOCLING_SERVE_API_KEY: Final[str] = "docling_serve_api_key"
        DOCLING_SERVE_TIMEOUT: Final[str] = "docling_serve_timeout"
        DOCLING_SERVE_POLL_INTERVAL: Final[str] = "docling_serve_poll_interval"
        DOCLING_SERVE_MAX_RETRIES: Final[str] = "docling_serve_max_retries"
        DOCLING_SERVE_DO_OCR: Final[str] = "docling_serve_do_ocr"  # Deprecated: use DOCLING_SERVE_OCR_PRESET
        DOCLING_SERVE_OCR_ENGINE: Final[str] = "docling_serve_ocr_engine"  # Deprecated: use DOCLING_SERVE_OCR_PRESET
        DOCLING_SERVE_OCR_LANGUAGES: Final[str] = (
            "docling_serve_ocr_languages"  # Deprecated: use DOCLING_SERVE_OCR_LANG
        )
        DOCLING_SERVE_OCR_PRESET: Final[str] = "docling_serve_ocr_preset"
        DOCLING_SERVE_OCR_LANG: Final[str] = "docling_serve_ocr_lang"
        DOCLING_SERVE_PDF_BACKEND: Final[str] = "docling_serve_pdf_backend"
        DOCLING_SERVE_TABLE_MODE: Final[str] = "docling_serve_table_mode"
        DOCLING_SERVE_IMAGE_EXPORT_MODE: Final[str] = "docling_serve_image_export_mode"
        DOCLING_SERVE_OUTPUT_FORMATS: Final[str] = "docling_serve_output_formats"

        # Processing Configuration
        ALWAYS_RETRIEVE_DOCUMENT: Final[str] = "always_retrieve_document"
        COMPUTE_EMBEDDINGS: Final[str] = "compute_embeddings"
        CREATE_EMBEDDED_IMAGES: Final[str] = "create_embedded_images"
        DISABLE_VALIDATION: Final[str] = "disable_validation"
        FILTER_UNKNOWN_LANGUAGE: Final[str] = "filter_unknown_language"
        MAX_FILE_SIZE: Final[str] = "max_file_size"
        PARTIAL_INGEST: Final[str] = "partial_ingest"
        SAMPLING_PERCENTAGE: Final[str] = "sampling_percentage"

        # Model Configuration
        EMBEDDINGS_MODEL_ID: Final[str] = "embeddings_model_id"
        MODEL_ID: Final[str] = "model_id"
        MODEL_NAME: Final[str] = "model_name"

        # Node and Pipeline Configuration
        NODE_METADATA: Final[str] = "node_metadata"
        NODE_PARAMETERS: Final[str] = "node_parameters"
        NODES_METADATA_FILE: Final[str] = "nodes_metadata.json"
        PIPELINE_DETAILS: Final[str] = "pipeline_details"

    class VectorDB:
        """Vector database constants."""

        # Vector Database Connection Configuration
        VECTOR_DB_TYPE: Final[str] = "vector_db_type"
        HOST: Final[str] = "host"
        PORT: Final[str] = "port"
        USERNAME: Final[str] = "username"
        PASSWORD: Final[str] = "password"
        USE_SSL: Final[str] = "use_ssl"
        VERIFY_CERTS: Final[str] = "verify_certs"
        AWS_AUTH: Final[str] = "aws_auth"
        AWS_REGION: Final[str] = "aws_region"
        JWT_TOKEN: Final[str] = "jwt_token"

        # OpenSearch Index Configuration
        CREATE_INDEX: Final[str] = "create_index"
        INDEX_MAPPINGS: Final[str] = "index_mappings"
        INDEX_NAME: Final[str] = "index_name"
        INDEX_SETTINGS: Final[str] = "index_settings"
        INDEX_TYPE: Final[str] = "index_type"
        OPENSEARCH_FEATURE_MAPPINGS: Final[str] = "opensearch_feature_mappings"
        STORED_INDEX_METADATA: Final[str] = "stored_index_metadata"

        # Vector Configuration
        ADD_SPARSE_VECTOR: Final[str] = "add_sparse_vector"
        ADD_SPARSE_VECTOR_DEFAULT: Final[bool] = True
        METRIC_TYPE: Final[str] = "metric_type"
        SEMANTIC_CONFIG: Final[str] = "semantic_config"
        VECTOR_DIMENSION: Final[str] = "vector_dimension"
        VECTOR_SIMILARITY_KEY: Final[str] = "vector_similarity"

        # Vector DB General
        OPENSEARCH: Final[str] = "opensearch"
        VECTOR_DB_NAME: Final[str] = "vector_db_name"
        VECTORDB_PARAMETERS: Final[str] = "vectordb_parameters"

        # OpenSearch-specific parameters
        ENGINE: Final[str] = "engine"
        ALGORITHM: Final[str] = "algorithm"
        SPACE_TYPE: Final[str] = "space_type"
        ENGINE_PARAMETERS: Final[str] = "engine_parameters"

    class Types:
        """Data type constants."""

        # Primitive Data Types
        TYPE_BOOL: Final[str] = "bool"
        TYPE_DOUBLE: Final[str] = "double"
        TYPE_FLOAT: Final[str] = "float"
        TYPE_STRING: Final[str] = "string"

        # Integer Data Types
        TYPE_INT8: Final[str] = "int8"
        TYPE_INT16: Final[str] = "int16"
        TYPE_INT32: Final[str] = "int32"
        TYPE_INT64: Final[str] = "int64"

        # Complex Data Types
        TYPE_JSON: Final[str] = "json"
        TYPE_VECTOR: Final[str] = "vector"
        TYPE_VECTOR_SPARSE: Final[str] = "vector_sparse"

    class Extraction:
        """Document extraction constants."""

        # Extraction Output Fields
        ERROR: Final[str] = "error"
        ERRORS: Final[str] = "errors"
        MESSAGE: Final[str] = "message"
        PAGE_NO: Final[str] = "page_no"
        SEMANTIC_LABEL: Final[str] = "semantic_label"
        STATUS: Final[str] = "status"
        SUCCESS: Final[str] = "success"

        # Extraction Configuration
        KEY: Final[str] = "key"

        # File Extensions
        EXTRACTION_REQUIRED_FILE_EXTENSIONS: Final[list[str]] = [".pdf", ".docx", ".pptx", ".doc", ".ppt"]
        ACCEPTED_FILE_EXTENSIONS: Final[list[str]] = [*EXTRACTION_REQUIRED_FILE_EXTENSIONS, ".md", ".txt"]
        INGEST_FILE_EXTENSIONS: Final[list[str]] = [*ACCEPTED_FILE_EXTENSIONS, ".json"]

    class ExtractionModes:
        """Extraction mode constants for ExtractOperator."""

        # Configuration Parameter Names
        TEXT_EXTRACTION_MODE: Final[str] = "text_extraction_mode"
        ENTITY_EXTRACTION_MODE: Final[str] = "entity_extraction_mode"

        # Text Extraction Mode Values
        TEXT_MODE_DOCLING_LIBRARY: Final[str] = "docling_library"
        TEXT_MODE_DOCLING_SERVE: Final[str] = "docling_serve"

        # Entity Extraction Mode Values
        ENTITY_MODE_OLLAMA: Final[str] = "ollama"
        ENTITY_MODE_DOCLING: Final[str] = "docling"
        ENTITY_MODE_LITELLM: Final[str] = "litellm"
        ENTITY_MODE_NONE: Final[str] = "none"

        # Entity Extraction Configuration
        ENTITY_MODEL_NAME: Final[str] = "entity_model_name"
        ENTITY_TEMPERATURE: Final[str] = "entity_temperature"
        ENTITY_MAX_TOKENS: Final[str] = "entity_max_tokens"
        ENTITY_MAX_DOC_CHARS: Final[str] = "entity_max_doc_chars"

        # Entity Data Expansion (applies to entity extraction only)
        EXPAND_EXTRACTED_DATA: Final[str] = "expand_extracted_data"

        # Document Type Configuration
        DOCUMENT_TYPE_COLUMN: Final[str] = "document_type_column"

    class PIIHAP:
        """PII/HAP constants."""

        # Payload field constants
        INPUT_FIELD: Final[str] = "input"
        DETECTIONS_FIELD: Final[str] = "detections"
        DEFAULT_MODEL_NAME: Final[str] = "granite4"

        # PII Configuration
        PII_AND_HAP_EXTRACT_REDACT: Final[str] = "pii_and_hap_extract_redact"
        PII_FIELD_NAME: Final[str] = "pii"
        PII_LIST: Final[str] = "pii_list"
        PII_REDACTION_CHARACTER_KEY: Final[str] = "redaction_character"
        PII_REDACTION_KEY: Final[str] = "redaction"
        PII_THRESHOLD_KEY: Final[str] = "pii_threshold"

        # HAP Configuration
        HAP_FIELD_NAME: Final[str] = "hap"
        HAP_REDACTION_CHARACTER_KEY: Final[str] = "hap_redaction_character"
        HAP_REDACTION_KEY: Final[str] = "hap_redaction"
        HAP_THRESHOLD_KEY: Final[str] = "hap_threshold"
        MODERATIONS: Final[str] = "moderations"

        # Redaction Configuration
        DEFAULT_REDACTION_CHARACTER_VALUE: Final[str] = "*"
        DEFAULT_REDACTION_VALUE: Final[bool] = False
        EXPECTED_REDACTIONS: Final[str] = "expected_redactions"
        REDACTION_CHARACTER_KEY: Final[str] = "redaction_character"
        REDACTION_KEY: Final[str] = "redaction"
        REDACTION_MASKING_CHARACTER_KEY: Final[str] = "redaction_masking_character"
        REDACTION_REGEX_KEY: Final[str] = "redaction_regex"

    class Filtering:
        """Filtering constants."""

        # Filter Configuration
        AVAILABLE_FOR_FILTER: Final[str] = "available_for_filter"
        FILTER_CRITERIA_JSON: Final[str] = "criteria_json"
        FILTER_CRITERIA_LIST: Final[str] = "criteria_list"
        FILTER_FEATURES_TO_DROP_KEY: Final[str] = "features_to_drop"
        FILTER_LOGICAL_OPERATOR_KEY: Final[str] = "logical_operator"
        INCLUDE_FILTER_KEY: Final[str] = "include_filter"

        # SQL Operations
        SQL_FILTER: Final[str] = "sql_filter"

        # Value Range Filtering
        MAX_VALUE: Final[str] = "max_value"
        MIN_VALUE: Final[str] = "min_value"

    class Processing:
        """Processing constants."""

        # Chunking Configuration
        CHUNK_SIZE: Final[str] = "chunk_size"
        CHUNK_SIZE_DEFAULT: Final[int] = 2048
        CHUNKER: Final[str] = "chunker"
        START_INDEX: Final[str] = "start_index"

        # Embedding Configuration
        COMPUTE_EMBEDDINGS: Final[str] = "compute_embeddings"

        # Deduplication Configuration
        DOC_ID_HASH: Final[str] = "doc_id_hash_column"
        DOC_ID_HASH_DEFAULT: Final[str] = "doc_id_hash"

    class Metadata:
        """Metadata constants."""

        # Document Metadata
        CREATED_TIME: Final[str] = "created_time"
        DOCUMENT_CLASS: Final[str] = "document_class"
        DOCUMENT_CLASS_ID: Final[str] = "document_class_id"
        DOCUMENT_FORMAT: Final[str] = "document_format"
        DOCUMENT_ID: Final[str] = "document_id"
        DOCUMENT_TYPE: Final[str] = "document_type"
        FORMAT: Final[str] = "format"
        LANGUAGE: Final[str] = "language"
        LANGUAGE_SCORE: Final[str] = "language_score"
        LAST_MODIFIED_TIME: Final[str] = "last_modified_time"
        MODIFIED_TIME: Final[str] = "modified_time"
        PROCESSING_STATE: Final[str] = "processing_state"

        # Pipeline Metadata
        METADATA: Final[str] = "metadata"
        NODE_METADATA: Final[str] = "node_metadata"
        PIPELINE_DETAILS: Final[str] = "pipeline_details"
        UNSTRUCTURED_DATA_CURATION_ID: Final[str] = "unstructured_data_curation_id"
        UPDATED_DOCUMENTS: Final[str] = "updated_documents"

        # Tracking and Identification
        TOTAL_PAGES_PROCESSED: Final[str] = "total_pages_converted"

    class Storage:
        """Storage constants."""

        # Storage Configuration
        CONNECTION_PATH: Final[str] = "connection_path"
        COS_ENDPOINT: Final[str] = "cos_endpoint"
        DATASOURCE_TYPE: Final[str] = "datasource_type"
        SCHEMA_NAME: Final[str] = "schema_name"
        STORAGE: Final[str] = "storage"
        TABLE_NAME: Final[str] = "table_name"
        TARGET_STORE: Final[str] = "target_store"

        # Storage Types
        AWS_STORAGE_TYPE: Final[str] = "amazon_s3"
        COS_STORAGE_TYPE: Final[str] = "bmcos_object_storage"
        DEFAULT_S3_REGION: Final[str] = "us-east-1"

        # Output Configuration
        OUTPUT_FEATURES_TO_DROP: Final[str] = "output_features_to_drop"
        OUTPUT_FOLDER: Final[str] = "output_folder"

    class Misc:
        """Miscellaneous constants."""

        # General Identifiers
        CATEGORY: Final[str] = "category"
        COUNT: Final[str] = "count"
        DELETED: Final[str] = "deleted"
        ENTITY: Final[str] = "entity"
        ID: Final[str] = "id"
        IS_PRIMARY: Final[str] = "is_primary"
        LABEL: Final[str] = "label"
        NAME: Final[str] = "name"
        OPERATOR: Final[str] = "operator"
        PAGES: Final[str] = "pages"
        PATH: Final[str] = "path"
        PATHS: Final[str] = "paths"
        PRIMARY: Final[str] = "primary"
        REGEX_KEY: Final[str] = "regex"
        ROWS: Final[str] = "rows"
        SDK: Final[str] = "sdk"
        SHORT_NAME: Final[str] = "short_name"
        SIZE: Final[str] = "size"
        TAGS: Final[str] = "tags"
        URL: Final[str] = "url"
        VALUE: Final[str] = "value"

        # Feature and Transform Constants
        BRANCHING: Final[str] = "branching"
        CONTENT_TYPE: Final[str] = "content_type"
        ENTITIES: Final[str] = "entities"
        FEATURE_NAME: Final[str] = "feature_name"
        INGEST_TYPE: Final[str] = "ingest_type"
        INTERNAL_FEATURE: Final[str] = "internal_feature"
        IS_INTERNAL_FEATURE: Final[str] = "is_internal_feature"
        IS_OPERATOR_AVAILABLE: Final[str] = "is_operator_available"
        JSON_IDENTIFIER: Final[str] = "json_identifier"
        KEY_VALUE: Final[str] = "key_value"
        LINK_CONDITIONS: Final[str] = "link_conditions"
        LINK_ID: Final[str] = "link_id"
        LINK_NAME: Final[str] = "link_name"
        MANDATORY: Final[str] = "mandatory"
        MAPPED_COLUMN_NAME: Final[str] = "mapped_column_name"
        NEW_FEATURE: Final[str] = "new_feature"
        NORMALIZED_VALUE: Final[str] = "normalized_value"
        OLD_FEATURE: Final[str] = "old_feature"
        ORIGINAL_FEATURE: Final[str] = "original_feature"
        TRANSFORM: Final[str] = "transform"
        TYPE: Final[str] = "type"
        USER_CODE: Final[str] = "user_code"
        USER_DATA: Final[str] = "user_data"
        VALUE_DATA_TYPE: Final[str] = "value_data_type"

        # Operator and Collection Constants
        AVAILABLE_COLLECTIONS: Final[str] = "available_collections"
        AVAILABLE_INDICES: Final[str] = "available_indices"
        COLLECTION_COLUMNS: Final[str] = "collection_columns"
        COLUMN_OPTION: Final[str] = "column_option"
        COMPUTE: Final[str] = "compute"
        CORE_OPERATORS_PATH: Final[str] = "core.operators"
        DESIGN_FLOW_OUTPUT_OPERATOR: Final[str] = "design_flow_output"
        DISABLED: Final[str] = "disabled"
        DOCUMENTS: Final[str] = "documents"
        ENABLED: Final[str] = "enabled"
        ENABLED_TEXT: Final[str] = "enabled_text"
        ENTITY_CURATION_OPERATOR: Final[str] = "entity_curation_operator"
        ENTITY_EXTRACT: Final[str] = "extract_entity"
        DOCUMENT_CLASSIFIER: Final[str] = "document_classifier"
        DOCLING_CHUNKER: Final[str] = "docling_chunker"
        ENTITY_STORE_OPERATOR: Final[str] = "entity_store"
        FORCED: Final[str] = "forced"
        FULL_OUTER_JOIN: Final[str] = "full_outer"
        HEARTBEAT_EMBEDDINGS_PUBLISH_SIZE: Final[str] = "embeddings_publish_compute_size"
        INPUT_LINKS: Final[str] = "input_links"
        IS_DATASIFT_SUPPORTED_COLLECTION: Final[str] = "is_datasift_supported_collection"
        IS_DATASIFT_SUPPORTED_INDEX: Final[str] = "is_datasift_supported_index"
        MARKED_UNSTRUCTURED_STATUS: Final[str] = "marked_unstructured_status"
        MAX_BATCH_SIZE_MB: Final[str] = "max_batch_size_mb"
        MERGE_OPTION: Final[str] = "merge_option"
        MERGE_TYPE: Final[str] = "merge_type"
        NEW_COLUMNS: Final[str] = "selected_python_features"
        NODE_IDS: Final[str] = "node_ids"
        REASON: Final[str] = "reason"
        RESOURCE_KEY: Final[str] = "resource_key"
        SELECTED_PYTHON_FEATURES: Final[str] = "selected_python_features"
        SUPPORTED: Final[str] = "supported"
        TOTAL_FILE_COUNT: Final[str] = "file_count"
        UPDATED_FEATURES: Final[str] = "updated_features"

        # Default Values and Limits
        DEFAULT_MAX_THREADS: Final[int] = 25
        DEFAULT_WXAI_API_MAX_WAIT_TIME: Final[int] = 3600
        MAX_CONCURRENT_DELETIONS: Final[int] = 10

        # Operator Paths - organized by OperatorCategory
        ALL_OPERATORS_PATH: Final[list[str]] = [
            "core.operators.extract",
            "core.operators.ingest",
            "core.operators.functional",
            "core.operators.quality",
            "core.operators.vectordb",
            "core.operators.storage",
        ]

    class ContainerKinds:
        CATALOG: Final[str] = "catalog"
        PROJECT: Final[str] = "project"
        SPACE: Final[str] = "space"
