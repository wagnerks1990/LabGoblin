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
