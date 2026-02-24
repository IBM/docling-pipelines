import pathlib
from datasift_opensource.backend.common.util.log import get_logger

logger = get_logger()


def get_filter_extensions(include_filter):

    extensions = None

    if isinstance(include_filter, list):
        return [f".{s.strip()}" if not s.strip().startswith(".") else s.strip() for s in include_filter]

    if include_filter is not None:
        extensions = [f".{x.strip()}" if not x.strip().startswith(".") else x.strip() for x in include_filter.split(',')]
    return extensions


def filter_based_on_extension(file_path, excluded_extensions, included_extensions):
    extn = pathlib.Path(file_path).suffix.lower()
    if excluded_extensions and extn in excluded_extensions:
        logger.info(f'Skipping {file_path} as the file is in the exclusion list')
        return True

    if included_extensions and extn not in included_extensions:
        logger.info(f'Skipping {file_path} as the file type is not supported')
        return True

    return False


def bytes_to_mb(bytes_value):
    """Convert bytes to megabytes (MB)."""
    return bytes_value / 1048576  # 1 MB = 1048576 bytes


def is_doc_previously_processed(*, previously_processed_docs_dict: dict, doc_id, modified_time):
    """Returns True if the doc was processed in the previous job run and the doc is not modified since the last processed time."""
    if not previously_processed_docs_dict:
        return False
    previous_modified_time = previously_processed_docs_dict.get(doc_id, None)
    if previous_modified_time and previous_modified_time >= modified_time:
        return True
    return False
