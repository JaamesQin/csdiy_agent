"""Offline safety contract for public catalog source probes.

This file intentionally owns a tiny fake downloader instead of importing a
production downloader: the repository currently records offering probes but
does not fetch public sources.  The fake transport makes the security policy
executable without DNS, sockets, or real network access.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import pytest


MAX_BYTES = 128
TIMEOUT_SECONDS = 1.0


class ProbeRejected(ValueError):
    pass


@dataclass(frozen=True)
class FakeHTTPResponse:
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    redirect: str | None = None
    delay_seconds: float = 0.0


class FakeHTTP:
    """A closed-world HTTP transport: an unknown URL is a test failure."""

    def __init__(self, responses: dict[str, FakeHTTPResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, *, timeout: float) -> FakeHTTPResponse:
        self.calls.append(url)
        if url not in self.responses:
            raise AssertionError(f"unexpected network/provider access: {url}")
        response = self.responses[url]
        if response.delay_seconds > timeout:
            raise TimeoutError(f"probe exceeded {timeout}s")
        if len(response.body) > MAX_BYTES:
            raise ProbeRejected("response exceeds byte cap")
        return response


def _address_is_public_global(host: str, resolved: tuple[str, ...]) -> bool:
    if not host or host.lower() == "localhost":
        return False
    try:
        addresses = tuple(ipaddress.ip_address(value) for value in resolved)
    except ValueError as exc:
        raise ProbeRejected("unresolved or invalid host") from exc
    return bool(addresses) and all(address.is_global and not address.is_multicast for address in addresses)


def _validate_url(url: str, resolved: dict[str, tuple[str, ...]]) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password:
        raise ProbeRejected("HTTPS without URL credentials is required")
    if not _address_is_public_global(parts.hostname or "", resolved.get(parts.hostname or "", ())):
        raise ProbeRejected("host must resolve only to public global addresses")


def _is_readable_pdf(body: bytes) -> bool:
    if not body.startswith(b"%PDF-"):
        return False
    lowered = body.lower()
    if b"<html" in lowered or b"type=\"password\"" in lowered or b"login" in lowered:
        return False
    return b"/page" in lowered or b"text" in lowered


def probe_public_source(
    url: str,
    transport: FakeHTTP,
    *,
    resolved: dict[str, tuple[str, ...]],
    license_text: str | None,
    max_redirects: int = 3,
) -> dict[str, object]:
    """Probe a fixture only, revalidating every redirect before fetching it."""

    seen: set[str] = set()
    chain: list[str] = []
    current = url
    for _ in range(max_redirects + 1):
        _validate_url(current, resolved)
        if current in seen:
            raise ProbeRejected("redirect loop")
        seen.add(current)
        chain.append(current)
        response = transport.get(current, timeout=TIMEOUT_SECONDS)
        if response.redirect:
            current = response.redirect
            continue
        if response.status_code in {401, 403}:
            return {"status": "auth_required", "final_url": current, "chain": chain}
        if response.status_code >= 400:
            return {"status": "failed", "final_url": current, "chain": chain}
        content_type = response.headers.get("content-type", "").lower()
        if content_type.startswith("application/pdf"):
            if not _is_readable_pdf(response.body):
                return {"status": "unreadable_or_masquerading_pdf", "final_url": current, "chain": chain}
        elif content_type.startswith("text/html"):
            if b"<html" not in response.body.lower():
                return {"status": "unreadable_html", "final_url": current, "chain": chain}
        else:
            return {"status": "unsupported_content_type", "final_url": current, "chain": chain}
        return {
            "status": "license_unknown" if not license_text else "verified_public",
            "final_url": current,
            "chain": chain,
        }
    raise ProbeRejected("redirect limit exceeded")


def _global_hosts(*names: str) -> dict[str, tuple[str, ...]]:
    return {name: ("93.184.216.34",) for name in names}


def test_url_credentials_are_rejected_before_fake_http() -> None:
    transport = FakeHTTP({})

    with pytest.raises(ProbeRejected, match="credentials"):
        probe_public_source(
            "https://user:secret@example.test/course",
            transport,
            resolved={"example.test": ("93.184.216.34",)},
            license_text="CC BY 4.0",
        )

    assert transport.calls == []


@pytest.mark.parametrize(
    "url,resolved",
    [
        ("https://localhost/course", {"localhost": ("127.0.0.1",)}),
        ("https://internal.test/course", {"internal.test": ("10.0.0.8",)}),
        ("https://linklocal.test/course", {"linklocal.test": ("169.254.1.4",)}),
        ("https://multicast.test/course", {"multicast.test": ("224.0.0.1",)}),
    ],
)
def test_private_or_non_global_addresses_are_rejected(url: str, resolved: dict[str, tuple[str, ...]]) -> None:
    with pytest.raises(ProbeRejected, match="public global"):
        probe_public_source(url, FakeHTTP({}), resolved=resolved, license_text="CC BY 4.0")


def test_redirect_target_is_revalidated_before_following() -> None:
    start = "https://public.test/course"
    private = "https://redirected.test/private.pdf"
    transport = FakeHTTP({start: FakeHTTPResponse(redirect=private)})

    with pytest.raises(ProbeRejected, match="public global"):
        probe_public_source(
            start,
            transport,
            resolved={"public.test": ("93.184.216.34",), "redirected.test": ("192.168.1.10",)},
            license_text="CC BY 4.0",
        )

    assert transport.calls == [start]


def test_final_redirect_chain_is_recorded_and_revalidated() -> None:
    start = "https://public.test/course"
    final = "https://archive.test/course.pdf"
    transport = FakeHTTP(
        {
            start: FakeHTTPResponse(redirect=final),
            final: FakeHTTPResponse(headers={"content-type": "application/pdf"}, body=b"%PDF-1.7 /Page text"),
        }
    )

    result = probe_public_source(
        start,
        transport,
        resolved=_global_hosts("public.test", "archive.test"),
        license_text="CC BY 4.0",
    )

    assert result["status"] == "verified_public"
    assert result["final_url"] == final
    assert result["chain"] == [start, final]


@pytest.mark.parametrize(
    "response,match",
    [
        (FakeHTTPResponse(body=b"x" * (MAX_BYTES + 1)), "byte cap"),
        (FakeHTTPResponse(delay_seconds=TIMEOUT_SECONDS + 0.01), "exceeded"),
    ],
)
def test_byte_caps_and_timeouts_are_enforced(response: FakeHTTPResponse, match: str) -> None:
    url = "https://public.test/source"
    with pytest.raises((ProbeRejected, TimeoutError), match=match):
        probe_public_source(url, FakeHTTP({url: response}), resolved=_global_hosts("public.test"), license_text="CC BY 4.0")


def test_login_html_masquerading_as_pdf_is_not_accepted() -> None:
    url = "https://public.test/slides.pdf"
    response = FakeHTTPResponse(
        headers={"content-type": "application/pdf"},
        body=b"%PDF-1.7 <html><title>Login</title><input type=\"password\">",
    )

    result = probe_public_source(url, FakeHTTP({url: response}), resolved=_global_hosts("public.test"), license_text="CC BY 4.0")

    assert result["status"] == "unreadable_or_masquerading_pdf"


@pytest.mark.parametrize(
    "content_type,body,license_text,expected",
    [
        ("application/pdf", b"not a pdf", "CC BY 4.0", "unreadable_or_masquerading_pdf"),
        ("application/pdf", b"%PDF-1.7 /Page text", "CC BY 4.0", "verified_public"),
        ("text/html", b"<html><body>Course notes</body></html>", None, "license_unknown"),
    ],
)
def test_content_magic_and_readability_gate_acceptance(
    content_type: str, body: bytes, license_text: str | None, expected: str
) -> None:
    url = "https://public.test/source"
    result = probe_public_source(
        url,
        FakeHTTP({url: FakeHTTPResponse(headers={"content-type": content_type}, body=body)}),
        resolved=_global_hosts("public.test"),
        license_text=license_text,
    )

    assert result["status"] == expected


def test_unknown_license_is_explicit_and_never_verified() -> None:
    url = "https://public.test/notes.html"
    response = FakeHTTPResponse(headers={"content-type": "text/html"}, body=b"<html>Course notes</html>")

    result = probe_public_source(url, FakeHTTP({url: response}), resolved=_global_hosts("public.test"), license_text=None)

    assert result["status"] == "license_unknown"
    assert result["status"] != "verified_public"
