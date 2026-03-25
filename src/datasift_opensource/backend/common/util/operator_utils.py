import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

import pyarrow as pa
from charset_normalizer import from_bytes
from docling.document_converter import DocumentConverter
from docling_core.types.doc import TableItem, PictureItem
from pyarrow import Table

from common.constants.constants import internal_metrics
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import (
    FlowValidationException,
    ValidationAlert,
)
from common.exceptions.error_messages import ValidationCodeMessages
from common.util.log import get_logger

hash_functions = hashlib.sha3_512

def prepare_document_content_fetch(
    table: pa.Table
) -> list:
    """
    Prepare to fetch document content from a PyArrow table row.
    
    Args:
        table: PyArrow table containing document data
        
    Returns:
        returns a list of dicts with keys: idx, doc_id, doc_name, binary_content or error
        
    """
    doc_tasks = []
    for row_idx in range(table.num_rows):
        try:
            doc_id = (
                table[OperatorConstants.Columns.ID][row_idx].as_py()
                if OperatorConstants.Columns.ID in table.column_names
                else f"doc_{row_idx}"
            )
            doc_name = (
                table[OperatorConstants.Columns.NAME][row_idx].as_py()
                if OperatorConstants.Columns.NAME in table.column_names
                else f"document_{row_idx}"
            )

            # Get binary content
            if OperatorConstants.Columns.BINARY_CONTENT in table.column_names:
                binary_content = table[OperatorConstants.Columns.BINARY_CONTENT][row_idx].as_py()
            else:
                if OperatorConstants.Columns.PATH in table.column_names:
                    file_path = table[OperatorConstants.Columns.PATH][row_idx].as_py()
                    with open(file_path, "rb") as f:
                        binary_content = f.read()
                else:
                    raise ValueError(f"No binary content or path available for document {doc_name}")

            doc_tasks.append({"idx": row_idx, "doc_id": doc_id, "doc_name": doc_name, "binary_content": binary_content})
        except Exception as e:
            logger.error(f"Error preparing document at index {row_idx}: {e!s}")
            doc_tasks.append({"idx": row_idx, "doc_id": str(row_idx), "doc_name": f"document_{row_idx}", "error": str(e)})
    return doc_tasks

def get_optimal_workers(is_cpu_intensive: bool = False) -> int:
    """
    Determine optimal number of workers based on system resources.
    Cross-platform compatible: Works on Linux, Windows, and macOS.

    Returns:
        Optimal number of workers
    """
    import platform

    cpu_count = os.cpu_count() or 4
    system = platform.system()

    # For I/O-bound tasks (document extraction), use more workers than CPU count
    # For CPU-bound tasks (template extraction with VLM), use CPU count
    if is_cpu_intensive:
        # Template extraction is more CPU-intensive (uses VLM models)
        optimal = max(1, cpu_count - 1)  # Leave one CPU free for system
    else:
        # Basic extraction is more I/O-bound (file reading, PDF parsing)
        optimal = min(cpu_count * 2, 16)  # Cap at 16 to avoid excessive threads

    logger.info(f"Auto-detected optimal workers: {optimal} (CPU count: {cpu_count}, OS: {system})")
    return optimal

