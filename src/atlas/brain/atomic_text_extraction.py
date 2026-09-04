"""Stage 7 grounded atomic extraction from real text.

This module does NOT summarize a source and does NOT persist knowledge.
It converts real raw text into transient AtomicEvidence units that are
accepted only when each unit cites an exact quote that really exists in
the chunk it came from.

Pipeline:
raw text -> deterministic chunks -> structured extraction ->
exact-quote verification -> exact line locator -> AtomicEvidence

Unsupported / hallucinated claims are discarded fail-closed.
"""

from dataclasses import dataclass

from atlas.brain.atomic_evidence import AtomicEvidence
from atlas.integrations.base import AIProvider


MAX_CHUNK_CHARS = 6000
MAX_ATOMICS_PER_CHUNK = 5


@dataclass(frozen=True)
class TextChunk:
    text: str
    start_line: int
    end_line: int


def chunk_text(
    text: str,
    max_chars: int = MAX_CHUNK_CHARS,
) -> list[TextChunk]:
    """Split text deterministically on real line boundaries.

    Every original line belongs to exactly one chunk. No overlap is used
    in V1 so duplicate evidence is not manufactured by chunk overlap.
    Extremely long single lines remain one chunk rather than being
    silently rewritten into artificial line boundaries.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be positive")

    lines = text.splitlines()
    if not lines:
        return []

    chunks: list[TextChunk] = []
    current: list[str] = []
    current_chars = 0
    start_line = 1

    for index, line in enumerate(lines, start=1):
        added_chars = len(line) + (1 if current else 0)

        if current and current_chars + added_chars > max_chars:
            chunks.append(
                TextChunk(
                    text="\n".join(current),
                    start_line=start_line,
                    end_line=index - 1,
                )
            )
            current = [line]
            current_chars = len(line)
            start_line = index
        else:
            current.append(line)
            current_chars += added_chars

    if current:
        chunks.append(
            TextChunk(
                text="\n".join(current),
                start_line=start_line,
                end_line=len(lines),
            )
        )

    return chunks


def _quote_line_range(chunk: TextChunk, quote: str) -> tuple[int, int] | None:
    """Locate an exact quote inside its real chunk and map it to lines."""
    if not quote or quote not in chunk.text:
        return None

    start_char = chunk.text.find(quote)
    end_char = start_char + len(quote)

    before = chunk.text[:start_char]
    through = chunk.text[:end_char]

    relative_start = before.count("\n") + 1
    relative_end = through.count("\n") + 1

    return (
        chunk.start_line + relative_start - 1,
        chunk.start_line + relative_end - 1,
    )


def _extract_from_chunk(
    chunk: TextChunk,
    task_description: str,
    provider: AIProvider,
    max_atomics: int,
    locator_prefix: str = "",
) -> list[AtomicEvidence]:
    fields: dict[str, str] = {}

    for i in range(1, max_atomics + 1):
        fields[f"atomic_{i}_statement"] = (
            "one concise factual observation directly supported by this "
            "exact text chunk; empty if no additional useful observation exists"
        )
        fields[f"atomic_{i}_quote"] = (
            "an exact verbatim quote copied from this chunk that directly "
            "supports atomic_{i}_statement; must appear character-for-character "
            "in the chunk; empty if no exact supporting quote exists"
        )

    prompt = (
        "Extract atomic research evidence from the following REAL source text.\n"
        "Do not summarize the whole source. Do not infer beyond what the text "
        "directly supports. Every statement MUST have an exact verbatim quote "
        "from this chunk. If you cannot cite an exact quote, leave that item "
        "empty. Prefer observations relevant to the research task.\n\n"
        f"RESEARCH TASK:\n{task_description}\n\n"
        f"REAL TEXT CHUNK (lines {chunk.start_line}-{chunk.end_line}):\n"
        f"{chunk.text}"
    )

    raw = provider.complete_structured(prompt, fields)
    atomics: list[AtomicEvidence] = []
    seen: set[tuple[str, str]] = set()

    for i in range(1, max_atomics + 1):
        statement = raw.get(f"atomic_{i}_statement", "").strip()
        quote = raw.get(f"atomic_{i}_quote", "").strip()

        if not statement or not quote:
            continue

        line_range = _quote_line_range(chunk, quote)
        if line_range is None:
            # Fail closed: unsupported / altered / hallucinated quote.
            continue

        start_line, end_line = line_range
        key = (statement, quote)
        if key in seen:
            continue
        seen.add(key)

        line_locator = (
            f"lines:{start_line}"
            if start_line == end_line
            else f"lines:{start_line}-{end_line}"
        )
        locator = (
            f"{locator_prefix};{line_locator}"
            if locator_prefix
            else line_locator
        )

        atomics.append(
            AtomicEvidence(
                description=statement,
                locator=locator,
                evidence_excerpt=quote,
            )
        )

    return atomics


def extract_atomic_evidence_from_text(
    text: str,
    task_description: str,
    ai_provider: AIProvider,
    *,
    max_chunk_chars: int = MAX_CHUNK_CHARS,
    max_atomics_per_chunk: int = MAX_ATOMICS_PER_CHUNK,
    locator_prefix: str = "",
) -> list[AtomicEvidence]:
    """Extract grounded atomic evidence from all chunks of real text."""
    if not task_description.strip():
        raise ValueError("task_description must be non-empty")
    if not 1 <= max_atomics_per_chunk <= 10:
        raise ValueError("max_atomics_per_chunk must be between 1 and 10")

    atomics: list[AtomicEvidence] = []

    for chunk in chunk_text(text, max_chars=max_chunk_chars):
        atomics.extend(
            _extract_from_chunk(
                chunk,
                task_description,
                ai_provider,
                max_atomics_per_chunk,
                locator_prefix=locator_prefix,
            )
        )

    return atomics
