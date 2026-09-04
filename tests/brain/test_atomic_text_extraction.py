from atlas.brain.atomic_text_extraction import (
    chunk_text,
    extract_atomic_evidence_from_text,
)


class _FakeProvider:
    name = "fake"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete_structured(self, prompt, fields):
        self.calls.append((prompt, fields))
        return self.responses.pop(0)


def test_chunk_text_preserves_every_real_line_exactly_once():
    text = "\n".join(
        [
            "line one alpha",
            "line two beta",
            "line three gamma",
            "line four delta",
        ]
    )

    chunks = chunk_text(text, max_chars=30)

    assert len(chunks) >= 2
    reconstructed = []
    covered_lines = []

    for chunk in chunks:
        reconstructed.extend(chunk.text.splitlines())
        covered_lines.extend(range(chunk.start_line, chunk.end_line + 1))

    assert reconstructed == text.splitlines()
    assert covered_lines == [1, 2, 3, 4]


def test_exact_quote_becomes_atomic_with_real_line_locator():
    text = (
        "Intro line.\n"
        "Customers repeatedly complain about slow delivery.\n"
        "Another line."
    )

    provider = _FakeProvider(
        [
            {
                "atomic_1_statement": "Customers report slow delivery.",
                "atomic_1_quote": "Customers repeatedly complain about slow delivery.",
                "atomic_2_statement": "",
                "atomic_2_quote": "",
            }
        ]
    )

    atomics = extract_atomic_evidence_from_text(
        text,
        "identify customer pain",
        provider,
        max_chunk_chars=1000,
        max_atomics_per_chunk=2,
    )

    assert len(atomics) == 1
    assert atomics[0].description == "Customers report slow delivery."
    assert atomics[0].locator == "lines:2"


def test_hallucinated_or_modified_quote_is_rejected_fail_closed():
    text = "The report states revenue increased by 12 percent."

    provider = _FakeProvider(
        [
            {
                "atomic_1_statement": "Revenue increased.",
                # Not character-for-character present in the real text.
                "atomic_1_quote": "Revenue increased by twelve percent.",
            }
        ]
    )

    atomics = extract_atomic_evidence_from_text(
        text,
        "find growth evidence",
        provider,
        max_atomics_per_chunk=1,
    )

    assert atomics == []


def test_multiline_exact_quote_gets_real_line_range():
    text = (
        "Header\n"
        "First supporting sentence.\n"
        "Second supporting sentence.\n"
        "Footer"
    )

    quote = "First supporting sentence.\nSecond supporting sentence."
    provider = _FakeProvider(
        [
            {
                "atomic_1_statement": "Two supporting statements appear together.",
                "atomic_1_quote": quote,
            }
        ]
    )

    atomics = extract_atomic_evidence_from_text(
        text,
        "extract evidence",
        provider,
        max_atomics_per_chunk=1,
    )

    assert len(atomics) == 1
    assert atomics[0].locator == "lines:2-3"


def test_multiple_real_chunks_are_each_analyzed():
    text = (
        "A1 real demand signal\n"
        "A2 more text\n"
        "B1 competitor weakness\n"
        "B2 more text"
    )

    provider = _FakeProvider(
        [
            {
                "atomic_1_statement": "Demand signal exists.",
                "atomic_1_quote": "A1 real demand signal",
            },
            {
                "atomic_1_statement": "Competitor weakness exists.",
                "atomic_1_quote": "B1 competitor weakness",
            },
        ]
    )

    atomics = extract_atomic_evidence_from_text(
        text,
        "find demand and competitor weaknesses",
        provider,
        max_chunk_chars=35,
        max_atomics_per_chunk=1,
    )

    assert len(provider.calls) == 2
    assert len(atomics) == 2
    assert atomics[0].locator == "lines:1"
    assert atomics[1].locator == "lines:3"


def test_duplicate_atomic_from_same_chunk_is_not_returned_twice():
    text = "One exact fact appears here."

    provider = _FakeProvider(
        [
            {
                "atomic_1_statement": "A fact appears.",
                "atomic_1_quote": "One exact fact appears here.",
                "atomic_2_statement": "A fact appears.",
                "atomic_2_quote": "One exact fact appears here.",
            }
        ]
    )

    atomics = extract_atomic_evidence_from_text(
        text,
        "find facts",
        provider,
        max_atomics_per_chunk=2,
    )

    assert len(atomics) == 1


def test_verified_exact_quote_is_preserved_as_evidence_excerpt():
    text = "Users say setup takes too long."

    provider = _FakeProvider(
        [
            {
                "atomic_1_statement": "Setup friction is reported.",
                "atomic_1_quote": "Users say setup takes too long.",
            }
        ]
    )

    atomics = extract_atomic_evidence_from_text(
        text,
        "identify friction",
        provider,
        max_atomics_per_chunk=1,
    )

    assert len(atomics) == 1
    assert atomics[0].evidence_excerpt == "Users say setup takes too long."


def test_source_native_locator_prefix_is_preserved():
    text = "Exact evidence on this source-native segment."

    provider = _FakeProvider(
        [
            {
                "atomic_1_statement": "Evidence exists.",
                "atomic_1_quote": "Exact evidence on this source-native segment.",
            }
        ]
    )

    atomics = extract_atomic_evidence_from_text(
        text,
        "find evidence",
        provider,
        max_atomics_per_chunk=1,
        locator_prefix="page:18",
    )

    assert len(atomics) == 1
    assert atomics[0].locator == "page:18;lines:1"
    assert (
        atomics[0].evidence_excerpt
        == "Exact evidence on this source-native segment."
    )
