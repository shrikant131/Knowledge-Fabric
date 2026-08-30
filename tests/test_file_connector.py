import textwrap

from knowledge_fabric.connectors.file_connector import FileConnector


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_fetch_picks_up_code_and_doc_files(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    return 1\n")
    _write(tmp_path, "b.md", "# Title\n\nSome text.\n")
    _write(tmp_path, "ignore.bin", "not text")  # unsupported extension

    connector = FileConnector(root_path=str(tmp_path), source_id="test_source")
    items = list(connector.fetch())
    item_ids = {i.item_id for i in items}

    assert "a.py" in item_ids
    assert "b.md" in item_ids
    assert "ignore.bin" not in item_ids


def test_detect_delta_only_returns_changed_items(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    return 1\n")
    connector = FileConnector(root_path=str(tmp_path), source_id="test_source")
    items = list(connector.fetch())

    # first run: no prior hashes, everything is "changed"
    changed = connector.detect_delta(items, seen_hashes={})
    assert len(changed) == 1

    # second run: seed seen_hashes with the current hash -> nothing changed
    seen = {items[0].item_id: items[0].content_hash}
    changed_again = connector.detect_delta(items, seen_hashes=seen)
    assert changed_again == []

    # modify the file -> should be detected as changed
    _write(tmp_path, "a.py", "def foo():\n    return 2\n")
    new_items = list(connector.fetch())
    changed_after_edit = connector.detect_delta(new_items, seen_hashes=seen)
    assert len(changed_after_edit) == 1


def test_parse_and_chunk_python_splits_by_function(tmp_path):
    source = textwrap.dedent("""
        def alpha():
            return 1

        def beta():
            return 2
    """).strip()
    _write(tmp_path, "funcs.py", source)
    connector = FileConnector(root_path=str(tmp_path), source_id="test_source")
    item = next(iter(connector.fetch()))
    doc = connector.parse(item)
    chunks = connector.chunk(doc)

    symbols = [c.symbol for c in chunks]
    assert any("alpha" in s for s in symbols)
    assert any("beta" in s for s in symbols)
    # each chunk should carry a citation label referencing the file
    assert all(c.item_id == "funcs.py" for c in chunks)


def test_chunk_ids_are_stable_across_runs(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    return 1\n")
    connector = FileConnector(root_path=str(tmp_path), source_id="test_source")
    item = next(iter(connector.fetch()))

    doc1 = connector.parse(item)
    chunks1 = connector.chunk(doc1)
    doc2 = connector.parse(item)
    chunks2 = connector.chunk(doc2)

    assert [c.chunk_id for c in chunks1] == [c.chunk_id for c in chunks2]
