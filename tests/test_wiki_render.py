"""Local link regression checks for Wiki publication."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "render_wiki", Path(__file__).parents[1] / "scripts" / "render_wiki.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_nested_links_and_home_are_resolved_without_touching_external_urls(tmp_path):
    docs = tmp_path / "docs"
    (docs / "operations").mkdir(parents=True)
    (docs / "index.md").write_text("[Console](operations/consoles.md#security)")
    (docs / "operations" / "consoles.md").write_text(
        "[Home](../index.md) [Web](https://example.test/a.md) [Anchor](#local)"
    )
    output = tmp_path / "wiki"
    output.mkdir()
    (output / "Existing.md").write_text("Preserve unique work")
    module.render(docs, output)
    assert (
        output / "Home.md"
    ).read_text() == "[Console](operations--consoles#security)"
    assert (output / "operations--consoles.md").read_text() == (
        "[Home](Home) [Web](https://example.test/a.md) [Anchor](#local)"
    )
    assert (output / "Existing.md").read_text() == "Preserve unique work"
