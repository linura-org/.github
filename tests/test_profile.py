"""Adversarial regression cases for organization-profile validation."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_profile import validate_profile  # noqa: E402


class ProfileChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = (ROOT / "profile" / "README.md").read_text(encoding="utf-8")

    def assert_rejected(self, profile: str, reason: str) -> None:
        errors = validate_profile(profile, ROOT)
        self.assertTrue(any(reason in error for error in errors), errors)

    def test_canonical_profile(self) -> None:
        self.assertEqual(validate_profile(self.profile, ROOT), [])

    def test_missing_documentation_link(self) -> None:
        self.assert_rejected(self.profile.replace("https://linura.org/docs", "https://linura.org/removed"), "Missing canonical navigation link")

    def test_untrusted_external_destination(self) -> None:
        self.assert_rejected(self.profile + "\n[More](https://example.org/private)\n", "Unexpected external destination")

    def test_wrong_managed_order(self) -> None:
        self.assert_rejected(self.profile.replace("execute → verify → commit", "verify → execute → commit"), "canonical order")

    def test_missing_class_boundary(self) -> None:
        self.assert_rejected(self.profile.replace("`TransientExternalEffect`", "Transient effects"), "operation-class distinction")

    def test_bad_banner(self) -> None:
        self.assert_rejected(self.profile.replace("./assets/linura-new.png", "./assets/missing.png"), "canonical relative asset")

    def test_unexpected_raw_html(self) -> None:
        self.assert_rejected(self.profile + "\n<script>alert(1)</script>\n", "Unexpected raw HTML")

    def test_injected_html_handler(self) -> None:
        self.assert_rejected(self.profile.replace("<p align=\"center\">", "<p onclick=\"alert(1)\" align=\"center\">", 1), "Unexpected HTML attribute")

    def test_markdown_image(self) -> None:
        self.assert_rejected(self.profile + "\n![third party](https://example.org/image.png)\n", "Markdown images")

    def test_unsupported_release_claim(self) -> None:
        self.assert_rejected(self.profile + "\nv9.2.0 is fully supported.\n", "version-specific support claims")

    def test_allowed_titled_markdown_link(self) -> None:
        self.assertEqual(validate_profile(self.profile + '\n[More](https://linura.org/docs "title")\n', ROOT), [])

    def test_allowed_reference_markdown_link(self) -> None:
        self.assertEqual(validate_profile(self.profile + '\n[More][docs]\n\n[docs]: https://linura.org/docs "Docs"\n', ROOT), [])

    def test_titled_markdown_link_cannot_bypass_allowlist(self) -> None:
        self.assert_rejected(self.profile + '\n[More](https://example.org "title")\n', "Unexpected external destination")

    def test_reference_markdown_link_cannot_bypass_allowlist(self) -> None:
        self.assert_rejected(self.profile + '\n[More][ref]\n\n[ref]: https://example.org "title"\n', "Unexpected external destination")

    def test_collapsed_reference_cannot_bypass_allowlist(self) -> None:
        self.assert_rejected(self.profile + '\n[More][]\n\n[more]: https://example.org\n', "Unexpected external destination")

    def test_hidden_html_comment_is_rejected(self) -> None:
        self.assert_rejected(self.profile + "\n<!-- [Hidden Docs](https://linura.org/docs) -->\n", "HTML comments are not permitted")

    def test_github_sibling_repository_is_rejected(self) -> None:
        self.assert_rejected(self.profile + "\n[Fake](https://github.com/linura-org/linura-phish)\n", "Unexpected GitHub destination")

    def test_github_other_repo_is_rejected(self) -> None:
        self.assert_rejected(self.profile + "\n[Other](https://github.com/linura-org/linura-platform)\n", "Unexpected GitHub destination")

    def test_traversal_path_is_rejected(self) -> None:
        self.assert_rejected(self.profile + "\n[Other](https://github.com/linura-org/linura/../linura-phish)\n", "Noncanonical path")

    def test_encoded_path_is_rejected(self) -> None:
        self.assert_rejected(self.profile + "\n[Other](https://github.com/linura-org/linura%2F-phish)\n", "Encoded")

    def test_explicit_port_is_rejected(self) -> None:
        self.assert_rejected(self.profile + "\n[Other](https://github.com:443/linura-org/linura)\n", "Unexpected credentials, port")

    def test_unreviewed_bare_url_is_rejected(self) -> None:
        self.assert_rejected(self.profile + "\nhttps://example.org\n", "Bare URLs")

    def test_untrusted_html_anchor_is_rejected(self) -> None:
        self.assert_rejected(self.profile + '\n<a href="https://example.org">more</a>\n', "Unexpected external destination")

    def test_hidden_html_anchor_is_rejected(self) -> None:
        self.assert_rejected(self.profile + '\n<a style="display:none" href="https://linura.org/docs">Docs</a>\n', "Unexpected HTML attribute")

    def test_untrusted_autolink_is_rejected(self) -> None:
        self.assert_rejected(self.profile + "\n<https://example.org>\n", "Unexpected external destination")

    def test_markdown_code_is_not_a_link(self) -> None:
        self.assertEqual(validate_profile(self.profile + "\n    [Not a link](https://example.org)\n", ROOT), [])



if __name__ == "__main__":
    unittest.main()
