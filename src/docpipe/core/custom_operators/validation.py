"""AST-based static validation for custom operator source files."""

import ast
from pathlib import Path
from typing import Any

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.operators.abstract_operator import OperatorCategory
from docpipe.exceptions.docpipe_exceptions import CustomOperatorInvalidDataException


class ASTOperatorValidator(ast.NodeVisitor):
    """Static AST visitor to validate custom operator source files without executing them."""

    def __init__(self) -> None:
        self.operator_classes: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Inspect class definitions in the AST."""
        # Check if the class inherits from AbstractOperator (by name or attribute)
        is_abstract_operator_subclass = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "AbstractOperator":
                is_abstract_operator_subclass = True
                break
            if isinstance(base, ast.Attribute) and base.attr == "AbstractOperator":
                is_abstract_operator_subclass = True
                break

        if not is_abstract_operator_subclass:
            self.generic_visit(node)
            return

        class_info: dict[str, Any] = {
            "name": node.name,
            "has_transform": False,
            "has_get_metadata_static": False,
            "short_name": None,
            "category": None,
            "owner": None,
        }

        # Inspect class body
        for stmt in node.body:
            # Check class attributes (short_name, category, owner)
            # Handles both plain assignments (`x = ...`) and annotated assignments (`x: T = ...`)
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                if isinstance(stmt, ast.Assign):
                    targets = [t for t in stmt.targets if isinstance(t, ast.Name)]
                    value: ast.expr = stmt.value
                else:  # ast.AnnAssign
                    if stmt.value is None or not isinstance(stmt.target, ast.Name):
                        continue
                    targets = [stmt.target]
                    value = stmt.value

                for target in targets:
                    if target.id == "short_name":
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            class_info["short_name"] = value.value
                        else:
                            raise CustomOperatorInvalidDataException(
                                message="short_name must be a string literal",
                                field_name="short_name",
                            )
                    elif target.id == "category":
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            class_info["category"] = value.value
                        elif isinstance(value, ast.Attribute):
                            class_info["category"] = value.attr
                        else:
                            raise CustomOperatorInvalidDataException(
                                message="category must be a string literal or OperatorCategory enum member",
                                field_name="category",
                            )
                    elif target.id == DocpipeConstants.OWNER_ATTRIBUTE:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            class_info["owner"] = value.value
                        elif isinstance(value, ast.Attribute) and value.attr == "OWNER_CUSTOM":
                            class_info["owner"] = DocpipeConstants.OWNER_CUSTOM
                        else:
                            raise CustomOperatorInvalidDataException(
                                message=f"owner must be '{DocpipeConstants.OWNER_CUSTOM}'",
                                field_name="owner",
                            )

            # Check functions (transform, get_metadata)
            elif isinstance(stmt, ast.FunctionDef):
                if stmt.name == "transform":
                    class_info["has_transform"] = True
                elif stmt.name == "get_metadata":
                    # Check for @staticmethod decorator
                    has_staticmethod = any(
                        (isinstance(dec, ast.Name) and dec.id == "staticmethod")
                        or (isinstance(dec, ast.Attribute) and dec.attr == "staticmethod")
                        for dec in stmt.decorator_list
                    )
                    if has_staticmethod:
                        class_info["has_get_metadata_static"] = True

        self.operator_classes.append(class_info)
        self.generic_visit(node)


def validate_operator_file(*, operator_file_path: Path) -> dict[str, Any]:
    """Validate a custom operator Python file statically using AST.

    Args:
        operator_file_path: Path to the Python file to validate

    Returns:
        Dictionary containing extracted metadata: {"short_name": ..., "category": ..., "class_name": ...}

    Raises:
        CustomOperatorInvalidDataException: If the operator file does not meet contract requirements
    """
    if not operator_file_path.exists():
        raise CustomOperatorInvalidDataException(
            message=f"Operator file does not exist: {operator_file_path}",
            field_name="operator_file",
        )

    try:
        source_code = operator_file_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code, filename=operator_file_path.name)
    except SyntaxError as e:
        raise CustomOperatorInvalidDataException(
            message=f"Syntax error in operator file: {e.msg} (line {e.lineno})",
            field_name="operator_file",
        ) from e
    except Exception as e:
        raise CustomOperatorInvalidDataException(
            message=f"Failed to read or parse operator file: {e}",
            field_name="operator_file",
        ) from e

    validator = ASTOperatorValidator()
    validator.visit(tree)

    if not validator.operator_classes:
        raise CustomOperatorInvalidDataException(
            message="No class inheriting from AbstractOperator found in operator file",
            field_name="operator_file",
        )

    if len(validator.operator_classes) > 1:
        class_names = [c["name"] for c in validator.operator_classes]
        raise CustomOperatorInvalidDataException(
            message=f"Multiple operator classes found ({', '.join(class_names)}). Exactly one is allowed.",
            field_name="operator_file",
        )

    op_info = validator.operator_classes[0]

    # Validate short_name
    if not op_info["short_name"]:
        raise CustomOperatorInvalidDataException(
            message=f"Operator class '{op_info['name']}' must define 'short_name' as a non-empty string literal",
            field_name="short_name",
        )

    # Validate category
    if not op_info["category"]:
        raise CustomOperatorInvalidDataException(
            message=f"Operator class '{op_info['name']}' must define 'category' class attribute",
            field_name="category",
        )

    # Validate category value against OperatorCategory
    valid_categories = {c.value for c in OperatorCategory}
    if op_info["category"] not in valid_categories and op_info["category"] not in [c.name for c in OperatorCategory]:
        raise CustomOperatorInvalidDataException(
            message=f"Invalid category '{op_info['category']}'. Must be one of: {', '.join(sorted(valid_categories))}",
            field_name="category",
        )

    # Normalize category value
    category_val = (
        op_info["category"]
        if op_info["category"] in valid_categories
        else getattr(OperatorCategory, op_info["category"]).value
    )

    # Validate owner
    if op_info["owner"] != DocpipeConstants.OWNER_CUSTOM:
        raise CustomOperatorInvalidDataException(
            message=(
                f"Operator class '{op_info['name']}' must set owner='{DocpipeConstants.OWNER_CUSTOM}', "
                f"got '{op_info['owner']}'"
            ),
            field_name="owner",
        )

    # Validate required methods
    if not op_info["has_transform"]:
        raise CustomOperatorInvalidDataException(
            message=f"Operator class '{op_info['name']}' must implement 'transform' method",
            field_name="transform",
        )

    if not op_info["has_get_metadata_static"]:
        raise CustomOperatorInvalidDataException(
            message=f"Operator class '{op_info['name']}' must implement 'get_metadata' as a @staticmethod",
            field_name="get_metadata",
        )

    return {
        "short_name": op_info["short_name"],
        "category": category_val,
        "class_name": op_info["name"],
    }
