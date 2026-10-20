import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scripts.auto_add_playable_sources as source_updater


class PlayableConfigTests(unittest.TestCase):
    def test_requires_site_with_api_or_url(self):
        self.assertTrue(
            source_updater.is_playable_config(
                {"sites": [{"key": "source", "api": "csp_Test"}]}
            )
        )
        self.assertFalse(source_updater.is_playable_config({"sites": []}))
        self.assertFalse(source_updater.is_playable_config({"sites": [{"key": "x"}]}))
        self.assertFalse(source_updater.is_playable_config({"urls": []}))

    def test_encodes_internationalized_urls(self):
        self.assertEqual(
            source_updater.encode_url("http://饭太硬.ga/x/配置.json"),
            "http://xn--sss604efuw.ga/x/%E9%85%8D%E7%BD%AE.json",
        )

    def test_local_candidates_use_github_pages_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "源" / "测试.json"
            config.parent.mkdir()
            config.write_text(
                json.dumps({"sites": [{"api": "csp_Test"}]}), encoding="utf-8"
            )
            with (
                patch.object(source_updater, "ROOT", root),
                patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}),
            ):
                candidates = source_updater.local_candidates()

        self.assertEqual(
            candidates,
            [
                {
                    "name": "自动收录 · 源/测试",
                    "url": "https://owner.github.io/repo/%E6%BA%90/%E6%B5%8B%E8%AF%95.json",
                }
            ],
        )

    def test_manifest_update_is_idempotent_and_preserves_existing_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "manifest.json"
            original = {"urls": [{"name": "manual", "url": "https://existing.test"}]}
            target.write_text(json.dumps(original), encoding="utf-8")
            candidate = {"name": "new", "url": "https://new.test/config.json"}
            with patch.object(source_updater, "TARGET", target):
                self.assertEqual(source_updater.update_manifest([candidate]), 1)
                self.assertEqual(source_updater.update_manifest([candidate]), 0)
            result = json.loads(target.read_text(encoding="utf-8"))

        self.assertEqual(result["urls"], [original["urls"][0], candidate])


if __name__ == "__main__":
    unittest.main()
