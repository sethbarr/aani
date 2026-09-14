"""Locate copied paper text in cached source blocks without fuzzy matching."""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


def sha256(data: bytes) -> str:
    """Return the SHA-256 digest of exact bytes."""
    return hashlib.sha256(data).hexdigest()


def words(text: str) -> list[tuple[str, int, int]]:
    """Tokenize alphanumeric words while preserving character offsets.

    Args:
        text: Text to scan without altering its stored representation.

    Returns:
        Lowercase words with start and exclusive end character offsets.
    """
    tokens = []
    start = None
    for offset, character in enumerate(text):
        if character.isalnum():
            if start is None:
                start = offset
        elif start is not None:
            tokens.append((text[start:offset].casefold(), start, offset))
            start = None
    if start is not None:
        tokens.append((text[start:].casefold(), start, len(text)))
    return tokens


@dataclass
class SourceBlock:
    """One privately cached paper block and its attribution."""

    source_id: str
    block_id: str
    path: str
    file_sha256: str
    text: str
    kind: str

    def reference(self, start: int, end: int) -> dict:
        """Describe a span using offsets in decoded block UTF-8 bytes."""
        return {
            "source_id": self.source_id,
            "block_id": self.block_id,
            "private_source_path": self.path,
            "source_file_sha256": self.file_sha256,
            "block_text_sha256": sha256(self.text.encode()),
            "block_utf8_byte_start": len(self.text[:start].encode()),
            "block_utf8_byte_end": len(self.text[:end].encode()),
            "span_sha256": sha256(self.text[start:end].encode()),
            "source_words": len(self.text[start:end].split()),
            "kind": self.kind,
        }


class SourceIndex:
    """Index exact word sequences from all locally cached paper corpora."""

    def __init__(self, root: Path, width: int = 6) -> None:
        """Load unique blocks and create a conservative overlap index."""
        self.width = width
        self.blocks: list[SourceBlock] = []
        self.tokens: list[list[tuple[str, int, int]]] = []
        self.grams: dict[tuple[str, ...], list[tuple[int, int]]] = defaultdict(list)
        seen = set()
        for path in sorted((root / "data/interim").glob("**/texts/*.json")):
            if "publication_safety" in path.parts:
                continue
            raw = path.read_bytes()
            data = json.loads(raw)
            for row in data.get("blocks", []):
                text = row.get("text", "")
                key = (data.get("source_id", row.get("source_id")),
                       row.get("block_id"), sha256(text.encode()))
                if key in seen or not text:
                    continue
                seen.add(key)
                block = SourceBlock(str(key[0]), str(key[1]), str(path.relative_to(root)),
                                    sha256(raw), text, row.get("kind", "unknown"))
                self.blocks.append(block)
                tokens = words(text)
                self.tokens.append(tokens)
                block_index = len(self.blocks) - 1
                for index in range(len(tokens) - width + 1):
                    gram = tuple(token[0] for token in tokens[index:index + width])
                    self.grams[gram].append((block_index, index))

    def matches(self, text: str, minimum_words: int = 6) -> list[dict]:
        """Locate maximal word-sequence overlaps and retain source attribution.

        This detector supports publication review only. It never changes the
        extraction validator or its matching rules.
        """
        tokens = words(text)
        found: list[dict] = []
        seen: set[tuple[int, int, int]] = set()
        covered: dict[int, int] = {}
        for index in range(len(tokens) - self.width + 1):
            gram = tuple(token[0] for token in tokens[index:index + self.width])
            for block_index, source_index in self.grams.get(gram, []):
                if index < covered.get(block_index, -1):
                    continue
                source_tokens = self.tokens[block_index]
                length = self.width
                while (index + length < len(tokens)
                       and source_index + length < len(source_tokens)
                       and tokens[index + length][0] == source_tokens[source_index + length][0]):
                    length += 1
                if length < minimum_words:
                    continue
                start, end = tokens[index][1], tokens[index + length - 1][2]
                key = (block_index, start, end)
                if key in seen:
                    continue
                seen.add(key)
                covered[block_index] = index + length
                reference = self.blocks[block_index].reference(
                    source_tokens[source_index][1], source_tokens[source_index + length - 1][2])
                found.append({"start": start, "end": end, "token_count": length,
                              "reference": reference})
        return found

    def exact_references(self, text: str, source_id: str | None = None) -> list[dict]:
        """Return every exact block span for an attributed quotation."""
        if not text.strip():
            return []
        found = []
        for block in self.blocks:
            if source_id and block.source_id != source_id:
                continue
            start = block.text.find(text)
            while start >= 0:
                found.append(block.reference(start, start + len(text)))
                start = block.text.find(text, start + 1)
        return found
