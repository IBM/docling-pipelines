# Common Utilities

This package contains shared utilities, models, and exceptions used across the datasift project.

## Purpose
- Shared utility functions
- Common data models
- Exception classes
- Helper functions
- Infrastructure utilities for model management

## Components
- Utility modules
- Common models and data structures
- Exception hierarchy
- Logging utilities
- Infrastructure model managers

## Infrastructure Utilities

### Model Managers

#### FastTextModelManager
**Location**: `datasift/utils/infrastructure/fasttext_model_manager.py`

Thread-safe singleton manager for FastText language detection model supporting 176+ languages.

**Key Features**:
- Singleton pattern ensures only one model instance per process
- Reference counting for memory-efficient model sharing across parallel flows
- Automatic model download (~131MB) with SSL fallback for corporate proxies
- Lock timeout protection (60s acquire, 10s release)
- Error state tracking to prevent repeated failed load attempts
- Graceful degradation when model loading fails

**Used By**: LanguageDetection operator (FastText adapter)

**Thread Safety**:
- Separate locks for model operations and downloads
- Double-checked locking pattern for singleton and downloads
- Configurable timeouts prevent indefinite blocking

#### NLTKDataManager
**Location**: `datasift/utils/infrastructure/nltk_data_manager.py`

Thread-safe NLTK data package management with SSL certificate bypass capabilities.

**Key Features**:
- Thread-safe downloads using locks
- Automatic SSL retry on certificate errors for restricted environments
- Scoped monkey-patching with guaranteed cleanup
- No global side effects on urllib or other code
- Downloads to virtual environment's nltk_data directory

**Used By**: MLEnrichment operator (punkt_tab tokenizer)

**Why Monkey-Patching**:
NLTK doesn't provide any method to inject SSL context (no override points, no parameters). The only solution is to temporarily replace `nltk.downloader.urlopen` during download operations. The patch is scoped to the download call only (~1-2 seconds) and restored via finally block (guaranteed cleanup).