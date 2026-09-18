"""What ``research_client`` may reach when a student names the URL.

The research fetch is the one place this app makes an outbound request to an
address someone else chose, and it is not blind: the bytes that come back are
put in the model's prompt, persisted into rule ``notes``/``source_quote`` and
shown to the student, and a failure message is surfaced through
``job.last_error``. So anything reachable is also readable, and every test here
is about narrowing what "reachable" means.

Nothing in this file opens a socket. Both boundaries the fetch crosses are
substituted — ``socket.getaddrinfo`` for the name lookup and
``research_client._fetch_client`` for the transport — which is also what lets
the tests assert the thing that matters most: not just that a bad target is
refused, but that the *good* one is connected to by the exact address that was
validated.
"""
import ipaddress
import socket
import time
import zlib

import httpx
import pytest

import app.ai.research_client as rc
from app.research.schema import RuleRejected, validate_requirements_url

PUBLIC_IP = "142.250.190.78"
OTHER_PUBLIC_IP = "23.185.0.4"


def _addrinfo(ip: str) -> tuple:
    family = (
        socket.AF_INET6 if ipaddress.ip_address(ip).version == 6 else socket.AF_INET
    )
    return (family, socket.SOCK_STREAM, 6, "", (ip, 443))


def fake_resolver(*answers, calls=None):
    """A ``getaddrinfo`` that hands out ``answers`` one call at a time.

    The last answer repeats, so a single-address resolver is just
    ``fake_resolver(["1.2.3.4"])``. ``calls`` records each lookup, because "how
    many times was this name resolved" is itself the assertion in the rebinding
    test below.
    """
    sequence = list(answers)

    def _resolve(host, port=None, *args, **kwargs):
        if calls is not None:
            calls.append(host)
        ips = sequence[0] if len(sequence) == 1 else sequence.pop(0)
        return [_addrinfo(ip) for ip in ips]

    return _resolve


def html_page(body: str = "requirement text " * 60) -> str:
    return f"<html><body><p>{body}</p></body></html>"


def use_transport(monkeypatch, handler):
    """Route the fetch through a MockTransport and return the seen requests."""
    seen: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def _client(timeout):
        return httpx.Client(
            transport=httpx.MockTransport(_handler),
            follow_redirects=False,
            timeout=timeout,
            headers={"User-Agent": rc.USER_AGENT},
        )

    monkeypatch.setattr(rc, "_fetch_client", _client)
    return seen


# ── F1: the address is pinned, so there is no second resolution ──────


def test_a_public_university_page_still_fetches(monkeypatch):
    """The whole point of the guard is that it does not break the normal case."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([PUBLIC_IP]))
    use_transport(monkeypatch, lambda r: httpx.Response(200, text=html_page()))

    assert "requirement text" in rc._fetch_sync(
        "https://artsci.calendar.utoronto.ca/section/Computer-Science"
    )


def test_the_socket_goes_to_the_validated_address_not_the_name(monkeypatch):
    """The pin, stated directly: the request carries the IP that was checked,
    while the ``Host`` header and the TLS ``server_hostname`` still carry the
    university's name — so virtual hosting works and the certificate is still
    verified against the name the student typed, not against an IP literal."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([PUBLIC_IP]))
    seen = use_transport(monkeypatch, lambda r: httpx.Response(200, text=html_page()))

    rc._fetch_sync("https://calendar.yorku.ca/programs/cs")

    request = seen[0]
    assert request.url.host == PUBLIC_IP
    assert request.url.path == "/programs/cs"
    assert request.headers["Host"] == "calendar.yorku.ca"
    assert request.extensions["sni_hostname"] == "calendar.yorku.ca"


def test_dns_rebinding_cannot_move_the_target_after_the_check(monkeypatch):
    """The TOCTOU this pin closes.

    A 0-TTL record that alternates a public address and 169.254.169.254 beats a
    check-then-connect fetch about half the time, and the prize is the cloud
    metadata endpoint — credentials, in a response body this app puts in a
    prompt and writes into a rule note. The second answer is never asked for:
    the name is resolved exactly once and the connection is made to that
    address.
    """
    calls: list[str] = []
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        fake_resolver([PUBLIC_IP], ["169.254.169.254"], calls=calls),
    )
    seen = use_transport(monkeypatch, lambda r: httpx.Response(200, text=html_page()))

    rc._fetch_sync("https://rebind.example.edu/requirements")

    assert calls == ["rebind.example.edu"]
    assert seen[0].url.host == PUBLIC_IP


def test_a_name_resolving_to_any_private_address_is_refused(monkeypatch):
    """Multi-answer records are the cheap way past a first-answer-only check:
    one public A record to pass inspection, one private one to be connected to.
    Every answer has to be public, not just the one we would have used."""
    monkeypatch.setattr(
        socket, "getaddrinfo", fake_resolver([PUBLIC_IP, "169.254.169.254"])
    )
    use_transport(monkeypatch, lambda r: httpx.Response(200, text=html_page()))

    with pytest.raises(ValueError, match="non-public"):
        rc._fetch_sync("https://split-horizon.example.edu/x")


