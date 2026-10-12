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


def test_freshness_guard_rejects_a_superseded_validated_commit(tmp_path):
    import subprocess

    remote = tmp_path / "repository"
    remote.mkdir()

    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(remote), *args], text=True
        ).strip()

    git("init", "-b", "main")
    git("config", "user.name", "Synthetic test")
    git("config", "user.email", "test@example.invalid")
    git("commit", "--allow-empty", "-m", "First validated revision")
    validated = git("rev-parse", "HEAD")
    guard = Path(__file__).parents[1] / "scripts" / "wiki_is_current.sh"
    assert subprocess.run([str(guard), validated, str(remote)]).returncode == 0
    git("commit", "--allow-empty", "-m", "Newer revision")
    assert subprocess.run([str(guard), validated, str(remote)]).returncode != 0


def test_removed_generated_pages_are_deleted_but_manual_pages_survive(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("Home")
    old = docs / "old.md"
    old.write_text("Obsolete generated page")
    output = tmp_path / "wiki"
    module.render(docs, output)
    (output / "Manual.md").write_text("Keep unique contributor work")
    old.unlink()
    module.render(docs, output)
    assert not (output / "old.md").exists()
    assert (output / "Manual.md").read_text() == "Keep unique contributor work"


def test_invalid_manifest_cannot_delete_files_outside_wiki(tmp_path):
    import pytest

    docs = tmp_path / "docs"
    docs.mkdir()
    output = tmp_path / "wiki"
    output.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Preserve")
    (output / ".labgoblin-generated-pages.json").write_text('["../outside.md"]')
    with pytest.raises(ValueError):
        module.render(docs, output)
    assert outside.read_text() == "Preserve"


def test_freshness_transport_failure_is_not_a_stale_revision(tmp_path):
    import subprocess

    guard = Path(__file__).parents[1] / "scripts" / "wiki_is_current.sh"
    result = subprocess.run([str(guard), "unknown", str(tmp_path / "missing")])
    assert result.returncode == 2
