"""Safe HTTP Page Reader with robust HTML text extraction and strict SSRF defenses."""

from __future__ import annotations

from html.parser import HTMLParser
import ipaddress
import re
import socket
from typing import Set
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .base import PageReader
from ..models import PageContent
from ..telemetry import log_error, log_info, log_warning, sanitize

PROHIBITED_METADATA_HOSTS: Set[str] = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "localhost",
}


class SSRFValidationError(ValueError):
    """Raised when an outbound URL fails SSRF safety validation."""


class SafeRedirectHandler(HTTPRedirectHandler):
    """Revalidates destination URLs on HTTP redirects to prevent SSRF bypass via 3xx."""

    def __init__(self, validator_func, max_redirects: int = 3) -> None:
        super().__init__()
        self.validator_func = validator_func
        self.max_redirects = max_redirects
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > self.max_redirects:
            raise HTTPError(req.full_url, code, "Maximum redirect limit exceeded", headers, fp)

        if not self.validator_func(newurl):
            raise HTTPError(
                req.full_url,
                code,
                f"SSRF blocked: Redirect destination '{sanitize(newurl)}' is prohibited",
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)

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

    @staticmethod
    def is_ip_prohibited(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        """Check if an IP address belongs to loopback, private, link-local, multicast, or reserved ranges."""
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return True
        if str(ip) == "169.254.169.254":
            return True
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            if HTTPPageReader.is_ip_prohibited(ip.ipv4_mapped):
                return True
        return False

    def validate_url(self, url: str) -> bool:
        """Comprehensive SSRF validation checking scheme, credentials, hostnames, and resolved IPs."""
        if not url or not isinstance(url, str):
            return False

        try:
            parsed = urlparse(url.strip())
            # 1. Scheme restriction: only http and https
            if parsed.scheme.lower() not in ("http", "https"):
                return False

            # 2. Reject URLs with embedded credentials (e.g. user:pass@host)
            if parsed.username or parsed.password:
                return False

            if not parsed.hostname:
                return False

            hostname = parsed.hostname.lower().strip()

            # 3. Check against known prohibited metadata hostnames
            if hostname in PROHIBITED_METADATA_HOSTS:
                return False

            # 4. If hostname is a literal IP address, validate directly
            try:
                literal_ip = ipaddress.ip_address(hostname)
                if self.is_ip_prohibited(literal_ip):
                    return False
                return True
            except ValueError:
                # Not a literal IP, proceed to DNS resolution
                pass

            # 5. DNS Resolution: Resolve A and AAAA records
            port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
            try:
                addr_infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
            except (socket.gaierror, socket.herror, OSError):
                # DNS failure: reject fail-securely
                return False

            if not addr_infos:
                return False

            for family, _, _, _, sockaddr in addr_infos:
                ip_str = sockaddr[0]
                try:
                    resolved_ip = ipaddress.ip_address(ip_str)
                    if self.is_ip_prohibited(resolved_ip):
                        return False
                except ValueError:
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
                error_message=f"SSRF Protection: Invalid or disallowed URL target: {sanitize(url)}",
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
            opener = build_opener(SafeRedirectHandler(self.validate_url, max_redirects=3))
            with opener.open(req, timeout=self.timeout) as resp:
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
