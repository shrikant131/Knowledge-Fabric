from knowledge_fabric.chunking.doc_chunker import split_doc_sections


def test_splits_by_markdown_headings():
    text = "# Intro\n\nHello.\n\n## Details\n\nMore text here.\n"
    sections = split_doc_sections(text)
    titles = [t for t, _ in sections]
    assert "Intro" in titles
    assert "Details" in titles


def test_no_headings_falls_back_to_single_document_section():
    text = "Just some plain text with no headings at all."
    sections = split_doc_sections(text)
    assert len(sections) == 1
    assert sections[0][0] == "<document>"


def test_long_section_is_split_into_parts():
    long_body = "\n\n".join([f"Paragraph {i} " + ("word " * 50) for i in range(20)])
    text = f"# Big Section\n\n{long_body}\n"
    sections = split_doc_sections(text, max_chars=500)
    big_section_parts = [t for t, _ in sections if t.startswith("Big Section")]
    assert len(big_section_parts) > 1
    # every part should individually respect the size budget (with some slack
    # since we split on paragraph boundaries, not mid-paragraph)
    for _, body in sections:
        assert len(body) < 1200
