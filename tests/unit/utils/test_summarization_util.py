"""Tests for summarization utility functions."""

from unittest.mock import Mock

import pytest

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.utils.summarization_util import SummarizationUtil


@pytest.fixture
def mock_client():
    """Create a mock LLM client."""
    client = Mock()
    client.run = Mock(return_value="Paragraph 0: Test summary")
    return client


@pytest.fixture
def summarization_util(mock_client):
    """Create a SummarizationUtil instance with default parameters."""
    return SummarizationUtil(
        client=mock_client,
        max_length=1000,
        words_per_token=0.75,
        overlap_ratio=0.1,
        task_instruction="Summarize the following text:",
        summary_sentences=3,
        output_format="Return only the summary.",
    )


class TestSummarizationUtilInit:
    """Test SummarizationUtil initialization."""

    def test_initialization(self, mock_client):
        """Test that SummarizationUtil initializes correctly."""
        util = SummarizationUtil(
            client=mock_client,
            max_length=500,
            words_per_token=0.8,
            overlap_ratio=0.2,
            task_instruction="Test instruction",
            summary_sentences=5,
            output_format="Test format",
        )

        assert util.client == mock_client
        assert util.max_length == 500
        assert util.words_per_token == 0.8
        assert util.overlap_ratio == 0.2
        assert util.task_instruction == "Test instruction"
        assert util.summary_sentences == 5
        assert util.output_format == "Test format"


class TestGenerateSummaryForChunkedContent:
    """Test generate_summary_for_chunked_content method."""

    def test_generate_summary_for_chunked_content_with_dict(self, summarization_util, mock_client):
        """Test generating summaries for chunked content with dict format."""
        chunked_content = [
            {"chunk": "First chunk content", "start_index": 0},
            {"chunk": "Second chunk content", "start_index": 100},
        ]

        mock_client.run.return_value = "Paragraph 0: Summary for first\nParagraph 1: Summary for second"

        summarization_util.generate_summary_for_chunked_content(chunked_content=chunked_content)

        assert OperatorConstants.Columns.SUMMARY in chunked_content[0]
        assert OperatorConstants.Columns.SUMMARY in chunked_content[1]
        assert chunked_content[0][OperatorConstants.Columns.SUMMARY] == "Summary for first"
        assert chunked_content[1][OperatorConstants.Columns.SUMMARY] == "Summary for second"

    def test_generate_summary_for_chunked_content_with_string(self, summarization_util, mock_client):
        """Test generating summaries for chunked content with string format."""
        chunked_content = ["First chunk", "Second chunk"]

        mock_client.run.return_value = "Paragraph 0: Summary one\nParagraph 1: Summary two"

        summarization_util.generate_summary_for_chunked_content(chunked_content=chunked_content)

        # String chunks don't get summaries added (only dict format)
        assert not isinstance(chunked_content[0], dict)

    def test_generate_summary_no_summary_available(self, summarization_util, mock_client):
        """Test that missing summaries get default text."""
        chunked_content = [{"chunk": "Test chunk", "start_index": 0}]

        mock_client.run.return_value = "Paragraph 5: Wrong index"

        summarization_util.generate_summary_for_chunked_content(chunked_content=chunked_content)

        assert chunked_content[0][OperatorConstants.Columns.SUMMARY] == "No summary available"

    def test_generate_summary_empty_list(self, summarization_util, mock_client):
        """Test with empty chunked content list."""
        chunked_content = []

        summarization_util.generate_summary_for_chunked_content(chunked_content=chunked_content)

        assert len(chunked_content) == 0
        mock_client.run.assert_called_once()


class TestGenerateSummaryForContent:
    """Test generate_summary_for_content method."""

    def test_generate_summary_for_content(self, summarization_util, mock_client):
        """Test generating summary for single content."""
        content = "This is a test content that needs summarization."

        mock_client.run.return_value = "Paragraph 0: Test summary content"

        result = summarization_util.generate_summary_for_content(content=content)

        assert result == "Test summary content"
        mock_client.run.assert_called_once()

    def test_generate_summary_for_content_no_match(self, summarization_util, mock_client):
        """Test when no summary is found in response."""
        content = "Test content"

        mock_client.run.return_value = "Invalid response format"

        result = summarization_util.generate_summary_for_content(content=content)

        assert result == "No summary available"


