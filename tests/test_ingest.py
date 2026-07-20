from rag.ingest import MAX_CHUNK_CHARS, chunk_document


def test_splits_on_headings():
    text = "# Title\n\nIntro para.\n\n## Section A\n\nBody A.\n\n## Section B\n\nBody B.\n"
    chunks = chunk_document("doc.md", text)
    headings = [c.heading for c in chunks]
    assert headings == ["Title", "Section A", "Section B"]
    assert chunks[1].text.strip() == "Body A."


def test_headingless_text_falls_back_to_paragraphs():
    text = "Para one.\n\nPara two.\n\nPara three."
    chunks = chunk_document("doc.txt", text)
    assert len(chunks) == 1
    assert chunks[0].heading == ""
    assert "Para one." in chunks[0].text and "Para three." in chunks[0].text


def test_long_section_splits_into_multiple_blocks():
    para_a = "a" * (MAX_CHUNK_CHARS - 100)
    para_b = "b" * (MAX_CHUNK_CHARS - 100)
    text = f"# Big\n\n{para_a}\n\n{para_b}"
    chunks = chunk_document("doc.md", text)
    assert len(chunks) == 2
    assert all(c.heading == "Big" for c in chunks)
    assert chunks[0].text == para_a
    assert chunks[1].text == para_b


def test_empty_sections_are_skipped():
    text = "# Empty\n\n\n\n# Real\n\nsome text"
    chunks = chunk_document("doc.md", text)
    assert [c.heading for c in chunks] == ["Real"]
