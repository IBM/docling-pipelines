"""Invalid operator missing transform method."""

from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory


class InvalidOperatorNoTransform(AbstractOperator):
    """Invalid operator without transform method."""

    short_name: str = "invalid_no_transform"
    category: OperatorCategory = OperatorCategory.Functional

    def __init__(self, config: dict):
        super().__init__(config)

    def get_metadata(self) -> dict:
        return {"label": "Invalid Operator"}

    def get_required_features(self) -> list:
        return []