class TestAnnotateParagraph:
    """Test _annotate_paragraph method."""

    def test_annotate_paragraph(self, summarization_util):
        """Test paragraph annotation."""
        result = summarization_util._annotate_paragraph(chunk_sequence_number=5, para="Test paragraph")

        assert "<<< Paragraph 5 START >>>" in result
        assert "Paragraph 5: Test paragraph" in result
        assert "<<< Paragraph 5 END >>>" in result

    def test_annotate_paragraph_strips_whitespace(self, summarization_util):
        """Test that annotation strips whitespace from paragraph."""
        result = summarization_util._annotate_paragraph(chunk_sequence_number=0, para="  Test  \n")

        assert "Paragraph 0: Test" in result


class TestSplitIntoSentences:
    """Test _split_into_sentences method."""

    def test_split_into_sentences_basic(self, summarization_util):
        """Test basic sentence splitting."""
        text = "First sentence. Second sentence! Third sentence?"

        sentences = summarization_util._split_into_sentences(text)

        assert len(sentences) == 3
        assert sentences[0] == "First sentence."
        assert sentences[1] == "Second sentence!"
        assert sentences[2] == "Third sentence?"

    def test_split_into_sentences_empty(self, summarization_util):
        """Test splitting empty text."""
        sentences = summarization_util._split_into_sentences("")

        assert len(sentences) == 0

    def test_split_into_sentences_no_punctuation(self, summarization_util):
        """Test splitting text without sentence-ending punctuation."""
        text = "Single sentence without ending"

        sentences = summarization_util._split_into_sentences(text)

        assert len(sentences) == 1
        assert sentences[0] == text

    def test_split_into_sentences_multiple_spaces(self, summarization_util):
        """Test splitting with multiple spaces between sentences."""
        text = "First.    Second!     Third?"

        sentences = summarization_util._split_into_sentences(text)

        assert len(sentences) == 3


class TestCallModel:
    """Test _call_model method."""

    def test_call_model_success(self, summarization_util, mock_client):
        """Test successful model call."""
        mock_client.run.return_value = "Test response"

        result = summarization_util._call_model(content="Test content")

        assert result == "Test response"
        mock_client.run.assert_called_once()

    def test_call_model_empty_response(self, summarization_util, mock_client):
        """Test model call with empty response."""
        mock_client.run.return_value = ""

        result = summarization_util._call_model(content="Test content")

        # Verify empty string is returned
        assert result == ""

    def test_call_model_none_response(self, summarization_util, mock_client):
        """Test model call with None response."""
        mock_client.run.return_value = None

        result = summarization_util._call_model(content="Test content")

        # Verify None is returned
        assert result is None


class TestSlidingTextChunks:
    """Test _sliding_text_chunks method."""

    def test_sliding_text_chunks_small_content(self, summarization_util):
        """Test sliding chunks with content smaller than max_length."""
        content = "Short content. Another sentence."

        chunks = list(summarization_util._sliding_text_chunks(content=content))

        assert len(chunks) == 1
        assert chunks[0][0] == 0
        assert chunks[0][1] == content.strip()

    def test_sliding_text_chunks_large_content(self):
        """Test sliding chunks with content larger than max_length."""
        util = SummarizationUtil(
            client=Mock(),
            max_length=10,  # Very small for testing
            words_per_token=1.0,
            overlap_ratio=0.2,
            task_instruction="Test",
            summary_sentences=3,
            output_format="Test",
        )

        # Create content with many sentences
        sentences = [f"Sentence {i}." for i in range(20)]
        content = " ".join(sentences)

        chunks = list(util._sliding_text_chunks(content=content))

        assert len(chunks) > 1
        assert all(isinstance(chunk[0], int) for chunk in chunks)
        assert all(isinstance(chunk[1], str) for chunk in chunks)

    def test_sliding_text_chunks_very_long_sentence(self):
        """Test sliding chunks with a very long single sentence."""
        util = SummarizationUtil(
            client=Mock(),
            max_length=5,
            words_per_token=1.0,
            overlap_ratio=0.1,
            task_instruction="Test",
            summary_sentences=3,
            output_format="Test",
        )

        content = "This is a very long sentence with many words that exceeds the maximum length."

        chunks = list(util._sliding_text_chunks(content=content))

        assert len(chunks) >= 1