def detect_extension_from_bytes(binary_content: bytes) -> str:
    """
    Detect the file extension from the magic bytes of binary content.

    Used when the document name / path has no extension (e.g. a cloud URL).
    Returns a dotted extension string such as '.pdf', '.docx', or '' if unknown.
    """
    if not binary_content:
        return ""

    # PDF: %PDF
    if binary_content[:4] == b"%PDF":
        return ".pdf"

    # ZIP-based Office formats (docx, xlsx, pptx) and plain ZIP
    if binary_content[:2] == b"PK":
        # Inspect the central directory for known Office content-type markers
        content_sample = binary_content[:2048]
        if b"word/" in content_sample:
            return ".docx"
        if b"xl/" in content_sample:
            return ".xlsx"
        if b"ppt/" in content_sample:
            return ".pptx"
        return ".docx"  # generic ZIP-based Office fallback

    # Legacy OLE2 Office formats (doc, xls, ppt)
    if binary_content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return ".doc"

    # PNG
    if binary_content[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"

    # JPEG
    if binary_content[:3] == b"\xff\xd8\xff":
        return ".jpg"

    # GIF
    if binary_content[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"

    # TIFF
    if binary_content[:4] in (b"II*\x00", b"MM\x00*"):
        return ".tiff"

    # HTML
    content_start = binary_content[:512].lstrip()
    if content_start[:9].lower() == b"<!doctype" or content_start[:5].lower() == b"<html":
        return ".html"

    # Plain text / markdown fallback — try decoding as UTF-8
    try:
        binary_content[:512].decode("utf-8")
        return ".txt"
    except UnicodeDecodeError:
        pass

    return ""


def extract_basic_worker(
    file_path: str, binary_content: bytes, extract_tables: bool, extract_images: bool
) -> dict[str, Any]:
    """
    Worker function for basic extraction - designed to run in parallel.

    Args:
        file_path: Path to the document file
        binary_content: Binary content of the document
        extract_tables: Whether to extract tables
        extract_images: Whether to extract images

    Returns:
        Dictionary containing extracted markdown content
    """
    logger.info(f"Processing file: {file_path}")

    # Determine the effective file extension.
    # When file_path is a URL or has no extension (e.g. from IngestSourceOperator),
    # fall back to magic-byte detection so Docling receives a correctly-named temp file.
    file_suffix = Path(file_path).suffix.lower()
    if not file_suffix:
        file_suffix = detect_extension_from_bytes(binary_content)

    # Handle .txt and .md files specially (Docling cannot process them)
    if file_suffix in [".txt", ".md"]:
        try:
            # Decode text content
            try:
                raw_text = binary_content.decode("utf-8")
            except UnicodeDecodeError:
                # Try other encodings if UTF-8 fails
                try:
                    raw_text = binary_content.decode("latin-1")
                except Exception as e:
                    logger.error(f"Failed to decode text file {file_path}: {e!s}")
                    return {
                        OperatorConstants.Extraction.SUCCESS: False,
                        OperatorConstants.Extraction.ERROR: f"Failed to decode text: {e!s}",
                        OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
                    }

            # Use the raw text as markdown (since it's already plain text)
            markdown_text = raw_text

            logger.info(f"Completed extraction for text file: {file_path}")

            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: markdown_text,
                OperatorConstants.Columns.TABLES: [],  # No tables in plain text
                OperatorConstants.Columns.IMAGES: [],  # No images in plain text
                OperatorConstants.Metadata.METADATA: {
                    "table_count": 0,
                    "image_count": 0,
                    "char_count": len(markdown_text),
                    "is_text_file": True,
                },
            }
        except Exception as e:
            logger.error(f"Error processing text file {file_path}: {e!s}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: str(e),
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
            }
    # For non-text files, use Docling's DocumentConverter
    # Use context manager with delete=True to ensure cleanup even if process crashes
    with tempfile.NamedTemporaryFile(delete=True, suffix=file_suffix) as tmp_file:
        tmp_file.write(binary_content)
        tmp_file.flush()  # Ensure content is written to disk
        tmp_path = tmp_file.name

        try:
            # Initialize converter (each worker gets its own instance)
            converter = DocumentConverter()

            # Convert document
            result = converter.convert(tmp_path)

            # Export to markdown
            markdown_text = result.document.export_to_markdown()

            # Extract tables
            tables = []
            if extract_tables:
                for item, level in result.document.iterate_items():
                    if isinstance(item, TableItem):
                        table_df = item.export_to_dataframe()
                        tables.append({"ref": item.self_ref, "data": table_df.to_dict() if table_df is not None else None})

            # Extract images
            images = []
            if extract_images:
                for item, level in result.document.iterate_items():
                    if isinstance(item, PictureItem):
                        images.append({"ref": item.self_ref, "caption": getattr(item, "caption", None)})

            logger.info(f"Completed extraction for {file_path}")

            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: markdown_text,
                OperatorConstants.Columns.TABLES: tables,
                OperatorConstants.Columns.IMAGES: images,
                OperatorConstants.Metadata.METADATA: {
                    "table_count": len(tables),
                    "image_count": len(images),
                    "char_count": len(markdown_text),
                },
            }
        except Exception as e:
            logger.error(f"Error extracting content from {file_path}: {e!s}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: str(e),
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
            }
    # File is automatically deleted when context manager exits


