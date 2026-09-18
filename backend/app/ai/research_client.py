"""Groq provider — the *research* seam, sitting alongside the chat/parsing paths.

Why a separate module when there is only one provider
-----------------------------------------------------
``app/ai/client.py`` answers questions from data we already hold: a parsed
document, a seeded catalog. Research answers a different kind of question —
"what does this university's calendar actually say?" — and the difference that
matters is not the model, it is **where the words came from**. Everything in
this module exists to keep those two apart, so that a research answer can never
be produced the way a chat answer is.

Retrieval is ours, not the model's
----------------------------------
This used to run on Gemini's ``url_context``/Search grounding, and the whole
provider was here for that one capability. It is gone: the app runs on the Groq
free tier only, and nothing here may cost money.

What replaced it is better, not worse. **We fetch the page ourselves** — an
ordinary HTTPS GET, no tokens, no metering — strip it to text, and hand that text
to the model as the only thing it is allowed to read. The citation is then a page
*we* retrieved and whose HTTP status *we* saw, rather than a page the provider
reports having read. There is no version of this where the model quietly answers
from memory and reports a URL it never opened, because the URL never reaches the
model as a fetchable thing at all.

The one hard property this module exists to provide
---------------------------------------------------
**Every answer arrives with the URLs whose text is in the prompt.** A research
result with no retrieved page is an ungrounded guess, and ``research`` refuses to
return one. That refusal is what keeps "this course counts toward your degree"
from ever being said on the strength of the model's training data.

Fetching a student-named URL server-side is SSRF-shaped, so it is guarded twice:
``app.research.schema.validate_requirements_url`` checks the URL before it is
queued, and ``_resolve_fetch_target`` below re-checks every redirect hop against
the resolved IP, which is the half a string check cannot do — then ``_fetch_sync``
connects to *that* address, so the name is never resolved a second time and there
is no window between the check and the socket for DNS to change its answer.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
import time
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import urlparse

import httpx

from app.ai.client import (
    acomplete,
    budget_max_tokens,
    completion_text,
    get_groq_client,
    is_ai_enabled,
    json_kwargs,
    run_blocking,
)
from app.config import settings

logger = logging.getLogger("acadvo.ai.research")

# Cap on how much of the model's budget the answer may take.
#
# Sized for *thinking* models, which is not the obvious number. This budget is
# shared between the model's reasoning tokens and the answer it finally emits: a
# real extraction against a university calendar spent ~7.6k tokens thinking
# before writing ~2k of JSON, so a small budget truncates the answer mid-object.
# The failure is nasty because it is silent — the JSON simply ends early, and the
# caller sees "research output was not a list of rules", which reads like a bad
# model rather than a budget.
#
# On a constrained account this is only the *desired* budget: the request goes
# out through ``budget_max_tokens``, which trims it to whatever
# ``GROQ_MAX_REQUEST_TOKENS`` leaves.
MAX_OUTPUT_TOKENS = 8192


class ResearchDisabledError(RuntimeError):
    """Raised when research cannot run because no API key is configured.

    Kept distinct from ``AIDisabledError`` even though both now key off the same
    Groq key: callers degrade differently for the two (no AI at all = no
    recommendations; no research = recommendations without requirement-rule
    labelling), and the messages a user sees are not interchangeable.
    """

    def __init__(self):
        super().__init__(
            "Program research is disabled — add a real Groq API key to enable "
            "requirement-rule extraction from university pages."
        )


class UngroundedResearchError(RuntimeError):
    """The model answered without anything having been retrieved.

    This is the failure mode that matters. An answer produced from the model's
    training memory looks identical to one read off the university's calendar,
    and there is no way to check it later because there is nothing to check it
    against. Treated as a hard failure rather than a low-confidence result.
    """

    def __init__(self, detail: str = "no page was retrieved"):
        super().__init__(f"Research result rejected: {detail}.")


@dataclass(frozen=True)
class Source:
    """One page that was actually retrieved."""

    uri: str
    title: str = ""
    domain: str = ""

    def as_dict(self) -> dict:
        return {"uri": self.uri, "title": self.title, "domain": self.domain}


@dataclass
class ResearchResult:
    text: str
    sources: list[Source] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    model: str = ""

    @property
    def source_urls(self) -> list[str]:
        return [s.uri for s in self.sources]

    @property
    def domains(self) -> set[str]:
        return {s.domain.lower() for s in self.sources if s.domain}


def is_research_enabled() -> bool:
    return is_ai_enabled()


def get_research_client():
    """Return the shared Groq client, refusing when research is unconfigured.

    A thin wrapper rather than a re-export: callers of this module handle
    ``ResearchDisabledError``, and letting ``AIDisabledError`` escape from here
    would take the research-specific degradation path away from them.
    """
    if not is_research_enabled():
        raise ResearchDisabledError()
    return get_groq_client()


def reset_research_client() -> None:
    """Drop the cached client (tests that swap the key).

    The client now lives in ``app.ai.client``; this clears that one so a test
    changing the key does not keep talking through a client built from the old
    one.
    """
    import app.ai.client as ai_client

    ai_client._client = None


# ── Retrieval ────────────────────────────────────────────────────────

# Below this, an extraction is treated as a failed fetch rather than a page.
#
# Soft 404s are the reason. University calendars answer 200 OK with a "Page Not
# Found" body constantly (moved programs, rolled-over calendar years), and a
# JS-rendered page returns nothing but its own navigation chrome. Both look like
# a successful retrieval to anything that only checks the status code, and both
# would let the model "read" a page that says nothing and fall back on memory.
MIN_PAGE_CHARS = 400

# Reserved for the system instruction, the JSON template in the prompt, and the
# page delimiters — everything in the request that is not page text.
PROMPT_OVERHEAD_TOKENS = 1_200

# Measured at a deliberately pessimistic 3 characters per token, matching
# ``budget_max_tokens``. Overestimating costs a little page text; underestimating
# puts the request back over the limit, where it is refused outright.
CHARS_PER_TOKEN = 3


def page_budget_chars() -> int:
    """How much retrieved text fits in one request, in characters.

    Not a politeness limit — a correctness one. Prompt and completion share the
    account's per-minute token allowance, and Groq enforces that allowance
    per-REQUEST: one call over the line is refused with a 413 every time, no
    matter how long you wait. A single academic-calendar page is comfortably past
    the free tier's 8,000 on its own, so it is trimmed to fit rather than sent
    and refused. A truncated page yields fewer buckets; an unsent one yields
    none, and the program stays uncovered forever.

    With ``GROQ_MAX_REQUEST_TOKENS`` at 0 (the default, and right for any paid
    tier) only the flat ``RESEARCH_MAX_PAGE_CHARS`` cap applies.
    """
    hard_cap = max(1, settings.RESEARCH_MAX_PAGE_CHARS)
    ceiling = settings.GROQ_MAX_REQUEST_TOKENS
    if ceiling <= 0:
        return hard_cap
    # Half the budget to the answer, which has to cover the model's reasoning as
    # well as the JSON it finally emits.
    answer = min(MAX_OUTPUT_TOKENS, ceiling // 2)
    room = ceiling - answer - PROMPT_OVERHEAD_TOKENS
    return max(MIN_PAGE_CHARS, min(hard_cap, room * CHARS_PER_TOKEN))


_SOFT_404_RE = re.compile(
    r"page not found|404 (?:-|—|:)? ?(?:not found|error)|we can'?t find the page"
    r"|the page you (?:requested|are looking for)",
    re.IGNORECASE,
)

_DROP_ELEMENTS_RE = re.compile(
    r"(?is)<(script|style|noscript|svg|head|nav|footer|form|template)\b.*?</\1\s*>"
)
_BLOCK_END_RE = re.compile(r"(?is)<br\s*/?>|</(?:p|div|li|tr|h[1-6]|table|section)\s*>")
_TAG_RE = re.compile(r"(?s)<[^>]+>")

MAX_FETCH_BYTES = 5_000_000

# httpx's timeout is *per operation* — connect, then each socket read — so it
# bounds no single fetch. A server that dribbles one byte every 19s resets the
# read timer forever, and the manual redirect walk below multiplies whatever it
# does bound by six hops. ``_fetch_sync`` runs on anyio's worker-thread pool,
# which is shared by every request the API serves, so a handful of slow-drip
# pages named by one student is a resource-exhaustion path against the whole
# app. FETCH_DEADLINE is the wall clock across the entire walk — resolution,
# every hop, and the body read — and is what actually gives the thread back.
FETCH_TIMEOUT = 20.0
FETCH_DEADLINE = 45.0

MAX_REDIRECTS = 5

# A university calendar lives on the web's two ports. Anything else named by a
# URL — or by a redirect off one — is asking us to speak HTTP at a service that
# is not a web server: 6379 (Redis), 11211 (memcached), 9200 (Elasticsearch),
# 5432 (Postgres). Several of those parse enough of a malformed request to act
# on it, so restricting the port is a real restriction on what a fetch can
# reach, not cosmetic tidying.
ALLOWED_FETCH_PORTS = frozenset({80, 443})
DEFAULT_PORTS = {"http": 80, "https": 443}

USER_AGENT = "acadvo-requirements-research (+https://github.com/acadvo)"


def html_to_text(html: str) -> str:
    """Reduce an HTML page to the prose a reader would see.

    Regex rather than a parser on purpose: the output is model input, not a DOM,
    so the cost of an imperfect strip is a slightly noisier prompt — and adding a
    parser dependency to do it buys nothing the model notices. Structural
    elements are turned into newlines first so requirement lists stay legible as
    lists instead of collapsing into one paragraph.
    """
    text = _DROP_ELEMENTS_RE.sub(" ", html or "")
    text = _BLOCK_END_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n[ \n]*\n *", "\n\n", text)
    return text.strip()


def _unwrapped_addresses(raw: str) -> list:
    """Return ``raw`` plus every IPv4 address tunnelled inside it.

    ``ipaddress`` grew the sense to see through IPv4-mapped IPv6 late:
    ``ip_address("::ffff:127.0.0.1").is_global`` is False on the 3.12 this app
    pins, but that is a property of the interpreter, not of our check, and a
    security control that quietly depends on the runtime's minor version is one
    that silently reopens the moment someone builds against a different one.
    6to4 (``2002::/16``) and Teredo (``2001::/32``) carry an IPv4 address in the
    same way — an attacker who cannot make a name resolve to 127.0.0.1 directly
    may well be able to make it resolve to ``2002:7f00:1::``, which routes to
    the same place. So each embedded address is dug out and validated in its own
    right rather than trusted to whatever ``is_global`` happens to say about the
    wrapper.
    """
    address = ipaddress.ip_address(raw)
    found = [address]
    if isinstance(address, ipaddress.IPv6Address):
        for inner in (address.ipv4_mapped, address.sixtofour):
            if inner is not None:
                found.append(inner)
        if address.teredo:
            # (server, client) — the client half is the interesting one, but a
            # tunnel to a private server is no better.
            found.extend(address.teredo)
    return found


def _reject_non_public(host: str, raw: str) -> None:
    """Raise unless ``raw`` — and everything tunnelled in it — is public."""
    for address in _unwrapped_addresses(raw):
        if not address.is_global or address.is_multicast:
            raise ValueError(f"{host} resolves to a non-public address")


def _resolve_fetch_target(url: str) -> tuple[str, str, int, str]:
    """Resolve ``url`` **once** and return ``(scheme, host, port, address)``.

    ``validate_requirements_url`` already rejects the string forms of this
    (localhost, IP literals, .internal). This is the half a string check cannot
    do: a public hostname whose DNS record points at 127.0.0.1 or 169.254.169.254
    looks perfectly ordinary until it is resolved. Called for the original URL
    *and* every redirect hop, because a redirect is a fresh target chosen by
    someone other than us.

    The single resolution is the point, and the reason this returns an address
    instead of returning nothing. Validating here and then handing the *URL* to
    httpx resolves the name a second time, and the two answers do not have to
    agree: an attacker serving a 0-TTL record that alternates a public IP and
    169.254.169.254 wins that race about half the time, and the loser is the
    cloud metadata endpoint. Every returned address is checked, and the caller
    connects to the one returned here rather than to the name.

    Raises ``ValueError`` with a message safe to log.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme
    if scheme not in DEFAULT_PORTS:
        raise ValueError("only http(s) pages can be read")
    if parsed.username or parsed.password:
        # Rechecked per hop rather than only at submission: a redirect can
        # introduce credentials the student never typed, and pinning below would
        # otherwise forward them to a bare IP.
        raise ValueError("the URL must not contain credentials")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("that URL has an invalid port") from exc
    port = port if port is not None else DEFAULT_PORTS[scheme]
    if port not in ALLOWED_FETCH_PORTS:
        raise ValueError(f"only ports {sorted(ALLOWED_FETCH_PORTS)} can be read")
    host = parsed.hostname or ""
    if not host:
        raise ValueError("no host in URL")

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"could not resolve {host}") from exc
    if not infos:
        raise ValueError(f"could not resolve {host}")
    for info in infos:
        _reject_non_public(host, info[4][0])
    # Every answer passed, so any of them is safe; take the first, which is the
    # one the resolver preferred.
    return scheme, host, port, infos[0][4][0]


