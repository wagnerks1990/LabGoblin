import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sync_wiki import rewrite_target, sync


class WikiSyncTests(unittest.TestCase):
    def test_relative_links_assets_and_external_urls(self):
        pages = {"docs/operations/deployment.md": "Docs-operations-deployment"}
        self.assertEqual(
            rewrite_target("operations/deployment.md#setup", "docs/index.md", pages),
            "Docs-operations-deployment#setup",
        )
        self.assertEqual(rewrite_target("#setup", "docs/index.md", pages), "#setup")
        self.assertEqual(
            rewrite_target("https://example.com", "docs/index.md", pages),
            "https://example.com",
        )
        self.assertEqual(
            rewrite_target("../assets/logo.svg", "docs/index.md", pages),
            "https://github.com/wagnerks1990/LabGoblin/blob/main/assets/logo.svg",
        )

    def test_tracked_documents_only_and_preserve_custom_pages(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, destination = root / "repo", root / "wiki"
            (source / "docs").mkdir(parents=True)
            destination.mkdir()
            (source / "docs/index.md").write_text(
                "[Guide](guide.md)\n[ref]: guide.md\n"
            )
            (source / "docs/guide.md").write_text("# Guide\n")
            (source / "docs/private.md").write_text("untracked document")
            (destination / "Custom.md").write_text("Preserve unique work")
            with patch("scripts.sync_wiki.subprocess.check_output") as tracked:
                tracked.return_value = "docs/index.md\0docs/guide.md\0"
                self.assertEqual(sync(source, destination), 2)
            self.assertEqual(
                (destination / "Home.md").read_text(),
                "[Guide](Docs-guide)\n[ref]: Docs-guide\n",
            )
            self.assertFalse((destination / "Docs-private.md").exists())
            self.assertEqual(
                (destination / "Custom.md").read_text(), "Preserve unique work"
            )

    def test_repository_escape_is_rejected(self):
        with self.assertRaises(ValueError):
            rewrite_target("../../private.md", "docs/index.md", {})

    def test_colliding_page_names_fail_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "wiki"
            with patch("scripts.sync_wiki.subprocess.check_output") as tracked:
                tracked.return_value = "docs/index.md\0docs/a-b.md\0docs/a/b.md\0"
                with self.assertRaises(ValueError):
                    sync(Path(folder), destination)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
