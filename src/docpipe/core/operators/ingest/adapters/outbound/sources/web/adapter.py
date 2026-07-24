"""Web page source adapter using LangChain's RecursiveUrlLoader."""

from typing import Any, AsyncGenerator

import requests
from langchain_community.document_loaders import RecursiveUrlLoader
from pydantic import BaseModel

from docpipe.core.operators.ingest.adapters.outbound.sources.factories.source_factory import register_source_adapter
from docpipe.core.operators.ingest.adapters.outbound.sources.web.config import WebPageSourceConfig
from docpipe.core.operators.ingest.domain.models import Document
from docpipe.core.operators.ingest.ports.outbound.document_source import DocumentSourcePort
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.core.docpipe_utils import generate_hex_digest
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@register_source_adapter
class WebPageSourceAdapter(DocumentSourcePort):
    """
    Adapter for ingesting web pages recursively using LangChain's RecursiveUrlLoader.

    This adapter wraps LangChain's RecursiveUrlLoader to crawl web pages starting
    from a given URL and following links up to a specified depth.

    Features:
    - Recursive URL crawling with configurable depth
    - URL pattern exclusion for filtering unwanted pages
    - Configurable request timeout
    - Automatic HTML content extraction
    - Custom extractor support for specialized parsing

    Benefits:
    - Battle-tested by LangChain community
    - Automatic link discovery and traversal
    - Built-in error handling for failed requests
    - Simpler than manual web scraping implementation
    """

    # Metadata for connector discovery
    SOURCE_NAME = "web"
    SOURCE_DISPLAY_NAME = "Web Pages"
    SOURCE_DESCRIPTION = "Ingests web pages recursively using URL crawling"
    SOURCE_VERSION = "1.0.0"

    async def fetch_documents(self, config: WebPageSourceConfig) -> AsyncGenerator[Document, None]:
        """
        Fetch documents from web pages using RecursiveUrlLoader.

        Args:
            config: Validated web page configuration

        Yields:
            Document: Domain documents from web pages

        Raises:
            DocpipeException: If langchain_community is not installed or crawling fails
        """
        # Iterate through all URLs
        for url in config.urls:
            logger.info(f"Starting web crawl from {url} with max_depth={config.max_depth}")

            try:
                # Create LangChain loader with configuration
                # Note: RecursiveUrlLoader is synchronous
                loader = RecursiveUrlLoader(
                    url=url,
                    max_depth=config.max_depth,
                    extractor=lambda x: x,  # Default extractor returns raw HTML
                    prevent_outside=config.prevent_outside,  # Control external link following
                    use_async=False,  # Use synchronous requests
                    timeout=config.timeout,
                    # Note: exclude_dirs parameter filters URL paths
                    exclude_dirs=config.exclude_patterns if config.exclude_patterns else None,
                )

                # Load documents (synchronous operation from LangChain)
                langchain_docs = loader.load()
                logger.info(f"Successfully crawled {len(langchain_docs)} pages from {url}")

                # Convert LangChain documents to domain documents
                for lc_doc in langchain_docs:
                    # Extract metadata first for error handling
                    metadata = lc_doc.metadata
                    source_url = metadata.get("source", url)

                    try:
                        # Generate unique document ID from URL
                        doc_id = generate_hex_digest(text=source_url)

                        # Extract title from metadata or use URL as fallback
                        doc_name = metadata.get("title", source_url.split("/")[-1] or "index")

                        # Convert page_content (string) to bytes
                        # Store HTML content as bytes for consistency with other adapters
                        content = lc_doc.page_content.encode("utf-8")

                        # Create domain document
                        document = Document(
                            id=doc_id,
                            name=doc_name,
                            content=content,
                            source_url=source_url,
                            modified_time=None,  # Web pages don't have reliable modified time
                            metadata={
                                "content_type": "text/html",
                                "file_size": len(content),
                                "depth": metadata.get("depth", 0),
                                "url": source_url,
                            },
                        )
                        yield document
                    except Exception as e:
                        # Log warning but continue processing other pages
                        logger.warning(f"Failed to process page {source_url}: {e}")
                        continue
            except ImportError as e:
                raise DocpipeException(
                    "LangChain community dependencies not installed. Install with: pip install langchain-community"
                ) from e
            except Exception as e:
                # Log error for this URL but continue with other URLs
                logger.error(f"Failed to crawl {url}: {e}")
                continue

    async def test_connection(self, config: WebPageSourceConfig) -> tuple[bool, str]:
        """
        Test web page connection by checking URL accessibility.

        Args:
            config: Validated web page configuration

        Returns:
            Tuple[bool, str]: (success, message)
        """

        if not config.urls:
            return False, "No URLs provided"

        # Test all URLs
        results = []
        failed_urls = []

        for url in config.urls:
            try:
                # Test URL accessibility with a simple HEAD request
                response = requests.head(
                    url,
                    timeout=config.timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
                results.append(f"✓ {url} (Status: {response.status_code})")
            except requests.exceptions.Timeout:
                failed_urls.append(f"✗ {url} (Timeout after {config.timeout}s)")
            except requests.exceptions.ConnectionError:
                failed_urls.append(f"✗ {url} (Connection failed)")
            except requests.exceptions.HTTPError as e:
                failed_urls.append(f"✗ {url} (HTTP error: {e})")
            except Exception as e:
                failed_urls.append(f"✗ {url} (Error: {e!s})")

        # Determine overall success
        if not failed_urls:
            return True, f"Successfully connected to all {len(config.urls)} URL(s):\n" + "\n".join(results)
        elif results:
            # Partial success
            all_results = results + failed_urls
            return True, f"Connected to {len(results)}/{len(config.urls)} URL(s):\n" + "\n".join(all_results)
        else:
            # All failed
            return False, "Failed to connect to all URL(s):\n" + "\n".join(failed_urls)

    def get_config_schema(self) -> type[BaseModel]:
        """
        Get the configuration schema for this adapter.

        Returns:
            type[BaseModel]: The Pydantic configuration model
        """
        return WebPageSourceConfig

    def fetch_binary_content(
        self,
        *,
        source_id: str,
        connection_params: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bytes | None:
        """
        Fetch binary content for a specific URL via HTTP download.

        Args:
            source_id: URL to download
            connection_params: Connection parameters (timeout, etc.)
            credentials: Authentication credentials (not used for web)

        Returns:
            Binary content as bytes, or None if download fails
        """
        # Get timeout from connection_params or use default
        timeout = connection_params.get("timeout", 30)

        try:
            logger.info(f"Downloading binary content from URL: {source_id}")

            # Download content via HTTP GET
            response = requests.get(
                source_id,
                timeout=timeout,
                allow_redirects=True,
            )
            response.raise_for_status()

            content = response.content
            logger.info(f"Successfully downloaded {len(content)} bytes from {source_id}")
            return content

        except requests.exceptions.Timeout:
            logger.error(f"Timeout downloading from {source_id} after {timeout}s")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error downloading from {source_id}: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error downloading from {source_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading from {source_id}: {e}", exc_info=True)
            return None

    def build_config_from_operator_params(
        self,
        *,
        connection_params: dict,
        credentials: dict,
        included_extensions: list[str] | None = None,
        max_files: int | None = None,
    ) -> BaseModel:
        """
        Build web page configuration from operator parameters.

        Maps IngestSource operator parameters to WebPageSourceConfig.
        This encapsulates the knowledge of how to construct the config within
        the adapter itself, following the Single Responsibility Principle.

        Args:
            connection_params: Connection parameters from operator config
            credentials: Credentials from operator config (not used for web)
            included_extensions: File extensions to include (not used for web)
            max_files: Maximum number of files to process (not used for web)

        Returns:
            WebPageSourceConfig: Validated configuration object

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Support both single URL and list of URLs
        urls = connection_params.get("urls")
        if urls is None:
            # Fallback to single URL for backward compatibility
            url = connection_params.get("url")
            urls = [url] if url else []

        config_dict = {
            "urls": urls,
            "max_depth": connection_params.get("max_depth", 2),
            "prevent_outside": connection_params.get("prevent_outside", True),
            "exclude_patterns": connection_params.get("exclude_patterns", []),
            "timeout": connection_params.get("timeout", 30),
            "extractor": connection_params.get("extractor"),
        }

        return WebPageSourceConfig(**config_dict)