logger = get_logger()


def remove_rows(*, table: pa.Table, remove_row_idx: list) -> pa.Table:
    """
    Removes the rows for the given list of indexes in remove_row_idx from the table
    """
    indices_to_keep = [i for i in range(table.num_rows) if i not in remove_row_idx]
    return table.take(pa.array(indices_to_keep, type=pa.int64()))


def remove_all_rows(*, table: pa.Table, remove_row_id: list):
    """
    Removes all the rows for the given list of ID from the table
    """
    input_dict = table.to_pydict()

    remove_idx = []
    for idx, doc_id in enumerate(input_dict[OperatorConstants.Columns.ID]):
        if doc_id in remove_row_id:
            remove_idx.append(idx)

    table = remove_rows(table=table, remove_row_idx=remove_idx)

    return table


def find_doc_count(*, table: pa.Table) -> int:
    if not table:
        return 0
    if table.num_rows == 0:
        return 0
    if OperatorConstants.Columns.NAME in table.column_names:
        return len(table[OperatorConstants.Columns.NAME].unique())

    return table.num_rows


def find_doc_count_from_tables(*, tables: list[pa.Table]) -> int:
    doc_names = set()
    for table in tables:
        if table.num_rows > 0:
            doc_names.update(table[OperatorConstants.Columns.NAME].unique())
    return len(doc_names)


def validate_link_name(*, link_name: str, existing_link_names: set, errors: list):
    if not link_name:
        errors.append("Missing link name. Please provide a link name.")
        return
    key = link_name.lower()
    if key in existing_link_names:
        errors.append(f"Duplicate link name found: '{link_name}'. Link names must be unique.")
    else:
        existing_link_names.add(key)


def doc_id_hash(*, content) -> str:
    """
    Uses the content and adds a column with unique hash
    """
    hash_fn = hash_functions
    hashed_value = hash_fn(content.encode())

    return hashed_value.hexdigest()


def decode_binary_content(*, binary_content: bytes) -> str:
    """
    Decodes binary content into a string using detected encoding or defaults to UTF-8.

    Args:
        binary_content (bytes): The binary data to decode.

    Returns:
        str: Decoded string, using detected encoding or UTF-8 with replacements on failure.
    """
    detected_encoding = from_bytes(binary_content).best()
    if detected_encoding and detected_encoding.encoding:
        return str(detected_encoding)
    else:  # pragma: no cover
        # Fallback to a default encoding if detection failsF
        return binary_content.decode("utf-8", errors="replace")


def upsert_fields_in_schema(*, schema: pa.Schema, updates: dict[str, pa.DataType]) -> pa.Schema:
    """
    Returns a new schema with updated or added fields:
    - If a field exists in the schema and is in `updates`, its type is replaced.
    - If a field does not exist and is in `updates`, it is added.
    """
    existing_field_names = set(schema.names)
    updated_fields = []

    for field in schema:
        if field.name in updates:
            updated_fields.append(pa.field(field.name, updates[field.name]))
        else:
            updated_fields.append(field)

    for name, dtype in updates.items():
        if name not in existing_field_names:
            updated_fields.append(pa.field(name, dtype))

    return pa.schema(updated_fields)


def remove_internal_metrics_from_metadata(metadata) -> dict:
    internal_metadata = {}
    for key in list(metadata.keys()):
        if key in internal_metrics:
            internal_metadata[key] = metadata.pop(key)
    return internal_metadata