def _check_fetch_target(url: str) -> None:
    """Validate a fetch target and discard the address.

    Kept as a name of its own because "is this URL allowed" is a question worth
    asking without connecting to the answer.
    """
    _resolve_fetch_target(url)


def _fetch_client(timeout: float) -> httpx.Client:
    """Build the client used for one redirect walk.

    A seam, not an abstraction: it exists so a test can substitute a transport
    and assert what was put on the wire — specifically that the request went to
    a validated IP while still carrying the original hostname — without any test
    in this repo ever opening a socket.
    """
    return httpx.Client(
        follow_redirects=False,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"},
    )


def _read_capped(response: httpx.Response, deadline: float) -> bytes:
    """Read at most ``MAX_FETCH_BYTES`` of ``response``, then stop pulling.

    ``response.content`` cannot do this. By the time it returns a value it has
    already buffered the whole body *and* run it through gzip, so slicing the
    result to a cap protects nothing: a few hundred KB of zeros that inflate to
    2GB take the worker out with a MemoryError before the slice is ever
    evaluated. Counting decompressed bytes as they arrive and abandoning the
    stream is the only version of this cap that is a cap.

    Truncating rather than erroring keeps the legitimate case working — an
    enormous calendar page is still readable down to the first 5MB, which is far
    more than ``page_budget_chars`` will send the model anyway.

    The deadline is re-checked per chunk for the other shape of the same attack:
    a body delivered one byte every 19 seconds never trips a per-read timeout,
    so size alone would never save the thread.
    """
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        if time.monotonic() > deadline:
            raise ValueError("timed out reading that page")
        chunks.append(chunk[: MAX_FETCH_BYTES - total])
        total += len(chunk)
        if total >= MAX_FETCH_BYTES:
            break
    return b"".join(chunks)


