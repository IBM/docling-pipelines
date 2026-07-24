"""
Readability metrics implementation using pyphen for syllable counting.
Provides all standard readability formulas using pyphen and basic regex for tokenization.
"""

import math
import os
import re
from typing import Any

from pyphen import Pyphen

from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

# Text statistics dictionary keys
WORDS = "words"
SENTENCES = "sentences"
SYLLABLES = "syllables"
COMPLEX_WORDS = "complex_words"
CHARACTERS = "characters"
WORD_LIST = "word_list"
DIFFICULT_WORDS = "difficult_words"


def split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in sentences if s]


# Load easy words list
current_dir = os.path.dirname(os.path.abspath(__file__))
easy_words_path = os.path.join(current_dir, "easy_words.txt")
with open(easy_words_path) as _f:
    EASY_WORDS: set[str] = {word.strip() for word in _f if word.strip()}


class ReadabilityMetrics:
    """
    Readability metrics calculator using pyphen for syllable counting.
    Implements all major readability formulas.
    """

    def __init__(self, *, lang: str = "en_US") -> None:
        self.dic = Pyphen(lang=lang)
        self.easy_words = EASY_WORDS

    def get_words(self, *, text: str) -> list[str]:
        """Extract words from text using regex."""
        return re.findall(r"\b[a-zA-Z]+\b", text.lower())

    def count_syllables(self, *, word: str) -> int:
        """Count syllables in a word using pyphen. Returns at least 1 syllable per word."""
        word = word.lower().strip()
        if not word:
            return 0
        hyphenated = self.dic.inserted(word)
        syllable_count = hyphenated.count("-") + 1
        return max(1, syllable_count)

    def count_syllables_in_text(self, *, words: list[str]) -> int:
        """Count total syllables in a list of words."""
        return sum(self.count_syllables(word=w) for w in words)

    def count_characters(self, *, words: list[str]) -> int:
        """Count total characters in words (excluding spaces)."""
        return sum(len(w) for w in words)

    def count_complex_words(self, *, words: list[str], syllable_threshold: int = 3) -> int:
        """Count complex words (words with 3+ syllables by default)."""
        return sum(1 for w in words if self.count_syllables(word=w) >= syllable_threshold)

    def count_difficult_words(self, *, words: list[str]) -> int:
        """Count words not in easy word list."""
        return sum(1 for w in words if w.lower() not in self.easy_words)

    def text_stats(self, *, text: str) -> dict[str, Any]:
        """Calculate comprehensive text statistics."""
        words = self.get_words(text=text)
        sentences = split_sentences(text)
        syllables = self.count_syllables_in_text(words=words)
        complex_words = self.count_complex_words(words=words)
        characters = self.count_characters(words=words)
        difficult_words_count = self.count_difficult_words(words=words)
        return {
            WORDS: len(words),
            SENTENCES: max(1, len(sentences)),
            SYLLABLES: syllables,
            COMPLEX_WORDS: complex_words,
            CHARACTERS: characters,
            WORD_LIST: words,
            DIFFICULT_WORDS: difficult_words_count,
        }

    def flesch_reading_ease(self, *, stats: dict[str, Any]) -> float:
        words_count = stats[WORDS]
        sentences_count = stats[SENTENCES]
        syllables_count = stats[SYLLABLES]
        if words_count == 0:
            return 0.0
        return 206.835 - 1.015 * (words_count / sentences_count) - 84.6 * (syllables_count / words_count)

    def flesch_kincaid_grade(self, *, stats: dict[str, Any]) -> float:
        words_count = stats[WORDS]
        sentences_count = stats[SENTENCES]
        syllables_count = stats[SYLLABLES]
        if words_count == 0:
            return 0.0
        return 0.39 * (words_count / sentences_count) + 11.8 * (syllables_count / words_count) - 15.59

    def gunning_fog(self, *, stats: dict[str, Any]) -> float:
        words_count = stats[WORDS]
        sentences_count = stats[SENTENCES]
        complex_words_count = stats[COMPLEX_WORDS]
        if words_count == 0:
            return 0.0
        return 0.4 * ((words_count / sentences_count) + 100 * (complex_words_count / words_count))

    def smog_index(self, *, stats: dict[str, Any]) -> float:
        complex_words_count = stats[COMPLEX_WORDS]
        sentences_count = stats[SENTENCES]
        if sentences_count == 0:
            return 0.0
        return 1.043 * math.sqrt(complex_words_count * (30 / sentences_count)) + 3.1291

    def coleman_liau_index(self, *, stats: dict[str, Any]) -> float:
        words_count = stats[WORDS]
        chars_count = stats[CHARACTERS]
        sentences_count = stats[SENTENCES]
        if words_count == 0:
            return 0.0
        letters_per_100 = (chars_count / words_count) * 100
        sentences_per_100 = (sentences_count / words_count) * 100
        return 0.0588 * letters_per_100 - 0.296 * sentences_per_100 - 15.8

    def automated_readability_index(self, *, stats: dict[str, Any]) -> float:
        chars_count = stats[CHARACTERS]
        words_count = stats[WORDS]
        sentences_count = stats[SENTENCES]
        if words_count == 0:
            return 0.0
        return 4.71 * (chars_count / words_count) + 0.5 * (words_count / sentences_count) - 21.43

    def dale_chall_readability_score(self, *, stats: dict[str, Any]) -> float:
        words_count = stats[WORDS]
        sentences_count = stats[SENTENCES]
        difficult_words_count = stats[DIFFICULT_WORDS]
        if words_count == 0:
            return 0.0
        pct_difficult_words = (difficult_words_count / words_count) * 100
        avg_sentence_len = words_count / sentences_count
        score = 0.1579 * pct_difficult_words + 0.0496 * avg_sentence_len
        if pct_difficult_words > 5:
            score += 3.6365
        return score

    def difficult_words(self, *, stats: dict[str, Any]) -> int:
        return stats[DIFFICULT_WORDS]

    def linsear_write_formula(self, *, stats: dict[str, Any]) -> float:
        words = stats[WORD_LIST][:100]
        sentences = stats[SENTENCES]
        if not words:
            return 0.0
        easy = 0
        hard = 0
        for w in words:
            if self.count_syllables(word=w) < 3:
                easy += 1
            else:
                hard += 3
        score = (easy + hard) / max(1, sentences)
        if score > 20:
            score /= 2
        else:
            score = (score / 2) - 1
        return max(0, score)

    def text_standard(self, *, stats: dict[str, Any]) -> float:
        scores = [
            self.flesch_kincaid_grade(stats=stats),
            self.gunning_fog(stats=stats),
            self.smog_index(stats=stats),
            self.coleman_liau_index(stats=stats),
            self.automated_readability_index(stats=stats),
        ]
        avg = sum(scores) / len(scores)
        return round(avg, 1)

    def spache_readability(self, *, stats: dict[str, Any]) -> float:
        words_count = stats[WORDS]
        sentences_count = stats[SENTENCES]
        difficult_words_count = stats[DIFFICULT_WORDS]
        if words_count == 0:
            return 0.0
        avg_sentence_len = words_count / sentences_count
        pct_difficult_words = (difficult_words_count / words_count) * 100
        return 0.141 * avg_sentence_len + 0.086 * pct_difficult_words + 0.839

    def mcalpine_eflaw(self, *, stats: dict[str, Any]) -> float:
        words_count = stats[WORDS]
        sentences_count = stats[SENTENCES]
        words_list = stats[WORD_LIST]
        if sentences_count == 0:
            return 0.0
        miniwords_count = sum(1 for w in words_list if len(w) <= 3)
        return (words_count + miniwords_count) / sentences_count

    def reading_time(self, *, stats: dict[str, Any], wpm: int = 200) -> float:
        words_count = stats[WORDS]
        return words_count / wpm
