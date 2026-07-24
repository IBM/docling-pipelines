"""Shared fixtures for IngestSourceOperator tests."""

import pyarrow as pa
import pytest
from langchain_core.documents import Document


@pytest.fixture
def mock_documents():
    """Sample LangChain documents for testing ingest operators."""
    return [
        Document(
            page_content="This is the first document content.",
            metadata={"source": "file1.txt", "page": 1},
        ),
        Document(
            page_content="This is the second document content.",
            metadata={"source": "file2.txt", "page": 1},
        ),
        Document(
            page_content="This is the third document content.",
            metadata={"source": "file3.txt", "page": 2},
        ),
    ]


@pytest.fixture
def empty_input_table():
    """Empty PyArrow table used as the trigger input for ingest operators."""
    return pa.Table.from_arrays([])
