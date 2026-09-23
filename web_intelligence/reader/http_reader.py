"""Safe HTTP Page Reader with robust HTML text extraction."""

from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Set
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .base import PageReader
from ..models import PageContent
from ..telemetry import log_error, log_info, log_warning, sanitize

IGNORED_TAGS: Set[str] = {
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "svg",
    "iframe",
    "noscript",
    "object",
    "embed",
}


class HTMLTextExtractor(HTMLParser):
    """Cleanly extracts titles, paragraphs, headings, and lists while stripping boilerplates."""

    def __init__(self) -> None:
        super().__init__()
        self._ignore_depth = 0
        self._title_depth = 0
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in IGNORED_TAGS:
            self._ignore_depth += 1
        elif tag_lower == "title":
            self._title_depth += 1
        elif tag_lower in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "br"):
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in IGNORED_TAGS and self._ignore_depth > 0:
            self._ignore_depth -= 1
        elif tag_lower == "title" and self._title_depth > 0:
            self._title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._title_depth > 0:
            self.title_parts.append(data)
        elif self._ignore_depth == 0:
            text = data.strip()
            if text:
                self.text_parts.append(text + " ")

    def get_clean_text(self) -> tuple[str, str]:
        title = " ".join(self.title_parts).strip()
        title = re.sub(r"\s+", " ", title)

        raw_text = "".join(self.text_parts)
        # Normalize consecutive spaces and blank lines
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw_text.splitlines()]
        clean_text = "\n".join(line for line in lines if line)
        return title, clean_text


class HTTPPageReader(PageReader):
    """Standard safe HTTP page reader utilizing standard library with size and timeout guards."""

    reader_name: str = "http"

    def __init__(
        self,
        timeout: float = 10.0,
        max_bytes: int = 250_000,
        user_agent: str = "VennelaWebHunt/0.1 (+https://vennela.ai; bot)",
    ) -> None:
        super().__init__(timeout=timeout, max_bytes=max_bytes)
        self.user_agent = user_agent

    def validate_url(self, url: str) -> bool:
        """Reject non-http(s) schemes or malformed URLs to prevent SSRF."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            if not parsed.netloc:
                return False
            # Block localhost/private internal targets if requested
            host = parsed.netloc.split(":")[0].lower()
            if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
                return False
            return True
        except Exception:
            return False

    def fetch_page(self, url: str) -> PageContent:
        if not self.validate_url(url):
            return PageContent(
                url=url,
                title="",
                text_content="",
                status_code=400,
                success=False,
                error_message=f"Invalid or disallowed URL scheme: {sanitize(url)}",
            )

        req = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            method="GET",
        )

        try:
            with urlopen(req, timeout=self.timeout) as resp:
                status_code = getattr(resp, "status", 200)
                content_type = resp.headers.get("Content-Type", "")

                # Guard against binary payloads (images, zips, binaries)
                if not any(t in content_type.lower() for t in ("text", "html", "json", "xml", "")):
                    return PageContent(
                        url=url,
                        title="",
                        text_content="",
                        status_code=status_code,
                        success=False,
                        error_message=f"Skipping non-text Content-Type: {content_type}",
                    )

                # Stream read up to max_bytes
                raw_bytes = resp.read(self.max_bytes)
                charset = "utf-8"
                if "charset=" in content_type.lower():
                    charset = content_type.lower().split("charset=")[-1].split(";")[0].strip()

                try:
                    html_content = raw_bytes.decode(charset, errors="replace")
                except Exception:
                    html_content = raw_bytes.decode("utf-8", errors="replace")

                extractor = HTMLTextExtractor()
                extractor.feed(html_content)
                title, clean_text = extractor.get_clean_text()

                log_info(f"Retrieved page from {url} ({len(clean_text)} chars)")
                return PageContent(
                    url=url,
                    title=title or urlparse(url).netloc,
                    text_content=clean_text,
                    status_code=status_code,
                    content_length=len(clean_text),
                    success=True,
                )

        except HTTPError as exc:
            log_warning(f"HTTP error {exc.code} fetching {url}")
            return PageContent(
                url=url,
                title="",
                text_content="",
                status_code=exc.code,
                success=False,
                error_message=f"HTTP {exc.code}: {sanitize(str(exc.reason))}",
            )
        except (URLError, TimeoutError, OSError) as exc:
            log_warning(f"Connection/timeout error fetching {url}")
            return PageContent(
                url=url,
                title="",
                text_content="",
                status_code=0,
                success=False,
                error_message=f"Network error: {sanitize(str(exc))}",
            )
        except Exception as exc:
            log_error(f"Unexpected error reading page {url}: {exc}")
            return PageContent(
                url=url,
                title="",
                text_content="",
                status_code=500,
                success=False,
                error_message=f"Extraction failure: {sanitize(str(exc))}",
            )