def test_every_redirect_hop_is_resolved_and_validated(monkeypatch):
    """A redirect is a target chosen by whoever controls the first page, so a
    public front door that 302s to an internal host is the obvious bypass."""
    monkeypatch.setattr(
        socket, "getaddrinfo", fake_resolver([PUBLIC_IP], ["127.0.0.1"])
    )
    use_transport(
        monkeypatch,
        lambda r: httpx.Response(302, headers={"location": "https://inside.example/x"}),
    )

    with pytest.raises(ValueError, match="non-public"):
        rc._fetch_sync("https://front.example.edu/start")


def test_a_relative_redirect_is_joined_against_the_hostname_not_the_pin(
    monkeypatch,
):
    """The pinned URL must not leak into the next hop. Joining ``/moved``
    against ``https://142.250.190.78/`` would send hop two to an IP literal,
    losing the hostname the certificate is checked against."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([PUBLIC_IP]))
    responses = [
        httpx.Response(302, headers={"location": "/moved"}),
        httpx.Response(200, text=html_page()),
    ]
    seen = use_transport(monkeypatch, lambda r: responses.pop(0))

    rc._fetch_sync("https://calendar.yorku.ca/old")

    assert [r.url.path for r in seen] == ["/old", "/moved"]
    assert {r.headers["Host"] for r in seen} == {"calendar.yorku.ca"}


def test_credentials_introduced_by_a_redirect_are_refused(monkeypatch):
    """``validate_requirements_url`` strips these at submission, but a redirect
    never passes through it — and with the address pinned, forwarding them would
    mean sending a student-supplied Authorization header to a bare IP."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([PUBLIC_IP]))
    use_transport(
        monkeypatch,
        lambda r: httpx.Response(
            302, headers={"location": "https://user:pw@calendar.yorku.ca/x"}
        ),
    )

    with pytest.raises(ValueError, match="credentials"):
        rc._fetch_sync("https://calendar.yorku.ca/start")


# ── F2: the body is capped as it arrives, not after ──────────────────


def test_an_oversized_body_stops_being_pulled_at_the_cap(monkeypatch):
    """``response.content`` buffers the whole body before any slice runs, so
    the old ``content[:MAX_FETCH_BYTES]`` was a cap on the variable, not on
    memory. Counted here by what the server was actually asked for: the stream
    is abandoned within one chunk of the limit instead of being drained."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([PUBLIC_IP]))
    chunk = b"a" * 100_000
    served = {"chunks": 0}

    def _body():
        # Would run to 100MB if anything actually consumed it.
        for _ in range(1000):
            served["chunks"] += 1
            yield chunk

    use_transport(monkeypatch, lambda r: httpx.Response(200, content=_body()))

    body = rc._fetch_sync("https://calendar.yorku.ca/huge")

    assert len(body) == rc.MAX_FETCH_BYTES
    assert served["chunks"] == rc.MAX_FETCH_BYTES // len(chunk)


def test_a_gzip_bomb_is_abandoned_mid_decompression(monkeypatch):
    """The nastier version: 200MB of zeros ships as a couple hundred KB, so no
    cap on the *transfer* sees it coming. The bytes counted have to be the
    decompressed ones, which is why the cap lives in the iteration rather than
    in a Content-Length check."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([PUBLIC_IP]))
    served = {"megabytes": 0}

    def _bomb():
        compressor = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
        for _ in range(200):
            served["megabytes"] += 1
            block = compressor.compress(b"\0" * 1_000_000)
            if block:
                yield block
        yield compressor.flush()

    use_transport(
        monkeypatch,
        lambda r: httpx.Response(
            200, headers={"content-encoding": "gzip"}, content=_bomb()
        ),
    )

    body = rc._fetch_sync("https://calendar.yorku.ca/bomb")

    assert len(body) <= rc.MAX_FETCH_BYTES
    # A drained bomb would have pushed all 200MB through the decompressor.
    assert served["megabytes"] < 200


# ── F3: one wall clock across the whole walk ─────────────────────────