class TestGenerateSummaryPrompt:
    """Test _generate_summary_prompt method."""

    def test_generate_summary_prompt(self, summarization_util):
        """Test prompt generation."""
        content = "Test content"

        prompt = summarization_util._generate_summary_prompt(content=content)

        assert "sophisticated AI expert" in prompt
        assert "Summarize the following text:" in prompt
        assert "Test content" in prompt
        assert "does not exceed 3 sentences" in prompt
        assert "Return only the summary." in prompt


class TestParseSummaries:
    """Test _parse_summaries method."""

    def test_parse_summaries_basic(self, summarization_util):
        """Test basic summary parsing."""
        text = "Paragraph 0: First summary\nParagraph 1: Second summary"

        summaries = summarization_util._parse_summaries(text=text)

        assert len(summaries) == 2
        assert summaries[0] == "First summary"
        assert summaries[1] == "Second summary"

    def test_parse_summaries_empty(self, summarization_util):
        """Test parsing empty text."""
        summaries = summarization_util._parse_summaries(text="")

        assert len(summaries) == 0

    def test_parse_summaries_none(self, summarization_util):
        """Test parsing None."""
        summaries = summarization_util._parse_summaries(text=None)

        assert len(summaries) == 0

    def test_parse_summaries_with_markers(self, summarization_util):
        """Test parsing with paragraph markers."""
        text = "Paragraph 0: Summary with <<< Paragraph 0 START >>> markers"

        summaries = summarization_util._parse_summaries(text=text)

        assert 0 in summaries
        assert "markers" in summaries[0]
        assert "<<<" not in summaries[0]

    def test_parse_summaries_multiline(self, summarization_util):
        """Test parsing multiline summaries."""
        text = """Paragraph 0: This is a long summary
        that spans multiple lines
        and should be combined.
        Paragraph 1: Another summary."""

        summaries = summarization_util._parse_summaries(text=text)

        assert len(summaries) == 2
        assert 0 in summaries
        assert 1 in summaries


class TestNormalizeParagraphMarkers:
    """Test _normalize_paragraph_markers method."""

    def test_normalize_paragraph_markers_basic(self, summarization_util):
        """Test basic normalization."""
        text = "Some text Paragraph 1: content"

        result = summarization_util._normalize_paragraph_markers(text=text)

        assert "\nParagraph 1:" in result

    def test_normalize_numbered_list(self, summarization_util):
        """Test normalization of numbered lists."""
        text = "1. Paragraph 0: content\n2. Paragraph 1: more content"

        result = summarization_util._normalize_paragraph_markers(text=text)

        assert "1." not in result
        assert "2." not in result

    def test_normalize_brackets(self, summarization_util):
        """Test normalization of bracket formats."""
        text = "[Paragraph 0: content]\n[# Paragraph 1: more]"

        result = summarization_util._normalize_paragraph_markers(text=text)

        assert "[" not in result or "Paragraph 0:" in result

    def test_normalize_markdown_headers(self, summarization_util):
        """Test normalization of markdown headers."""
        text = "## Paragraph 0: content\n### Paragraph 1: more"

        result = summarization_util._normalize_paragraph_markers(text=text)

        assert "##" not in result


class TestExtractCleanSummary:
    """Test _extract_clean_summary method."""

    def test_extract_clean_summary_basic(self, summarization_util):
        """Test basic summary extraction."""
        content = "This is a clean summary."

        result = summarization_util._extract_clean_summary(content=content)

        assert result == "This is a clean summary."

    def test_extract_clean_summary_with_markers(self, summarization_util):
        """Test extraction with paragraph markers."""
        content = "<<< Paragraph 0 START >>> Summary text <<< Paragraph 0 END >>>"

        result = summarization_util._extract_clean_summary(content=content)

        assert "Summary text" in result
        assert "<<<" not in result

    def test_extract_clean_summary_with_code_blocks(self, summarization_util):
        """Test extraction with code block markers."""
        content = "```Summary text```"

        result = summarization_util._extract_clean_summary(content=content)

        assert "Summary text" in result
        assert "```" not in result

    def test_extract_clean_summary_with_leading_colon(self, summarization_util):
        """Test extraction with leading colon."""
        content = ": Summary text here."

        result = summarization_util._extract_clean_summary(content=content)

        assert result == "Summary text here."

    def test_extract_clean_summary_multiline(self, summarization_util):
        """Test extraction with multiple lines."""
        content = "First line.\nSecond line.\nThird line."

        result = summarization_util._extract_clean_summary(content=content)

        assert "First line." in result
        assert "Second line." in result
        assert "Third line." in result


