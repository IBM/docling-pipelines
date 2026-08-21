"""Unit tests for SummarizationUtil."""

from unittest.mock import MagicMock

from docpipe.utils.summarization_util import SummarizationUtil


def make_util(response: str = "Paragraph 0: Summary text.") -> SummarizationUtil:
    """Create a SummarizationUtil with a mock LLM client."""
    client = MagicMock()
    client.run.return_value = response
    return SummarizationUtil(
        client=client,
        max_length=500,
        words_per_token=0.75,
        overlap_ratio=0.1,
        task_instruction="Summarise each paragraph.",
        summary_sentences=2,
        output_format="Output: Paragraph N: <summary>",
    )


class TestGenerateSummaryForContent:
    def test_returns_summary_string(self):
        util = make_util("Paragraph 0: A clear summary.")
        result = util.generate_summary_for_content(content="Some long text here.")
        assert isinstance(result, str)
        assert "summary" in result.lower() or result  # non-empty

    def test_empty_client_response_returns_no_summary(self):
        util = make_util("")
        result = util.generate_summary_for_content(content="text")
        assert result == "No summary available"


class TestGenerateSummaryForChunkedContent:
    def test_attaches_summary_to_each_chunk(self):
        util = make_util("Paragraph 0: First summary.\nParagraph 1: Second summary.")
        chunks = [
            {"chunk": "First chunk text.", "start_index": 0},
            {"chunk": "Second chunk text.", "start_index": 1},
        ]
        util.generate_summary_for_chunked_content(chunked_content=chunks)
        assert "summary" in chunks[0]
        assert "summary" in chunks[1]

    def test_non_dict_chunk_handled(self):
        client = MagicMock()
        client.run.return_value = "Paragraph 0: Summary."
        util = SummarizationUtil(
            client=client,
            max_length=500,
            words_per_token=0.75,
            overlap_ratio=0.1,
            task_instruction="",
            summary_sentences=2,
            output_format="",
        )
        chunks = [{"chunk": "text", "start_index": 0}]
        util.generate_summary_for_chunked_content(chunked_content=chunks)
        assert chunks[0]["summary"]


class TestParseSummaries:
    def test_parses_well_formed_response(self):
        util = make_util()
        result = util._parse_summaries(text="Paragraph 0: This is the summary.\nParagraph 1: Another one.")
        assert 0 in result
        assert "summary" in result[0].lower()

    def test_returns_empty_on_none(self):
        util = make_util()
        assert util._parse_summaries(text=None) == {}

    def test_returns_empty_on_blank(self):
        util = make_util()
        assert util._parse_summaries(text="   ") == {}


class TestNormalizeParagraphMarkers:
    def test_normalises_bracket_format(self):
        util = make_util()
        text = "[Paragraph 1: summary]"
        result = util._normalize_paragraph_markers(text=text)
        assert "Paragraph 1:" in result


class TestIsMetaText:
    def test_detects_meta(self):
        util = make_util()
        assert util._is_meta_text(text="Let's summarise this.") is True
        assert util._is_meta_text(text="This is a real sentence.") is False


class TestIsWordCountingLine:
    def test_detects_word_count_line(self):
        util = make_util()
        assert util._is_word_counting_line(line="Total: 50 words") is True
        assert util._is_word_counting_line(line="This is normal text without numbers") is False


class TestSlidingTextChunks:
    def test_short_content_yields_once(self):
        util = make_util()
        chunks = list(util._sliding_text_chunks(content="Short text."))
        assert len(chunks) == 1
        assert chunks[0][0] == 0

    def test_long_content_yields_multiple(self):
        util = SummarizationUtil(
            client=MagicMock(),
            max_length=10,
            words_per_token=1.0,
            overlap_ratio=0.2,
            task_instruction="",
            summary_sentences=1,
            output_format="",
        )
        content = " ".join([f"word{i}." for i in range(30)])
        chunks = list(util._sliding_text_chunks(content=content))
        assert len(chunks) > 1
