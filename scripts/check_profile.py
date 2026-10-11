#!/usr/bin/env python3
"""Deterministic checks for the public GitHub organization profile."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import urlsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile" / "README.md"
MANAGED_STAGES = (
    "request / intent", "observe", "plan", "validate", "authorize", "prepare",
    "execute", "verify", "commit", "audit", "reconcile",
)
MARKDOWN = MarkdownIt("commonmark", {"html": True})
ALLOWED_ATTRIBUTES = {
    "p": frozenset({"align"}),
    "strong": frozenset(),
    "a": frozenset({"href", "title"}),
    "img": frozenset({"src", "alt", "width"}),
}
REQUIRED_LINKS = frozenset({
    "https://linura.org",
    "https://linura.org/docs",
    "https://github.com/linura-org/linura",
    "https://github.com/linura-org/linura/blob/main/docs/action-lifecycle.md",
    "https://github.com/linura-org/linura/blob/main/docs/architecture.md",
    "https://github.com/linura-org/linura/blob/main/docs/roadmap.md",
    "https://github.com/linura-org/linura/blob/main/CONTRIBUTING.md",
    "https://github.com/linura-org/linura/security/policy",
    "https://github.com/linura-org/linura/releases",
})


class ProfileHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.images: list[tuple[str, str]] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_ATTRIBUTES:
            self.errors.append(f"Unexpected raw HTML tag: {tag}")
            return
        attributes = dict(attrs)
        if len(attributes) != len(attrs):
            self.errors.append(f"Duplicate HTML attribute on {tag}")
        for name in attributes:
            if name not in ALLOWED_ATTRIBUTES[tag]:
                self.errors.append(f"Unexpected HTML attribute on {tag}: {name}")
        if tag == "a":
            if not attributes.get("href"):
                self.errors.append("Raw HTML anchor requires an href")
            else:
                self.links.append(attributes["href"] or "")
        if tag == "img":
            self.images.append((attributes.get("src") or "", attributes.get("alt") or ""))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_comment(self, data: str) -> None:
        self.errors.append("HTML comments are not permitted in the public profile")

    def handle_data(self, data: str) -> None:
        if re.search(r"(?i)\b(?:https?://|www\.)", data):
            self.errors.append("Bare URLs in HTML must use validated links")


def collect_links(markdown: str) -> tuple[set[str], list[tuple[str, str]], list[str]]:
    """Parse rendered CommonMark links, including titles and references."""
    links: set[str] = set()
    markup = ProfileHTML()
    errors: list[str] = []
    link_depth = 0

    def visit(tokens: list) -> None:
        nonlocal link_depth
        for token in tokens:
            if token.type == "link_open":
                link_depth += 1
                links.add(token.attrGet("href") or "")
            elif token.type == "link_close":
                link_depth -= 1
            elif token.type == "image":
                errors.append("Markdown images are not permitted; use the checked canonical banner")
            elif token.type in ("html_inline", "html_block"):
                markup.feed(token.content)
            elif token.type == "text" and link_depth == 0:
                if re.search(r"(?i)\b(?:https?://|www\.)", token.content):
                    errors.append("Bare URLs must use validated Markdown or HTML links")
            if token.children:
                visit(token.children)

    visit(MARKDOWN.parse(markdown))
    links.update(markup.links)
    errors.extend(markup.errors)
    if link_depth != 0:
        errors.append("Unbalanced rendered Markdown link tokens")
    return links, markup.images, errors


def validate_url(link: str) -> list[str]:
    errors: list[str] = []
    if re.search(r"[%\\\x00-\x1f\x7f]", link):
        errors.append(f"Encoded, escaped, or control characters in public URL: {link}")
    try:
        parsed = urlsplit(link)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return [f"Malformed public URL: {link}"]
    if parsed.scheme != "https" or not hostname:
        errors.append(f"Non-HTTPS or malformed public link: {link}")
    elif hostname == "github.com":
        if parsed.path != "/linura-org/linura" and not parsed.path.startswith("/linura-org/linura/"):
            errors.append(f"Unexpected GitHub destination: {link}")
    elif hostname != "linura.org":
        errors.append(f"Unexpected external destination: {link}")
    if parsed.username or parsed.password or port is not None or parsed.netloc.lower() != hostname:
        errors.append(f"Unexpected credentials, port, or hostname syntax in public link: {link}")
    if parsed.query or "//" in parsed.path or any(s in (".", "..") for s in parsed.path.split("/")):
        errors.append(f"Noncanonical path or query in public link: {link}")
    return errors


def validate_profile(markdown: str, root: Path) -> list[str]:
    errors: list[str] = []
    links, images, errors = collect_links(markdown)
    for link in sorted(links):
        errors.extend(validate_url(link))
    for link in sorted(REQUIRED_LINKS - links):
        errors.append(f"Missing canonical navigation link: {link}")

    if len(images) != 1:
        errors.append("Expected exactly one organization banner image")
    else:
        src, alt = images[0]
        if src != "./assets/linura-new.png" or not alt.strip():
            errors.append("Banner must use the canonical relative asset with descriptive alt text")
        elif not (root / "profile" / "assets" / "linura-new.png").is_file():
            errors.append("Canonical organization banner asset does not exist")

    diagrams = [
        token.content for token in MARKDOWN.parse(markdown)
        if token.type == "fence" and token.info.strip() == "text"
    ]
    stage_pattern = r"(?<![A-Za-z])(?:" + "|".join(
        re.escape(stage) for stage in MANAGED_STAGES
    ) + r")(?![A-Za-z])"
    observed_stages = [
        stage for diagram in diagrams for stage in re.findall(stage_pattern, diagram)
    ]
    if observed_stages != list(MANAGED_STAGES):
        errors.append("Managed lifecycle must appear exactly once in canonical order")
    for op_class in ("TransientExternalEffect", "ManagedExternalEffect"):
        if f"`{op_class}`" not in markdown:
            errors.append(f"Missing trusted operation-class distinction: {op_class}")
    if "Only managed external effects follow this complete lifecycle" not in markdown:
        errors.append("Lifecycle must be explicitly scoped to managed effects")
    if not all(word in markdown.lower() for word in ("unprivileged", "plan-bound", "independent verification")):
        errors.append("Transient-effect authority constraints are incomplete")
    if "experimental" not in markdown.lower() or "pre-1.0" not in markdown.lower():
        errors.append("Missing pre-1.0 experimental support caveat")
    if re.search(r"\bv\d+\.\d+(?:\.\d+)?\b", markdown, re.IGNORECASE):
        errors.append("Do not duplicate version-specific support claims in the profile")
    return errors


def main() -> int:
    errors = validate_profile(PROFILE.read_text(encoding="utf-8"), ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Organization profile checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
