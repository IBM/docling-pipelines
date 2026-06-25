"""Unit tests for IngestSourceOperator validation functionality."""

from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator


class TestIngestSourceOperatorValidation:
    """Test validation of IngestSourceOperator configurations."""

    def test_validation_catches_missing_secret_key_for_s3(self):
        """Test that validation catches missing secret_key for S3 provider."""
        config = {
            "provider": "s3",
            "credentials": {
                "access_key": "test_access_key",
                # Missing secret_key - should trigger validation error
            },
            "connection_params": {
                "bucket": "test-bucket",
                "prefix": "test/",
            },
            "validating_flow": True,
        }

        operator = IngestSourceOperator(config)

        errors = []
        warnings = []
        available_features = []

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        # Should have at least one error about missing secret_key
        assert len(errors) > 0, "Expected validation error for missing secret_key"
        assert any("secret_key" in str(error).lower() for error in errors), (
            "Expected error message to mention 'secret_key'"
        )

    def test_validation_catches_missing_access_key_for_s3(self):
        """Test that validation catches missing access_key for S3 provider."""
        config = {
            "provider": "s3",
            "credentials": {
                "secret_key": "test_secret_key",  # pragma: allowlist secret
                # Missing access_key - should trigger validation error
            },
            "connection_params": {
                "bucket": "test-bucket",
                "prefix": "test/",
            },
            "validating_flow": True,
        }

        operator = IngestSourceOperator(config)

        errors = []
        warnings = []
        available_features = []

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        # Should have at least one error about missing access_key
        assert len(errors) > 0, "Expected validation error for missing access_key"
        assert any("access_key" in str(error).lower() for error in errors), (
            "Expected error message to mention 'access_key'"
        )

    def test_validation_catches_missing_bucket_for_s3(self):
        """Test that validation catches missing bucket for S3 provider."""
        config = {
            "provider": "s3",
            "credentials": {
                "access_key": "test_access_key",
                "secret_key": "test_secret_key",  # pragma: allowlist secret
            },
            "connection_params": {
                # Missing bucket - should trigger validation error
                "prefix": "test/",
            },
            "validating_flow": True,
        }

        operator = IngestSourceOperator(config)

        errors = []
        warnings = []
        available_features = []

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        # Should have at least one error about missing bucket
        assert len(errors) > 0, "Expected validation error for missing bucket"
        assert any("bucket" in str(error).lower() for error in errors), "Expected error message to mention 'bucket'"

    def test_validation_passes_with_complete_s3_config(self):
        """Test that validation passes with complete S3 configuration."""
        config = {
            "provider": "s3",
            "credentials": {
                "access_key": "test_access_key",
                "secret_key": "test_secret_key",  # pragma: allowlist secret
            },
            "connection_params": {
                "bucket": "test-bucket",
                "prefix": "test/",
            },
            "validating_flow": True,
        }

        operator = IngestSourceOperator(config)

        errors = []
        warnings = []
        available_features = []

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        # Should have no errors with complete config
        assert len(errors) == 0, f"Expected no validation errors, but got: {errors}"

    def test_validation_catches_empty_credentials_for_s3(self):
        """Test that validation catches empty string credentials for S3."""
        config = {
            "provider": "s3",
            "credentials": {
                "access_key": "",  # Empty string
                "secret_key": "test_secret_key",  # pragma: allowlist secret
            },
            "connection_params": {
                "bucket": "test-bucket",
            },
            "validating_flow": True,
        }

        operator = IngestSourceOperator(config)

        errors = []
        warnings = []
        available_features = []

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        # Should have error about empty access_key
        assert len(errors) > 0, "Expected validation error for empty access_key"
        assert any("access_key" in str(error).lower() for error in errors), (
            "Expected error message to mention 'access_key'"
        )

    def test_validation_works_for_other_adapter_providers(self):
        """Test that validation works for other adapter-managed providers like Google Drive."""
        config = {
            "provider": "google_drive",
            "credentials": {
                # Missing required credentials for Google Drive
            },
            "connection_params": {},
            "validating_flow": True,
        }

        operator = IngestSourceOperator(config)

        errors = []
        warnings = []
        available_features = []

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        # Should catch validation errors for Google Drive too
        assert len(errors) > 0, "Expected validation error for incomplete Google Drive config"
