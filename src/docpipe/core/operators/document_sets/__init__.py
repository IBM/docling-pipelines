"""Document Set Operator - Pipeline integration for document set management.

This operator is a consumer of the assets layer services. It does NOT have its own
ports/adapters - those belong in the assets layer.

Architecture:
    Operator -> Assets Services -> Assets Repositories -> Storage Layer
"""

from docpipe.core.operators.document_sets.document_set_operator import DocumentSetOperator

__all__ = ["DocumentSetOperator"]