def import_transforms_code_from_file(transforms_path: Path) -> dict[str, any]:
    transforms_code = {}

    # Normalize path for Spark runtime when running from zip file
    # In Spark, the zip file is extracted to /datasift/storage/job-assets/
    # So we need to replace the zip path with the extracted location
    normalized_path = str(transforms_path)

    # Replace zip path with extracted location (similar to doc_quality.py)
    if "./datasift.zip" in normalized_path:
        normalized_path = normalized_path.replace("./datasift.zip", "/datasift/storage/job-assets")
    elif "datasift.zip" in normalized_path:
        normalized_path = normalized_path.replace("datasift.zip", "/datasift/storage/job-assets")
    else:
        logger.info(f"[DEBUG] import_transforms_code_from_file - No zip path found, using original: {normalized_path}")

    normalized_path = Path(normalized_path)
    for transformation_code_file in os.listdir(normalized_path):
        if transformation_code_file.endswith(".py"):
            transforms_code[transformation_code_file.replace(".py", "")] = open(
                normalized_path / transformation_code_file, encoding="utf-8"
            ).read()
        if transformation_code_file.endswith(".json"):
            transforms_code[transformation_code_file] = open(
                normalized_path / transformation_code_file, encoding="utf-8"
            ).read()
    return transforms_code


def drop_features_from_table(output_features_to_drop: list, table: Table):
    """

    Parameters
    ----------
    output_features_to_drop
    table

    Returns
    -------

    """
    # Get existing column names
    existing_columns = set(table.schema.names)
    # Filter to only columns that actually exist
    valid_columns_to_drop = [col for col in output_features_to_drop if col in existing_columns]
    # Drop only valid columns
    if valid_columns_to_drop:
        return table.drop_columns(valid_columns_to_drop)
    return table  # Return original table if no valid columns to drop


def rename_features_and_save_original(
    *, updated_features: list | None = None, input_features: dict | Table | None = None
) -> Any | None:
    if not input_features or not updated_features:
        return None

    existing_features = set(input_features.schema.names) if isinstance(input_features, Table) else input_features

    rename_map = _build_rename_map(updated_features=updated_features, existing_features=existing_features)

    _validate_existing_features(rename_map, existing_features)

    if isinstance(input_features, Table):
        return _rename_table(input_features, rename_map)

    if isinstance(input_features, dict):
        _validate_dict_mandatory(rename_map, input_features)
        _apply_dict_rename(input_features, rename_map)


def _build_rename_map(*, updated_features: list | None = None, existing_features: set):
    rename_map: dict[str, str] = {}
    seen_old: set = set()
    seen_new: set = set()

    for idx, upd in enumerate(updated_features):
        _validate_feature(upd, idx)

        old_name, new_name = (
            upd[OperatorConstants.Misc.OLD_FEATURE],
            upd[OperatorConstants.Misc.NEW_FEATURE],
        )

        _check_duplicate(
            old_name=old_name,
            new_name=new_name,
            idx=idx,
            seen_old=seen_old,
            seen_new=seen_new,
            input_features=existing_features,
        )

        seen_old.add(old_name)
        seen_new.add(new_name)
        rename_map[old_name] = new_name

    return rename_map


def _validate_feature(upd: dict, idx: int):
    if not isinstance(upd, dict):
        _raise_value_error(f"Each item in updated_features must be a dict. Item at index {idx} is {type(upd)}")

    old_name = upd.get(OperatorConstants.Misc.OLD_FEATURE)
    new_name = upd.get(OperatorConstants.Misc.NEW_FEATURE)

    if old_name is None or new_name is None:
        error = f"Each mapping dict must contain 'old_feature' and 'new_feature'. Got: {upd}"
        _raise_value_error(error)

    if not isinstance(old_name, str) or not isinstance(new_name, str):
        error = (
            f"Both old_feature and new_feature must be strings. "
            f"Got types: old_feature={type(old_name)}, new_feature={type(new_name)} in {upd}"
        )
        _raise_value_error(error)


def _check_duplicate(
    *,
    old_name: str,
    new_name: str,
    idx: int,
    seen_old: set,
    seen_new: set,
    input_features: Any,
):
    if old_name in seen_old:
        _raise_value_error(f"Duplicate mapping for old_feature '{old_name}' at index {idx}")

    if new_name in seen_new or new_name in seen_old or new_name in input_features:
        _raise_value_error(
            f"Duplicate name for new feature '{new_name}'. trying to rename same as first occurrence' or feature name already exists'{old_name}'"
        )


def _validate_existing_features(rename_map: dict[str, str], existing_features: set):
    missing_old = [old for old in rename_map if old not in existing_features]
    if missing_old:
        error = f"Cannot rename non-existing column(s): {missing_old}"
        logger.error(error, stack_info=True, exc_info=True)
        raise KeyError(error)


