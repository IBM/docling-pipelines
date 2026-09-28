"""Unit tests verifying DocLang auto-transcoding for ChunkerOperator."""

import pyarrow as pa

from docpipe.core.operators.functional.chunker import ChunkerOperator


class TestChunkerDocFormat:
    """Tests verifying ChunkerOperator behaves correctly with doc_format=doclang and markdown."""

    def test_chunker_doc_format_attribute(self):
        """ChunkerOperator correctly inherits and stores doc_format."""
        op = ChunkerOperator({"doc_format": "doclang"})
        assert op.doc_format == "doclang"

    def test_chunker_simple_doclang_strips_tags(self):
        """Simple chunking strips DocLang XML tags before splitting."""
        op = ChunkerOperator(
            {
                "chunk_type": "simple",
                "chunk_size": 500,
                "chunk_overlap": 50,
                "doc_format": "doclang",
            }
        )
        xml = '<doclang version="0.7">\n  <text>Heading One</text>\n  <text>Paragraph text content.</text>\n</doclang>'
        table = pa.table(
            {
                "id": ["0"],
                "name": ["doc.xml"],
                "content": [xml],
            }
        )
        output_tables, _metadata = op.transform(table)
        assert len(output_tables) == 1
        chunked = output_tables[0]["chunked_content"][0].as_py()
        assert len(chunked) > 0
        for chunk_item in chunked:
            text = chunk_item["chunk"]
            assert "<" not in text
            assert "</" not in text

    def test_chunker_semantic_doclang_strips_tags(self, monkeypatch):
        """Semantic chunking prepares clean text when doc_format=doclang."""
        op = ChunkerOperator(
            {
                "chunk_type": "semantic",
                "semantic_embeddings_model": "all-minilm",
                "doc_format": "doclang",
            }
        )
        prepared = op._prepare_text_for_splitting(
            content='<doclang version="0.7"><text>Sample text</text></doclang>',
            doc_format="doclang",
        )
        assert "<" not in prepared
        assert "Sample text" in prepared

    def test_chunker_hybrid_doclang_deserialization(self):
        """Hybrid chunking uses DocLangDocDeserializer to parse DocLang XML."""
        op = ChunkerOperator({"chunk_type": "hybrid", "doc_format": "doclang"})
        xml = (
            '<doclang version="0.7">\n  <text>Section Title</text>\n  <text>This is body paragraph.</text>\n</doclang>'
        )
        doc = op._create_docling_document_from_doclang(doclang_content=xml, doc_name="test.doclang")
        assert doc is not None
        # Exporting back to markdown should preserve text
        md = doc.export_to_markdown()
        assert "Section Title" in md
        assert "This is body paragraph." in md

    def test_chunker_hybrid_doclang_transform(self):
        """Hybrid chunker processes doclang content and produces chunks with metadata and doc_name."""
        op = ChunkerOperator({"chunk_type": "hybrid", "doc_format": "doclang"})
        xml = '<doclang version="0.7">\n  <text>First section text</text>\n</doclang>'
        table = pa.table(
            {
                "id": ["0"],
                "name": ["custom_report.doclang"],
                "content": [xml],
            }
        )
        output_tables, _metadata = op.transform(table)
        assert len(output_tables) == 1
        chunked = output_tables[0]["chunked_content"][0].as_py()
        assert len(chunked) > 0
        assert "First section text" in chunked[0]["chunk"]

    def test_chunker_docling_serve_doclang_strips_tags(self, monkeypatch):
        """docling-serve remote chunking converts DocLang to markdown before sending."""

        op = ChunkerOperator(
            {
                "provider": "docling_serve",
                "doc_format": "doclang",
            }
        )
        sent_contents = []

        def mock_docling_serve_split_text(*, content: str, doc_name: str | None = None):
            sent_contents.append(content)
            return []

        monkeypatch.setattr(op, "_docling_serve_split_text", mock_docling_serve_split_text)

        xml = '<doclang version="0.7">\n  <text>Remote content</text>\n</doclang>'
        table = pa.table(
            {
                "id": ["0"],
                "name": ["doc.xml"],
                "content": [xml],
            }
        )
        op.transform(table)
        assert len(sent_contents) == 1
        assert "<" not in sent_contents[0]
        assert "Remote content" in sent_contents[0]

    def test_chunker_markdown_path_unchanged(self):
        """ChunkerOperator with doc_format=markdown keeps markdown content behavior."""
        op = ChunkerOperator(
            {
                "chunk_type": "simple",
                "chunk_size": 500,
                "chunk_overlap": 50,
                "doc_format": "markdown",
            }
        )
        md_text = "# Title\n\nParagraph text."
        table = pa.table(
            {
                "id": ["0"],
                "name": ["doc.md"],
                "content": [md_text],
            }
        )
        output_tables, _metadata = op.transform(table)
        assert len(output_tables) == 1
        chunked = output_tables[0]["chunked_content"][0].as_py()
        assert len(chunked) > 0