def test_the_redirect_walk_has_a_wall_clock_deadline(monkeypatch):
    """``FETCH_TIMEOUT`` is per operation, so six hops of a slow-but-not-idle
    server each get their own budget and the thread is held for minutes. These
    threads come from the pool anyio shares with every API request, so a handful
    of student-named URLs is a denial-of-service against the whole app."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([PUBLIC_IP]))
    monkeypatch.setattr(rc, "FETCH_DEADLINE", 0.25)

    def _slow_redirect(request):
        time.sleep(0.1)
        return httpx.Response(302, headers={"location": "/next"})

    seen = use_transport(monkeypatch, _slow_redirect)

    with pytest.raises(ValueError, match="timed out"):
        rc._fetch_sync("https://calendar.yorku.ca/slow")

    # Stopped on the clock, not on MAX_REDIRECTS — which would have allowed six.
    assert len(seen) < rc.MAX_REDIRECTS + 1


def test_a_slow_drip_body_hits_the_deadline(monkeypatch):
    """The shape no read timeout catches: every chunk arrives well inside
    ``FETCH_TIMEOUT``, resetting it, so the transfer never times out and never
    ends. Checked per chunk rather than only after the read for that reason."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([PUBLIC_IP]))
    monkeypatch.setattr(rc, "FETCH_DEADLINE", 0.25)

    def _drip():
        for _ in range(100):
            time.sleep(0.05)
            yield b"x"

    use_transport(monkeypatch, lambda r: httpx.Response(200, content=_drip()))

    with pytest.raises(ValueError, match="timed out"):
        rc._fetch_sync("https://calendar.yorku.ca/drip")


# ── F4: only the web's two ports ─────────────────────────────────────


@pytest.mark.parametrize("port", [6379, 11211, 9200, 5432, 8000])
def test_a_non_web_port_is_refused_at_submission(port):
    """The docstring claimed ports were checked and nothing read ``parsed.port``.
    A public hostname pointed at 6379 is a Redis instance we would speak HTTP at
    and then quote back to the student."""
    with pytest.raises(RuleRejected):
        validate_requirements_url(f"https://calendar.yorku.ca:{port}/programs")


@pytest.mark.parametrize(
    "url",
    ["https://calendar.yorku.ca/x", "https://calendar.yorku.ca:443/x", "http://a.b/x"],
)
def test_the_standard_web_ports_are_still_accepted(url):
    assert validate_requirements_url(url) == url


def test_a_non_web_port_is_refused_on_a_redirect_hop(monkeypatch):
    """Submission-time validation never sees hop two, so the port check has to
    exist on the fetch side as well."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([PUBLIC_IP]))
    use_transport(
        monkeypatch,
        lambda r: httpx.Response(
            302, headers={"location": "https://calendar.yorku.ca:6379/x"}
        ),
    )

    with pytest.raises(ValueError, match="ports"):
        rc._fetch_sync("https://calendar.yorku.ca/start")


# ── F5: tunnelled IPv4, independent of the interpreter ───────────────


@pytest.mark.parametrize(
    "address,wrapped",
    [
        ("::ffff:127.0.0.1", "loopback, IPv4-mapped"),
        ("::ffff:169.254.169.254", "cloud metadata, IPv4-mapped"),
        ("::ffff:10.0.0.1", "RFC1918, IPv4-mapped"),
        ("2002:7f00:1::", "loopback, 6to4"),
        ("2002:a9fe:a9fe::", "cloud metadata, 6to4"),
    ],
)
def test_ipv4_tunnelled_inside_ipv6_is_refused(monkeypatch, address, wrapped):
    """``ip_address("::ffff:127.0.0.1").is_global`` returning False is a fact
    about CPython 3.13-and-earlier-backports, not about this check — it was True
    on older interpreters, and a guard whose correctness depends on the runtime's
    minor version is one that reopens silently on an upgrade. The embedded
    address is unwrapped and judged on its own."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([address]))

    with pytest.raises(ValueError, match="non-public"):
        rc._check_fetch_target("https://tunnelled.example.edu/x")


def test_public_ipv6_is_still_reachable(monkeypatch):
    """The unwrapping must not turn into a blanket ban on IPv6."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver(["2606:4700:4700::1111"]))
    seen = use_transport(monkeypatch, lambda r: httpx.Response(200, text=html_page()))

    rc._fetch_sync("https://calendar.yorku.ca/v6")

    assert seen[0].url.host == "2606:4700:4700::1111"
    assert seen[0].headers["Host"] == "calendar.yorku.ca"


def test_an_ipv4_mapped_public_address_is_not_collateral_damage(monkeypatch):
    """Unwrapping judges the inner address, so a mapped *public* one passes."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver([f"::ffff:{PUBLIC_IP}"]))
    use_transport(monkeypatch, lambda r: httpx.Response(200, text=html_page()))

    assert rc._fetch_sync("https://calendar.yorku.ca/x")


# ── The failure paths callers depend on ──────────────────────────────


def test_a_refused_target_is_reported_not_raised(monkeypatch):
    """``fetch_page`` still converts all of the above into an error string: a
    research job reports "we could not read that page" rather than dying, and
    the SSRF guards must not change that."""
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolver(["127.0.0.1"]))

    async def _run():
        return await rc.fetch_page("https://rebind.example.edu/x")

    import anyio

    text, error = anyio.run(_run)
    assert text == ""
    assert "non-public" in error


def test_an_unresolvable_host_is_refused(monkeypatch):
    def _boom(*args, **kwargs):
        raise socket.gaierror("nope")

    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    with pytest.raises(ValueError, match="could not resolve"):
        rc._check_fetch_target("https://nowhere.example.edu/x")