def _rename_table(input_table: Table, rename_map: dict[str, str]) -> Table:
    new_names_ordered = [rename_map.get(name, name) for name in input_table.schema.names]

    if len(new_names_ordered) != len(set(new_names_ordered)):
        dup = {name for name in new_names_ordered if new_names_ordered.count(name) > 1}
        raise ValueError(f"After rename new column names would have duplicates: {dup}")
    try:
        return input_table.rename_columns(new_names_ordered)
    except Exception as e:
        logger.error(str(e), stack_info=True, exc_info=True)
        raise


def _validate_dict_mandatory(rename_map: dict[str, str], input_features: dict):
    mandatory_features = get_mandatory_features(check_features=list(rename_map.keys()), input_features=input_features)
    if mandatory_features:
        raise FlowValidationException(
            message="Invalid rename attempted",
            errors=[
                ValidationAlert(
                    message_code=ValidationCodeMessages.RENAMING_MANDATORY_FEATURES.name,
                    message=ValidationCodeMessages.RENAMING_MANDATORY_FEATURES.value.format(
                        mandatory_features=mandatory_features
                    ),
                )
            ],
        )


def _apply_dict_rename(input_features: dict, rename_map: dict[str, str]):
    for old_name, new_name in rename_map.items():
        feature = input_features.pop(old_name, None)

        if feature is None:
            continue

        if OperatorConstants.Misc.ORIGINAL_FEATURE not in feature:
            feature[OperatorConstants.Misc.ORIGINAL_FEATURE] = old_name

        input_features[new_name] = feature


def get_mandatory_features(*, check_features: list, input_features: dict):
    if not check_features or not input_features:
        return []

    mandatory_features = [
        feature
        for feature, value in input_features.items()
        if feature in check_features and OperatorConstants.Misc.MANDATORY in value.get(OperatorConstants.Misc.TAGS, [])
    ]
    return mandatory_features


def _raise_value_error(msg: str):
    logger.error(msg, stack_info=True, exc_info=True)
    raise ValueError(msg)


def validate_filter_criteria(*, criteria_list, criteria_json) -> tuple[bool, bool]:
    """
    Validates filter criteria for operators that use criteria_list and criteria_json.

    Args:
        criteria_list: List of filter criteria strings
        criteria_json: Dictionary of filter criteria in JSON format. Can be either:
                      - Group format: {'logical_operator': 'AND'|'OR', 'criteria_list': [...]}
                      - Leaf format: {'variable': 'col', 'operator': '=', 'value': 'x'}

    Returns:
        Tuple of (criteria_valid, json_valid)
        - criteria_valid: Whether criteria_list has valid non-empty content
        - json_valid: Whether criteria_json has valid content (leaf condition or non-empty group with valid criteria)
    """
    # Check if criteria_list has valid non-empty content
    criteria_valid = isinstance(criteria_list, list) and any(c and c.strip() for c in criteria_list)

    # Check if criteria_json has valid content
    json_valid = _validate_criteria_json(criteria_json=criteria_json)

    return criteria_valid, json_valid


def _validate_criteria_json(*, criteria_json) -> bool:
    """
    Recursively validates criteria_json structure (matches runtime behavior).

    Args:
        criteria_json: Dictionary of filter criteria in JSON format

    Returns:
        bool: True if criteria_json is valid (leaf condition or group with ALL valid conditions/nested groups)
    """
    if not criteria_json or not isinstance(criteria_json, dict):
        return False

    # Check if it's a leaf condition (has 'variable' and 'operator')
    if "variable" in criteria_json and "operator" in criteria_json:
        return True

    # Check if it's a group with criteria_list
    if "criteria_list" in criteria_json:
        json_criteria_list = criteria_json.get("criteria_list", [])
        if not isinstance(json_criteria_list, list) or len(json_criteria_list) == 0:
            return False

        # ALL items must be valid (either leaf conditions or nested groups)
        # Recursively validate each item to match runtime behavior
        return all(
            isinstance(item, dict) and _validate_criteria_json(criteria_json=item) for item in json_criteria_list
        )

    return False
