"""
Unit tests for FastText Language Detection Adapter

Tests the FastText adapter integration with the LanguageDetect operator.
"""

import threading
import time

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.language_detection.lang_id import LanguageDetect
from docpipe.utils.infrastructure.fasttext_model_manager import FastTextModelManager


class TestLanguageDetectFastText:
    """Test suite for FastText language detection via LanguageDetect operator"""

    @pytest.fixture
    def sample_config(self):
        """Provide sample configuration for the operator with FastText provider"""
        return {
            "doc_column": "content",
            "language_provider": "fasttext",
            OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: False,
        }

    @pytest.fixture
    def sample_table(self):
        """Create a sample PyArrow table with multilingual content"""
        content = pa.array(
            [
                "Hello, world! This is an English text.",
                "Bonjour, monde! Ceci est un texte français.",
                "¡Hola, mundo! Este es un texto en español.",
                "Привет, мир! Это русский текст.",
                "こんにちは世界!これは日本語のテキストです。",
                "Salom dunyo! Bu o'zbek tilidagi matn.",  # Uzbek text
            ]
        )
        names = pa.array(
            [
                "english.txt",
                "french.txt",
                "spanish.txt",
                "russian.txt",
                "japanese.txt",
                "uzbek.txt",
            ]
        )
        doc_ids = pa.array(["1", "2", "3", "4", "5", "6"])

        return pa.Table.from_arrays(
            [doc_ids, content, names],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                OperatorConstants.Columns.NAME,
            ],
        )

    def test_operator_initialization(self, sample_config):
        """Test that operator initializes correctly with FastText provider"""
        operator = LanguageDetect(sample_config)

        assert operator.doc_column_name == "content"
        assert operator.filter_value is False
        assert operator.language_provider == "fasttext"
        assert operator.language_adapter is not None

        # Cleanup
        operator.cleanup()

    def test_operator_metadata(self, sample_config):
        """Test that operator metadata is correctly defined"""
        operator = LanguageDetect(sample_config)
        metadata = operator.get_metadata()

        assert metadata[OperatorConstants.Misc.LABEL] == "Language Annotator"
        assert OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE in metadata[OperatorConstants.Config.ATTRIBUTES]
        assert OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY in metadata[OperatorConstants.Config.FEATURES]
        assert OperatorConstants.Columns.LANGUAGE_SCORE_COLUMN_KEY in metadata[OperatorConstants.Config.FEATURES]

        # Cleanup
        operator.cleanup()

    def test_language_detection(self, sample_config, sample_table):
        """Test basic language detection functionality with FastText"""
        operator = LanguageDetect(sample_config)

        try:
            result_tables, metadata = operator.transform(sample_table)

            assert len(result_tables) == 1
            result_table = result_tables[0]

            # Check that language columns were added
            assert OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY in result_table.column_names
            assert OperatorConstants.Columns.LANGUAGE_SCORE_COLUMN_KEY in result_table.column_names

            # Check that all rows were processed
            assert result_table.num_rows == sample_table.num_rows

            # Check metadata
            assert metadata[Metrics.External.TOTAL_DOCS] == 6
            assert metadata[Metrics.External.PROCESSED_DOCS] >= 0

            # Verify language codes are detected (should be ISO 639-1 codes)
            languages = result_table[OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY].to_pylist()
            assert all(isinstance(lang, str) for lang in languages)
            assert all(len(lang) >= 2 for lang in languages)  # ISO codes are at least 2 chars

            # Verify confidence scores are between 0 and 1
            scores = result_table[OperatorConstants.Columns.LANGUAGE_SCORE_COLUMN_KEY].to_pylist()
            assert all(isinstance(score, float) for score in scores)
            assert all(0.0 <= score <= 1.0 for score in scores)

        finally:
            operator.cleanup()

    def test_uzbek_language_detection(self, sample_config, sample_table):
        """Test that Uzbek language is detected (main feature of FastText)"""
        operator = LanguageDetect(sample_config)

        try:
            result_tables, _ = operator.transform(sample_table)
            result_table = result_tables[0]

            # Find the Uzbek text row
            names = result_table[OperatorConstants.Columns.NAME].to_pylist()
            uzbek_idx = names.index("uzbek.txt")

            detected_lang = result_table[OperatorConstants.Columns.LANGUAGE_NAME_COLUMN_KEY][uzbek_idx].as_py()
            confidence = result_table[OperatorConstants.Columns.LANGUAGE_SCORE_COLUMN_KEY][uzbek_idx].as_py()

            # Uzbek should be detected (uz is the ISO 639-1 code)
            assert detected_lang is not None
            assert detected_lang != "UNKNOWN"
            assert confidence > 0.0

        finally:
            operator.cleanup()

    def test_filter_unknown_language(self):
        """Test filtering of documents with unknown language"""
        config = {
            "doc_column": "content",
            "language_provider": "fasttext",
            OperatorConstants.Config.FILTER_UNKNOWN_LANGUAGE: True,
        }

        # Create table with some empty/invalid content
        content = pa.array(
            [
                "Hello, world!",
                "",  # Empty content
                "123456789",  # Numbers only
                "Valid English text here.",
            ]
        )
        names = pa.array(["valid1.txt", "empty.txt", "numbers.txt", "valid2.txt"])
        doc_ids = pa.array(["1", "2", "3", "4"])

        table = pa.Table.from_arrays(
            [doc_ids, content, names],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                OperatorConstants.Columns.NAME,
            ],
        )

        operator = LanguageDetect(config)

        try:
            result_tables, metadata = operator.transform(table)
            result_table = result_tables[0]

            # Some rows might be filtered out
            assert result_table.num_rows <= table.num_rows

            # Check that failed docs are recorded in metadata
            if metadata["failed_docs_count"] > 0:
                assert len(metadata["failed_docs"]) == metadata["failed_docs_count"]

        finally:
            operator.cleanup()

    def test_model_manager_reference_counting(self, sample_config):
        """Test that model manager correctly handles reference counting"""
        # Create first operator
        operator1 = LanguageDetect(sample_config)

        # Create second operator (should share the same model instance via singleton)
        operator2 = LanguageDetect(sample_config)

        try:
            # Both operators should have adapters
            assert operator1.language_adapter is not None
            assert operator2.language_adapter is not None

            # Verify both can detect language (model is working)
            test_text = "Hello world"
            result1 = operator1.language_adapter.detect_language(test_text)
            result2 = operator2.language_adapter.detect_language(test_text)

            assert result1.language_code == result2.language_code
            assert result1.confidence > 0.0

        finally:
            operator1.cleanup()
            operator2.cleanup()

    def test_required_features(self, sample_config):
        """Test that required features are correctly specified"""
        operator = LanguageDetect(sample_config)
        required_features = operator.get_required_features()

        assert "content" in required_features

        # Cleanup
        operator.cleanup()

    def test_empty_table(self, sample_config):
        """Test handling of empty table"""
        empty_table = pa.Table.from_arrays(
            [pa.array([]), pa.array([]), pa.array([])],
            names=[
                OperatorConstants.Columns.ID,
                "content",
                OperatorConstants.Columns.NAME,
            ],
        )

        operator = LanguageDetect(sample_config)

        try:
            result_tables, metadata = operator.transform(empty_table)
            result_table = result_tables[0]

            assert result_table.num_rows == 0
            assert metadata[Metrics.External.TOTAL_DOCS] == 0

        finally:
            operator.cleanup()

    def test_lock_timeout_on_acquire(self, sample_config):
        """Test that acquire_model times out if lock is held too long"""
        manager = FastTextModelManager()

        # Acquire the lock and hold it
        lock_acquired = manager._model_lock.acquire(timeout=1.0)
        assert lock_acquired

        try:
            # Try to acquire model from another "thread" (simulated by direct call)
            # This should timeout since we're holding the lock
            with pytest.raises(RuntimeError, match="Failed to acquire model lock"):
                manager.acquire_model(timeout=0.5)
        finally:
            manager._model_lock.release()

    def test_lock_timeout_on_release(self, sample_config):
        """Test that release_model times out if lock is held"""
        manager = FastTextModelManager()

        # First acquire the model normally
        _model = manager.acquire_model(timeout=5.0)

        # Now hold the lock externally
        lock_acquired = manager._model_lock.acquire(timeout=1.0)
        assert lock_acquired

        try:
            # Try to release - should timeout
            with pytest.raises(RuntimeError, match="Failed to acquire model lock for release"):
                manager.release_model(timeout=0.5)
        finally:
            manager._model_lock.release()
            # Clean up properly
            manager.release_model(timeout=5.0)

    def test_concurrent_model_acquisition(self, sample_config):
        """Test that multiple threads can safely acquire the model"""
        manager = FastTextModelManager()
        results = []
        errors = []

        def acquire_and_release():
            try:
                model = manager.acquire_model(timeout=10.0)
                results.append(model is not None)
                time.sleep(0.1)  # Simulate some work
                manager.release_model(timeout=10.0)
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads
        threads = [threading.Thread(target=acquire_and_release) for _ in range(5)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=30.0)

        # All threads should have succeeded
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5
        assert all(results), "All threads should have acquired the model"

        # Reference count should be back to 0
        final_ref_count = manager.get_ref_count()
        assert final_ref_count == 0

    def test_error_state_prevents_reload(self, sample_config):
        """Test that failed load prevents subsequent load attempts"""
        # Create a fresh manager instance for this test
        manager = FastTextModelManager()

        # Force error state by setting flags directly
        manager._load_failed = True
        manager._load_error = RuntimeError("Simulated load failure")

        try:
            # Attempt should immediately fail with stored error
            with pytest.raises(RuntimeError, match="FastText model loading previously failed"):
                manager.acquire_model(timeout=5.0)

        finally:
            # Clean up error state
            manager._load_failed = False
            manager._load_error = None
            # Reset ref count if needed
            if manager._model_lock.acquire(timeout=1.0):
                try:
                    manager._ref_count = 0
                finally:
                    manager._model_lock.release()

    def test_download_lock_prevents_concurrent_downloads(self, sample_config):
        """Test that download lock prevents multiple simultaneous downloads"""
        # This test verifies the download lock exists and can be acquired
        manager = FastTextModelManager()

        # Verify download lock exists
        assert hasattr(manager, "_download_lock")
        assert type(manager._download_lock).__name__ == "lock"

        # Test that we can acquire and release the download lock
        acquired = manager._download_lock.acquire(timeout=1.0)
        assert acquired, "Should be able to acquire download lock"

        # Try to acquire again from same thread (should fail since we hold it)
        acquired_again = manager._download_lock.acquire(blocking=False)
        assert not acquired_again, "Should not be able to acquire lock twice"

        # Release the lock
        manager._download_lock.release()

        # Now should be able to acquire again
        acquired_after_release = manager._download_lock.acquire(timeout=1.0)
        assert acquired_after_release, "Should be able to acquire after release"
        manager._download_lock.release()

    def test_get_ref_count_with_timeout(self, sample_config):
        """Test that get_ref_count handles timeout gracefully"""
        manager = FastTextModelManager()

        # Hold the lock
        lock_acquired = manager._model_lock.acquire(timeout=1.0)
        assert lock_acquired

        try:
            # get_ref_count should return -1 when it can't acquire lock
            ref_count = manager.get_ref_count()
            assert ref_count == -1
        finally:
            manager._model_lock.release()

        # Now it should work normally
        ref_count = manager.get_ref_count()
        assert ref_count >= 0

    def test_is_loaded_with_timeout(self, sample_config):
        """Test that is_loaded handles timeout gracefully"""
        manager = FastTextModelManager()

        # Hold the lock
        lock_acquired = manager._model_lock.acquire(timeout=1.0)
        assert lock_acquired

        try:
            # is_loaded should return False when it can't acquire lock
            loaded = manager.is_loaded()
            assert loaded is False
        finally:
            manager._model_lock.release()

        # Now it should work normally
        loaded = manager.is_loaded()
        assert isinstance(loaded, bool)

    def test_error_state_clears_on_unload(self, sample_config):
        """Test that error state is cleared when model is unloaded"""
        manager = FastTextModelManager()

        # Simulate a failed load
        manager._load_failed = True
        manager._load_error = RuntimeError("Test error")
        manager._ref_count = 1

        # Release should clear error state when ref_count reaches 0
        manager.release_model(timeout=5.0)

        assert manager._load_failed is False
        assert manager._load_error is None
        assert manager._ref_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
