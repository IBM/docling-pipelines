"""Unit tests for DataAccessUtils."""

from typing import Any
from unittest.mock import patch

from docpipe.core.data_access.data_access_utils import DataAccessConstants, DataAccessUtils


class TestAddNodeNameToOutputFolder:
    def test_no_storage_type_returns_early(self):
        params = {"data_config": {"output_folder": "/tmp/out"}}
        DataAccessUtils.add_node_name_to_output_folder(params=params, node_name="my_node")
        # No modification
        assert params["data_config"]["output_folder"] == "/tmp/out"

    def test_unknown_storage_type_returns_early(self):
        params = {DataAccessConstants.DATA_STORAGE_TYPE: "unknown"}
        DataAccessUtils.add_node_name_to_output_folder(params=params, node_name="node")
        # No crash, no modification

    def test_memory_storage_appends_node_name(self):
        params = {
            DataAccessConstants.DATA_STORAGE_TYPE: DataAccessConstants.MEMORY,
            "data_config": {"output_folder": "/tmp/out"},
        }
        DataAccessUtils.add_node_name_to_output_folder(params=params, node_name="my node!")
        assert params["data_config"]["output_folder"] == "/tmp/out/my_node_"
        assert params["data_config"]["cache"] is True

    def test_local_storage_appends_node_name(self):
        params = {
            DataAccessConstants.DATA_STORAGE_TYPE: DataAccessConstants.LOCAL,
            "data_local_config": {"output_folder": "/data"},
        }
        DataAccessUtils.add_node_name_to_output_folder(params=params, node_name="step")
        assert params["data_local_config"]["output_folder"] == "/data/step"

    def test_appends_batch_num_when_present(self):
        params = {
            DataAccessConstants.DATA_STORAGE_TYPE: DataAccessConstants.MEMORY,
            "data_config": {"output_folder": "/out"},
            "batch_num": 3,
        }
        DataAccessUtils.add_node_name_to_output_folder(params=params, node_name="node")
        assert params["data_config"]["output_folder"] == "/out/node/3"

    def test_no_config_key_in_params(self):
        params = {DataAccessConstants.DATA_STORAGE_TYPE: DataAccessConstants.MEMORY}
        # config key present but no value → should not crash
        DataAccessUtils.add_node_name_to_output_folder(params=params, node_name="node")


class TestAddIntermediateStorageConfig:
    def test_local_storage_calls_local_config(self):
        config = {DataAccessConstants.DATA_STORAGE_TYPE: DataAccessConstants.LOCAL}
        with patch.object(DataAccessUtils, "add_data_local_config_for_cpd") as mock:
            DataAccessUtils.add_intermediate_storage_config(config, "job1", "run1")
            mock.assert_called_once_with(config=config, job_id="job1", job_run_id="run1")

    def test_memory_storage_sets_data_config(self):
        config = {DataAccessConstants.DATA_STORAGE_TYPE: DataAccessConstants.MEMORY}
        DataAccessUtils.add_intermediate_storage_config(config, "job1", "run1")
        assert config["data_config"]["da_class"] == "data_processing.data_access.DataAccessMemory"

    def test_memory_storage_clears_local_config(self):
        config: dict[str, Any] = {
            DataAccessConstants.DATA_STORAGE_TYPE: DataAccessConstants.MEMORY,
            "data_local_config": {"something": True},
        }
        DataAccessUtils.add_intermediate_storage_config(config, "j", "r")
        assert config["data_local_config"] is None


class TestAddDataLocalConfigForCpd:
    def test_creates_local_config_when_absent(self):
        config: dict[str, Any] = {}
        with patch("docpipe.core.data_access.data_access_utils.get_data_path", return_value="/data"):
            DataAccessUtils.add_data_local_config_for_cpd(config=config, job_id="j1", job_run_id="r1")
        assert config["data_local_config"]["output_folder"] == "/data/j1/r1/data"
        assert config["data_local_config"]["input_folder"] == "UNUSED"
        assert config["data_config"] is None

    def test_uses_existing_local_config_output_folder(self):
        config = {"data_local_config": {"output_folder": "/custom"}}
        DataAccessUtils.add_data_local_config_for_cpd(config=config, job_id="j", job_run_id="r")
        assert config["data_local_config"]["output_folder"] == "/custom"
        assert config["data_local_config"]["input_folder"] == "UNUSED"
        assert config["data_local_config"]["da_class"] == "docpipe.core.data_access.DocpipeDataAccessLocal"
