from typing import List, Dict, Any, Union

from pydantic import BaseModel, Field

file_upload_response_example = {
    "success": True,
    "classes": ["MyClass", "AnotherClass", "HelperClass"],
    "imports": ["import os", "import sys", "import math"],
    "from_imports": ["from datetime import datetime", "from collections import defaultdict"],
    "operator_path_dependency_tree": {
        "path/to/operator1": {
            "dependency1": {"type": "operator", "name": "operatorA"},
            "dependency2": {"type": "operator", "name": "operatorB"}
        },
        "path/to/operator2": None
    },
    "dependency_path_dependency_tree": {
        "path/to/dependency1": {
            "dep1": {"type": "path", "path": "path/to/other/file"},
            "dep2": {"type": "path", "path": "path/to/yet/another/file"}
        },
        "path/to/dependency2": None
    }
}

directory_tree_response_example = {
    "root": {
        "subdir1": {},
        "subdir2": {
            "subsubdir1": {}
        },
        "empty_dir": {}
    }
}

directory_tree_delete_response_example = {
    "message": "Path 'base_loc/custom_op' successfully deleted."
}

class StatusResponse(BaseModel):
    status: str
    message: str

class FileUploadResponse(BaseModel):
    success: bool = Field(
        title="Success Indicator",
        description="Indicates whether the file upload was successful. True if successful, False otherwise."
    )
    classes: List[str] = Field(
        default=None,
        title="List of Classes",
        description="A list of class names associated with the uploaded file. This is optional and can contain up to 50 items.",
        min_items=0,
        max_items=50
    )
    imports: List[str] = Field(
        default=None,
        title="List of Imports",
        description="A list of import statements extracted from the uploaded file. This is optional and can contain up to 50 items.",
        min_items=0,
        max_items=50
    )
    from_imports: List[str] = Field(
        default=None,
        title="List of From Imports",
        description="A list of import statements extracted from the uploaded file. This is optional and can contain up to 50 items.",
        min_items=0,
        max_items=50
    )
    custom_operator_dependency_tree: Dict[str, Dict[str, dict]] = Field(
        default=None,
        title="Operator Path Dependency Tree",
        description="A dictionary representing a tree-like structure of dependencies between operators utilities in the uploaded file."
    )
    custom_operator_package_tree: Dict[str, Dict[str, dict]] = Field(
        default=None,
        title="Dependency Path Dependency Tree",
        description="A dictionary representing packages provided."
    )
    status_id: str = Field(
        default=None,
        title="Status ID To Track Validation",
        description="The status id to track operation, specifically for Saas runtime executions."
    )

    class Config:
        json_schema_extra = {
            "description": "This model defines the response body for uploading a file custom operator",
            "example": file_upload_response_example
        }


class DirectoryTree(BaseModel):
    """Represents a hierarchical directory structure."""

    directory_tree: Dict[str, Dict[str, Any]] = Field(
        default={},
        title="Directory Tree",
        description="A nested dictionary representing a directory tree. "
                    "Each key is a folder name, and the value is another dictionary (subdirectory). "
                    "Empty folders are represented as empty dictionaries.",
        example=directory_tree_response_example
    )

    class Config:
        json_schema_extra = {
            "title": "Directory Tree",
            "description": "Represents a hierarchical directory structure.",
        }


class DirectoryTreeDelete(BaseModel):
    "Represents response schema of delete operation"
    message: str = Field(
        default={},
        title="Directory Tree Delete Response",
        description="The response that we get from deleting the directory tree",
        example=directory_tree_delete_response_example
    )

    class Config:
        json_schema_extra = {
            "title": "Directory Tree Delete Response",
            "description": "Represents response schema of delete operation",
        }