def _fetch_sync(url: str) -> str:
    """GET ``url``, following redirects by hand so each hop can be re-checked.

    ``follow_redirects=True`` would hand redirect choice to whoever controls the
    page — the exact move ``_resolve_fetch_target`` exists to prevent — so hops
    are walked explicitly here.

    Each hop connects to the address that was *just validated*, by rewriting the
    host of the URL to that literal, so no name is ever resolved twice and DNS
    rebinding has nothing to race against. Both halves of the original identity
    are preserved explicitly: the ``Host`` header, so virtual hosts still serve
    the right page, and the ``sni_hostname`` extension, which httpcore passes to
    ``start_tls`` as ``server_hostname``. That last one is load-bearing — it is
    what makes TLS present *and verify* the certificate for the university's
    hostname rather than for an IP literal. Certificate verification stays on;
    an attacker who wins nothing else must still produce a valid certificate for
    the name the student typed.
    """
    deadline = time.monotonic() + FETCH_DEADLINE
    with _fetch_client(FETCH_TIMEOUT) as client:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("timed out reading that page")
            scheme, host, port, address = _resolve_fetch_target(current)
            parsed = httpx.URL(current)
            with client.stream(
                "GET",
                parsed.copy_with(host=address),
                headers={"Host": parsed.netloc.decode("ascii")},
                extensions={"sni_hostname": host},
                # Per-hop timeouts never sum to more than the walk's budget.
                timeout=min(FETCH_TIMEOUT, remaining),
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("redirect without a destination")
                    # Joined against the *hostname* URL, not the pinned one: a
                    # relative Location must resolve against the origin the
                    # student named, or the next hop would carry an IP literal
                    # and lose the identity we are verifying against.
                    current = str(parsed.join(location))
                    continue
                if response.status_code != 200:
                    raise ValueError(f"HTTP {response.status_code}")
                body = _read_capped(response, deadline)
            return body.decode(response.encoding or "utf-8", errors="replace")
    raise ValueError("too many redirects")


async def fetch_page(url: str) -> tuple[str, str]:
    """Retrieve ``url`` and return ``(text, error)`` — exactly one is non-empty.

    Never raises. A page that cannot be read is a normal outcome the caller
    reports to the student ("we could not read that page"), not an exception that
    should take down a research job.
    """
    try:
        html = await run_blocking(_fetch_sync, url)
    except (httpx.HTTPError, ValueError, OSError) as exc:
        return "", str(exc) or exc.__class__.__name__

    text = html_to_text(html)
    if len(text) < MIN_PAGE_CHARS or _SOFT_404_RE.search(text[:2000]):
        # See MIN_PAGE_CHARS: a 200 with no readable content is a failed
        # retrieval, and calling it a success is how a model ends up "citing" a
        # page that never said anything.
        return "", "the page returned no readable requirement text"
    return text, ""


def _source_for(url: str) -> Source:
    host = urlparse(url).hostname or ""
    return Source(uri=url, title=host, domain=host)


def _collect_sources(response) -> tuple[list[Source], list[str]]:
    """Pull retrieved pages out of a Groq compound response's ``executed_tools``.

    Only used on the optional search path, where the provider — not us — chose
    what to open. Reads defensively at every level: ``executed_tools`` is absent
    on an ordinary completion, and a missing field must mean "nothing was
    retrieved" rather than an AttributeError a caller might mistake for a
    transport failure.
    """
    sources: list[Source] = []
    queries: list[str] = []
    seen: set[str] = set()

    for choice in getattr(response, "choices", None) or []:
        message = getattr(choice, "message", None)
        for tool in (getattr(message, "executed_tools", None) or []) if message else []:
            arguments = getattr(tool, "arguments", None)
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            arguments = arguments if isinstance(arguments, dict) else {}

            query = str(arguments.get("query") or "").strip()
            if query and query not in queries:
                queries.append(query)

            uris = [str(arguments.get("url") or "").strip()]
            results = getattr(tool, "search_results", None)
            if isinstance(results, dict):
                raw_results = results.get("results")
            else:
                raw_results = getattr(results, "results", None)
            for item in raw_results or []:
                url = (
                    item.get("url")
                    if isinstance(item, dict)
                    else getattr(item, "url", None)
                )
                uris.append(str(url or "").strip())

            for uri in uris:
                if not uri or uri in seen:
                    continue
                seen.add(uri)
                sources.append(_source_for(uri))
    return sources, queries


# ── Output parsing ───────────────────────────────────────────────────

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def strip_code_fence(text: str) -> str:
    """Remove a markdown fence the model was told not to emit.

    The other Groq paths do this through ``completion_text``; research output is
    fenced far more often (extraction answers get formatted for humans), so it
    keeps a real function with the ``json``-tagged and bare forms both covered.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    stripped = _FENCE_RE.sub("", stripped).strip()
    return stripped


def extract_json(text: str):
    """Parse the first JSON object/array in ``text``; return ``None`` on failure.

    Never raises. A research answer that is prose instead of JSON is a normal
    outcome to handle, not an exception to propagate — the caller records it as a
    failed extraction and the app keeps its existing behaviour.
    """
    candidate = strip_code_fence(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Extraction answers often wrap the JSON in a sentence of explanation.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


# ── The call ─────────────────────────────────────────────────────────


def _page_block(sources: list[Source], pages: dict[str, str]) -> str:
    """Render the retrieved pages as the only material the model may use.

    The per-request budget is split evenly across the pages rather than spent on
    the first one, so naming a second URL can never silently push the first out
    of the request.
    """
    per_page = max(MIN_PAGE_CHARS, page_budget_chars() // max(1, len(sources)))
    parts = [
        "Below is the text of the page(s) retrieved for this program. Use ONLY "
        "what these pages say. Do not use anything you remember about this "
        "university. If a requirement is not in this text, omit it.",
    ]
    for source in sources:
        text = pages[source.uri]
        if len(text) > per_page:
            # Say so rather than truncating silently: a model that thinks it has
            # the whole page will report an absent bucket as absent, which is a
            # confident wrong answer where "I only saw part of this" is a
            # correct one.
            text = text[:per_page] + "\n[… page truncated to fit the request budget …]"
        parts.append(
            f"\n===== BEGIN PAGE {source.uri} =====\n"
            f"{text}\n"
            f"===== END PAGE {source.uri} ====="
        )
    return "\n".join(parts)


async def _search_for_pages(prompt: str) -> tuple[list[Source], list[str]]:
    """Let the model find pages itself, via Groq compound's server-side search.

    Opt-in through ``RESEARCH_USE_SEARCH_GROUNDING`` and off by default, for a
    volume reason rather than a billing one: a search pulls several full pages
    into the request, which on the free tier's per-request token ceiling is
    refused outright with a 413. With it off, a student supplies their program's
    requirements URL and the (free, unmetered) direct fetch above reads it.
    """
    client = get_research_client()
    response = await acomplete(
        client,
        model=settings.RESEARCH_SEARCH_MODEL,
        temperature=0.0,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    "Find the official university pages that answer this, and "
                    "name them. Do not answer the question itself.\n\n" + prompt
                ),
            }
        ],
    )
    return _collect_sources(response)


async def research(
    prompt: str,
    *,
    urls: list[str] | None = None,
    system_instruction: str | None = None,
    temperature: float = 0.0,
    require_grounding: bool = True,
    use_search: bool | None = None,
) -> ResearchResult:
    """Retrieve the given pages and run one extraction over their text.

    Two retrieval modes, and the default is deliberate:

    * direct fetch (default) — the caller names the URLs and this module reads
      them over plain HTTPS. Free, unmetered, and the citation is a page we
      fetched and whose status we checked.
    * ``use_search`` — the model finds pages itself through Groq compound. Also
      free, but it drags several whole pages into one request, which the free
      tier's per-request token ceiling refuses; opt in via
      ``RESEARCH_USE_SEARCH_GROUNDING`` on an account with the headroom.

    Raises ``ResearchDisabledError`` when unconfigured and
    ``UngroundedResearchError`` when nothing was actually retrieved (see that
    class for why that is fatal rather than merely weak).
    """
    if not is_research_enabled():
        raise ResearchDisabledError()

    if use_search is None:
        use_search = settings.RESEARCH_USE_SEARCH_GROUNDING

    sources: list[Source] = []
    failed: list[str] = []
    queries: list[str] = []
    pages: dict[str, str] = {}

    for url in urls or []:
        text, error = await fetch_page(url)
        if text:
            pages[url] = text
            sources.append(_source_for(url))
        else:
            failed.append(url)
            logger.info("research: could not read %s (%s)", url, error)

    if not sources and use_search:
        found, queries = await _search_for_pages(prompt)
        for source in found:
            text, error = await fetch_page(source.uri)
            if text:
                pages[source.uri] = text
                sources.append(source)
            else:
                failed.append(source.uri)

    if require_grounding and not sources:
        # Name the URL that could not be read. "Research failed" with no reason
        # leaves a program permanently uncovered and nobody able to say why —
        # usually it is a wrong or moved URL, which is fixable in seconds.
        detail = (
            f"none of the given pages could be retrieved ({', '.join(failed)})"
            if failed
            else "no page was retrieved"
        )
        raise UngroundedResearchError(detail)

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    content = f"{_page_block(sources, pages)}\n\n{prompt}" if sources else prompt
    messages.append({"role": "user", "content": content})

    client = get_research_client()
    response = await acomplete(
        client,
        model=settings.RESEARCH_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=budget_max_tokens(content, MAX_OUTPUT_TOKENS),
        # The research model has no retrieval of its own, which is the point: the
        # grounding guarantee is that it saw the text we fetched and nothing
        # else. Do not swap in a compound system here — those browse on their own
        # initiative, and uncited material inside a cited answer is precisely the
        # failure this module exists to prevent.
        **json_kwargs(),
    )

    text = completion_text(response)
    if not text:
        raise UngroundedResearchError("the model returned no text")

    logger.info(
        "research: model=%s retrieved=%d failed=%d queries=%s",
        settings.RESEARCH_MODEL,
        len(sources),
        len(failed),
        queries,
    )
    return ResearchResult(
        text=text, sources=sources, queries=queries, model=settings.RESEARCH_MODEL
    )