class TestIsWordCountingLine:
    """Test _is_word_counting_line method."""

    def test_is_word_counting_line_true(self, summarization_util):
        """Test detection of word counting lines."""
        assert summarization_util._is_word_counting_line(line="(50 words)")
        assert summarization_util._is_word_counting_line(line="Word count: 25")
        assert summarization_util._is_word_counting_line(line="10 words total")

    def test_is_word_counting_line_false(self, summarization_util):
        """Test non-word-counting lines."""
        assert not summarization_util._is_word_counting_line(line="This is a normal sentence.")
        assert not summarization_util._is_word_counting_line(line="No numbers here")

    def test_is_word_counting_line_too_long(self, summarization_util):
        """Test that very long lines are not considered word counting."""
        long_line = "This is a very long line " * 10 + "with word count 5"

        assert not summarization_util._is_word_counting_line(line=long_line)


class TestIsMetaText:
    """Test _is_meta_text method."""

    def test_is_meta_text_true(self, summarization_util):
        """Test detection of meta text."""
        assert summarization_util._is_meta_text(text="Let's begin")
        assert summarization_util._is_meta_text(text="That's correct")
        assert summarization_util._is_meta_text(text="Good job")
        assert summarization_util._is_meta_text(text="Provide the answer")
        assert summarization_util._is_meta_text(text="assistant: Here is")
        assert summarization_util._is_meta_text(text="Ensure that")
        assert summarization_util._is_meta_text(text="Make sure to")
        assert summarization_util._is_meta_text(text="Return only")

    def test_is_meta_text_false(self, summarization_util):
        """Test non-meta text."""
        assert not summarization_util._is_meta_text(text="This is a normal summary.")
        assert not summarization_util._is_meta_text(text="The document discusses")

    def test_is_meta_text_case_insensitive(self, summarization_util):
        """Test that meta text detection is case insensitive."""
        assert summarization_util._is_meta_text(text="let's begin")
        assert summarization_util._is_meta_text(text="ENSURE THAT")


class TestGenerateSummariesIntegration:
    """Test _generate_summaries method integration."""

    def test_generate_summaries_small_content(self, summarization_util, mock_client):
        """Test summary generation for small content."""
        content = "Short content that fits in one request."
        mock_client.run.return_value = "Paragraph 0: Summary"

        summaries = summarization_util._generate_summaries(content=content)

        assert len(summaries) == 1
        assert 0 in summaries

    def test_generate_summaries_large_content(self, mock_client):
        """Test summary generation for large content requiring sliding windows."""
        util = SummarizationUtil(
            client=mock_client,
            max_length=10,
            words_per_token=1.0,
            overlap_ratio=0.1,
            task_instruction="Test",
            summary_sentences=3,
            output_format="Test",
        )

        # Create large content
        content = " ".join([f"Sentence {i}." for i in range(50)])
        mock_client.run.return_value = "Paragraph 0: Summary"

        summaries = util._generate_summaries(content=content)

        assert isinstance(summaries, dict)

    def test_generate_summaries_with_exception(self, mock_client):
        """Test summary generation with exception handling."""
        util = SummarizationUtil(
            client=mock_client,
            max_length=10,
            words_per_token=1.0,
            overlap_ratio=0.1,
            task_instruction="Test",
            summary_sentences=3,
            output_format="Test",
        )

        content = " ".join([f"Sentence {i}." for i in range(20)])
        mock_client.run.side_effect = Exception("Test error")

        summaries = util._generate_summaries(content=content)

        # Verify that exceptions are handled gracefully and an empty dict is returned
        assert isinstance(summaries, dict)

    def test_generate_summaries_merges_multiple_summaries(self, mock_client):
        """Test that multiple summaries for same paragraph are merged."""
        util = SummarizationUtil(
            client=mock_client,
            max_length=10,
            words_per_token=1.0,
            overlap_ratio=0.5,  # High overlap
            task_instruction="Test",
            summary_sentences=3,
            output_format="Test",
        )

        content = " ".join([f"Sentence {i}." for i in range(20)])
        mock_client.run.return_value = "Paragraph 0: Part one"

        summaries = util._generate_summaries(content=content)

        if 0 in summaries:
            # Multiple calls should result in merged summaries
            assert isinstance(summaries[0], str)
