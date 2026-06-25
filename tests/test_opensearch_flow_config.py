"""
Integration tests for OpenSearch flow configuration.

This test suite validates the OpenSearch operator integration within a complete
flow definition, ensuring proper configuration, node connectivity, and feature mappings.
"""

import json
import unittest
from pathlib import Path
from uuid import UUID

from docpipe.core.constants.operator_constants import OperatorConstants


class TestOpenSearchFlow(unittest.TestCase):
    """Test suite for OpenSearch flow configuration validation"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.flow_file = Path(__file__).parent / "flow_with_opensearch.json"

        # Load flow definition
        with open(cls.flow_file) as f:
            cls.flow_data = json.load(f)

        cls.flow_def = cls.flow_data["flow"]
        cls.dag = cls.flow_def["dag"]

        # Find nodes by operator type
        cls.ingest_node = next(n for n in cls.dag if n["operator"] == "ingest_local")
        cls.doc_id_node = next(n for n in cls.dag if n["operator"] == "doc_id_hash")
        cls.chunker_node = next(n for n in cls.dag if n["operator"] == "chunker")
        cls.embeddings_node = next(n for n in cls.dag if n["operator"] == "embeddings")
        cls.opensearch_node = next(n for n in cls.dag if n["operator"] == "opensearch")

    def test_load_flow_definition(self):
        """Test that flow definition loads correctly"""
        self.assertIsNotNone(self.flow_def)
        self.assertIn("OpenSearch Integration Flow", self.flow_def["name"])
        self.assertEqual(len(self.dag), 5)  # ingest, doc_id, chunker, embeddings, opensearch

    def test_flow_node_configuration(self):
        """Test that all nodes are properly configured"""
        # Test ingest node
        self.assertEqual(self.ingest_node["name"], "ingest_documents")
        self.assertEqual(self.ingest_node["operator"], "ingest_local")
        self.assertIn("paths", self.ingest_node["config"])

        # Test OpenSearch node
        self.assertEqual(self.opensearch_node["name"], "store_in_opensearch")
        self.assertEqual(self.opensearch_node["operator"], "opensearch")

        # Verify OpenSearch configuration keys
        config = self.opensearch_node["config"]
        required_keys = [
            OperatorConstants.VectorDB.OPENSEARCH_HOST,
            OperatorConstants.VectorDB.OPENSEARCH_PORT,
            OperatorConstants.VectorDB.INDEX_NAME,
            OperatorConstants.Columns.DOC_ID_COLUMN,
            OperatorConstants.Columns.EMBEDDINGS_COLUMN,
        ]
        for key in required_keys:
            self.assertIn(key, config, f"Missing required key: {key}")

    def test_flow_edges(self):
        """Test that nodes are properly connected"""
        # Test the complete pipeline: ingest → doc_id → chunker → embeddings → opensearch

        # Ingest should output to doc_id
        self.assertEqual(
            self.ingest_node["output_edges"][0]["node_id_ref"],
            self.doc_id_node["id"],
        )

        # Doc_id should receive from ingest and output to chunker
        self.assertEqual(
            self.doc_id_node["input_edges"][0]["node_id_ref"],
            self.ingest_node["id"],
        )
        self.assertEqual(
            self.doc_id_node["output_edges"][0]["node_id_ref"],
            self.chunker_node["id"],
        )

        # Chunker should receive from doc_id and output to embeddings
        self.assertEqual(
            self.chunker_node["input_edges"][0]["node_id_ref"],
            self.doc_id_node["id"],
        )
        self.assertEqual(
            self.chunker_node["output_edges"][0]["node_id_ref"],
            self.embeddings_node["id"],
        )

        # Embeddings should receive from chunker and output to opensearch
        self.assertEqual(
            self.embeddings_node["input_edges"][0]["node_id_ref"],
            self.chunker_node["id"],
        )
        self.assertEqual(
            self.embeddings_node["output_edges"][0]["node_id_ref"],
            self.opensearch_node["id"],
        )

        # OpenSearch should receive input from embeddings
        self.assertEqual(
            self.opensearch_node["input_edges"][0]["node_id_ref"],
            self.embeddings_node["id"],
        )

        # OpenSearch should be terminal node
        self.assertEqual(len(self.opensearch_node["output_edges"]), 0)

    def test_opensearch_feature_mappings(self):
        """Test OpenSearch feature mappings configuration"""
        config = self.opensearch_node["config"]

        # Check available_features
        self.assertIn(OperatorConstants.Config.AVAILABLE_FEATURES, config)
        features = config[OperatorConstants.Config.AVAILABLE_FEATURES]

        # Verify required features (including chunking-related features)
        required_features = [
            "id",
            "name",
            "content",
            "embeddings",
            "doc_id_hash",
            "chunk_sequence_number",
        ]
        for feature in required_features:
            self.assertIn(feature, features)
            self.assertIn("name", features[feature])
            self.assertIn("description", features[feature])
            self.assertIn("type", features[feature])

        # Check feature_mappings
        self.assertIn(OperatorConstants.Config.FEATURE_MAPPINGS, config)
        mappings = config[OperatorConstants.Config.FEATURE_MAPPINGS]

        # Verify mappings exist for key features
        self.assertIn("id", mappings)
        self.assertIn("embeddings", mappings)

    def test_opensearch_engine_configuration(self):
        """Test OpenSearch engine-specific configuration"""
        config = self.opensearch_node["config"]

        # Verify engine configuration
        self.assertEqual(config["engine"], "faiss")
        self.assertEqual(config["space_type"], "l2")

        # Verify HNSW parameters
        self.assertIn("ef_construction", config)
        self.assertIn("m", config)
        self.assertIn("ef_search", config)

        # Verify index settings
        self.assertEqual(config["number_of_shards"], 1)
        self.assertEqual(config["number_of_replicas"], 0)

    def test_flow_global_config(self):
        """Test flow global configuration"""
        global_config = self.flow_def["global_config"]

        self.assertIn("doc_column", global_config)
        self.assertEqual(global_config["doc_column"], "content")
        self.assertIn("disable_validation", global_config)

    def test_opensearch_authentication_config(self):
        """Test OpenSearch authentication configuration"""
        config = self.opensearch_node["config"]

        # Verify authentication settings
        self.assertIn(OperatorConstants.VectorDB.OPENSEARCH_USERNAME, config)
        self.assertIn(OperatorConstants.VectorDB.OPENSEARCH_PASSWORD, config)
        self.assertEqual(config[OperatorConstants.VectorDB.OPENSEARCH_USERNAME], "admin")

        # Verify SSL settings
        self.assertIn(OperatorConstants.VectorDB.OPENSEARCH_USE_SSL, config)
        self.assertIn(OperatorConstants.VectorDB.OPENSEARCH_VERIFY_CERTS, config)

    def test_node_ids_are_valid_uuids(self):
        """Test that all node IDs are valid UUIDs"""
        for node in self.dag:
            node_id = node["id"]
            # Should be at least 36 characters (UUID format)
            self.assertGreaterEqual(
                len(node_id),
                36,
                f"Node ID '{node_id}' is too short (must be at least 36 characters)",
            )

            # Should be a valid UUID format
            try:
                UUID(node_id)
            except ValueError:
                self.fail(f"Node ID '{node_id}' is not a valid UUID")

    def test_opensearch_column_references(self):
        """Test that OpenSearch references correct column names"""
        config = self.opensearch_node["config"]

        # The doc_id_hash operator creates a 'doc_id_hash' column
        # OpenSearch should reference this column
        self.assertEqual(
            config[OperatorConstants.Columns.DOC_ID_COLUMN],
            "doc_id_hash",
            "OpenSearch should reference 'doc_id_hash' column created by doc_id_hash operator",
        )

        # Embeddings column should be specified (created by embeddings operator)
        self.assertEqual(config[OperatorConstants.Columns.EMBEDDINGS_COLUMN], "embeddings")

    def test_flow_storage_and_execution_type(self):
        """Test flow storage and execution configuration"""
        self.assertEqual(self.flow_def["storage"], "in-memory")
        self.assertEqual(self.flow_def["execute_type"], "local")

    def test_opensearch_index_configuration(self):
        """Test OpenSearch index-specific configuration"""
        config = self.opensearch_node["config"]

        # Verify index name
        self.assertEqual(config[OperatorConstants.VectorDB.INDEX_NAME], "docpipe_test_index")

        # Verify connection details
        self.assertEqual(config[OperatorConstants.VectorDB.OPENSEARCH_HOST], "localhost")
        self.assertEqual(config[OperatorConstants.VectorDB.OPENSEARCH_PORT], 9200)


if __name__ == "__main__":
    unittest.main()
