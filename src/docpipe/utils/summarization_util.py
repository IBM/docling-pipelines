"""Text utility functions for summarization and embedding operations."""

import re
from collections import defaultdict
from typing import Any, Iterator

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class SummarizationUtil:
    """Utility class for generating summaries for chunked content."""

    def __init__(
        self,
        client: Any,
        max_length: int,
        words_per_token: float,
        overlap_ratio: float,
        task_instruction: str,
        summary_sentences: int,
        output_format: str,
    ):
        """
        Initialize the summarization utility.

        Args:
            client: The LLM client for generating summaries
            max_length: Maximum token length for content
            words_per_token: Approximate words per token ratio
            overlap_ratio: Overlap ratio for sliding windows
            task_instruction: Task instruction for the LLM
            summary_sentences: Maximum number of sentences in summary
            output_format: Output format instruction for the LLM
        """
        self.client = client
        self.max_length = max_length
        self.words_per_token = words_per_token
        self.overlap_ratio = overlap_ratio
        self.task_instruction = task_instruction
        self.summary_sentences = summary_sentences
        self.output_format = output_format

    def generate_summary_for_chunked_content(self, *, chunked_content: list[dict[str, Any]]) -> None:
        """
        Expected format of chunked_content:
        [ {"chunk": "<chunk_content>", "start_index": "<start_index>" },
          {"chunk": "<chunk_content>", "start_index": "<start_index>" },
          ....
        ]

        Result format of chunked_content after the method execution:
        [ {"chunk": "<chunk_content>", "start_index": "<start_index>", "summary": "<summary>" },
          {"chunk": "<chunk_content>", "start_index": "<start_index>", "summary": "<summary>" },
          ....
        ]
        """

        annotated_paragraphs = []
        for seq_num, chunk in enumerate(chunked_content):
            chunk_text = chunk.get(OperatorConstants.Columns.CHUNK) if isinstance(chunk, dict) else str(chunk)
            annotated_paragraphs.append(self._annotate_paragraph(chunk_sequence_number=seq_num, para=str(chunk_text)))

        full_content = "\n\n".join(annotated_paragraphs)
        summaries = self._generate_summaries(content=full_content)

        # Attach summaries back to chunks
        for seq_num, chunk in enumerate(chunked_content):
            if isinstance(chunk, dict):
                chunk[OperatorConstants.Columns.SUMMARY] = summaries.get(seq_num, "No summary available")

    def generate_summary_for_content(self, *, content: str) -> str:
        """Generate summary for content."""
        annotated_content = self._annotate_paragraph(chunk_sequence_number=0, para=content)
        summaries = self._generate_summaries(content=annotated_content)
        return summaries.get(0, "No summary available")

    def _annotate_paragraph(self, *, chunk_sequence_number: int, para: str) -> str:
        return f"<<< Paragraph {chunk_sequence_number} START >>>\nParagraph {chunk_sequence_number}: {para.strip()}\n<<< Paragraph {chunk_sequence_number} END >>>"

    def _split_into_sentences(self, text: str) -> list[str]:
        """
        Splits text into sentences using punctuation.
        """
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s for s in sentences if s]

    def _generate_summaries(self, *, content: str) -> dict[int, str]:
        # Estimate if content fits in one request (word-based)
        word_count = len(content.split())
        estimated_tokens = word_count / self.words_per_token

        if estimated_tokens <= self.max_length:
            response = self._call_model(content=content)
            return self._parse_summaries(text=response)

        all_summaries = defaultdict(list)

        # Use word-based sliding windows with sentence boundaries
        for chunk_idx, chunk_text in self._sliding_text_chunks(content=content):
            try:
                response = self._call_model(content=chunk_text)
                chunk_summaries = self._parse_summaries(text=response)
                for para_num, summary in chunk_summaries.items():
                    all_summaries[para_num].append(summary)
            except Exception as e:
                logger.warning(f"Failed to generate summary for window {chunk_idx}: {e!s}")
                continue

        merged_summaries = {}
        for para_num, summary_list in all_summaries.items():
            merged_summaries[para_num] = " ".join(summary_list)
        return merged_summaries

    def _call_model(self, *, content: str) -> str:
        """Call the Ollama model to generate summaries."""
        prompt = self._generate_summary_prompt(content=content)
        response = self.client.run(prompt=prompt)
        if not response:
            logger.warning("Empty response received from Ollama model")
        return response

    def _sliding_text_chunks(self, *, content: str) -> Iterator[tuple[int, str]]:
        """
        Generate sliding windows over text using word-based estimation.
        """
        max_words = int(self.max_length * self.words_per_token)
        overlap_words = int(max_words * self.overlap_ratio)
        stride_words = max_words - overlap_words

        sentences = self._split_into_sentences(content)
        # Convert sentences to (sentence, word_count)
        sent_word_counts = [(s, len(s.split())) for s in sentences]
        total_words = sum(wc for _, wc in sent_word_counts)

        if total_words <= max_words:
            yield 0, content.strip()
            return

        chunk_idx = 0
        start_sent_idx = 0

        while start_sent_idx < len(sent_word_counts):
            current_words = 0
            chunk_sentences = []
            i = start_sent_idx

            # Build chunk without breaking sentences
            while i < len(sent_word_counts):
                sent, wc = sent_word_counts[i]
                if current_words + wc > max_words:
                    break
                chunk_sentences.append(sent)
                current_words += wc
                i += 1

            if not chunk_sentences:
                # Handle very long single sentence
                chunk_sentences.append(sent_word_counts[i][0])
                i += 1
            chunk_text = " ".join(chunk_sentences)
            yield chunk_idx, chunk_text

            chunk_idx += 1
            # Move start forward based on stride (in words)
            words_moved = 0
            new_start = start_sent_idx

            while new_start < len(sent_word_counts) and words_moved < stride_words:
                words_moved += sent_word_counts[new_start][1]
                new_start += 1

            if new_start <= start_sent_idx:
                break  # Prevent infinite loop

            start_sent_idx = new_start

    def _generate_summary_prompt(self, *, content: str) -> str:
        return (
            "You are a sophisticated AI expert in Natural Language Processing (NLP), "
            "with a specialized ability to semantically analyze long text and distill their meaning."
            f"{self.task_instruction}\n\n"
            f"```\n{content}\n```\n\n"
            "The abstract should contain all the important aspects given in the paragraph."
            f"Ensure that the abstract does not exceed {self.summary_sentences} sentences."
            "Each paragraph abstract should be self-contained and not depend on the previous abstracts."
            "Each abstract must be written in the same language as the input paragraph it summarizes"
            f"{self.output_format}\n\n"
        )

    def _parse_summaries(self, *, text: str | None) -> dict[int, str]:
        """Parse LLM response to extract paragraph summaries."""
        if not text or not text.strip():
            return {}

        text = self._normalize_paragraph_markers(text=str(text))
        matches = re.findall(r"(?ms)^Paragraph\s*(\d+)\s*:\s*((?:(?!^Paragraph\s*\d+).)*)", text)

        summaries = {}
        for num, content in matches:
            final_summary = self._extract_clean_summary(content=content)
            if final_summary:
                summaries[int(num)] = final_summary

        return summaries

    def _normalize_paragraph_markers(self, *, text: str) -> str:
        """Normalize various paragraph marker formats."""
        # Ensure "Paragraph X:" always starts on a new line
        text = re.sub(r"(?<!\n)(Paragraph\s*\d+\s*:)", r"\n\1", text)
        # Remove numbered list prefixes
        text = re.sub(r"(?m)^\s*\d+\.\s+", "", text)
        # Normalize bracket formats
        text = re.sub(r"(?m)^\[[\s#]*Paragraph\b", "Paragraph", text)
        # Normalize markdown headers
        text = re.sub(r"(?m)^#+\s+Paragraph\b", "Paragraph", text)
        # Normalize colons and brackets
        return re.sub(r"Paragraph\s*(\d+)\s*[:\]]+", r"Paragraph \1:", text)

    def _extract_clean_summary(self, *, content: str) -> str:
        """Extract and clean summary content from raw paragraph text."""
        cleaned = content.strip()
        cleaned = re.sub(r"<<<\s*Paragraph\s*\d+\s*(?:START|END)\s*>>>", "", cleaned).replace("```", "")

        summary_lines = []
        for line in cleaned.splitlines():
            line = line.strip()
            if not line or self._is_meta_text(text=line):
                continue
            if self._is_word_counting_line(line=line):
                continue
            summary_lines.append(line)

        combined = " ".join(summary_lines).strip()

        # Remove leading colon and whitespace (common artifact from chat models)
        combined = re.sub(r"^\s*:\s*", "", combined)

        sentences = re.split(r"(?<=[.!?])\s+", combined)
        valid_sentences = [s.strip() for s in sentences if s.strip() and not self._is_meta_text(text=s.strip())]
        return " ".join(valid_sentences).strip()

    def _is_word_counting_line(self, *, line: str) -> bool:
        """Check if line is a word-counting artifact."""
        if len(line) >= 50:
            return False
        line_lower = line.lower()
        if "word" not in line_lower and "words" not in line_lower:
            return False
        return any(c.isdigit() for c in line)

    def _is_meta_text(self, *, text: str) -> bool:
        """Detect LLM meta commentary or instruction artifacts."""
        return bool(
            re.match(
                r"^(Let's|That's|Good|Provide|Check|Count|Try|Possible|We need|"
                r"assistant|Ensure|Make sure|Return only|Return|No extra)",
                text,
                re.IGNORECASE,
            )
        )
