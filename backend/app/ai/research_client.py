"""Gemini provider — the *research* seam, sitting alongside Groq.

Why a second provider
---------------------
``app/ai/client.py`` (Groq) answers questions from data we already hold: a parsed
document, a seeded catalog. It has no retrieval, and the 16 tools in
``app/ai/tools.py`` are all internal DB operations. That is the right shape for
the high-volume paths and it stays exactly as it is.

What it cannot do is read a university's website. Requirement rules — "6.00
credits in AP/HUMA, 6.00 in AP/SOSC, 6.00 in SC/NATS, minus these exclusions" —
are published as prose on calendar pages, differ per school, and are never
enumerated as a course list. Getting them means retrieval with citations, which
is why Gemini's Google Search grounding is wired in here.

The one hard property this module exists to provide
---------------------------------------------------
**Every answer arrives with the URLs the model actually retrieved.** Not URLs it
typed into its JSON — those are as inventable as anything else a model writes —
but the grounding chunks the API reports for the response. A research result with
no grounding chunks is an ungrounded guess, and ``research_json`` refuses to
return one. That refusal is what keeps "this course counts toward your degree"
from ever being said on the strength of the model's memory.

Disabled by default: with no ``GEMINI_API_KEY`` the whole path is off, and the
app keeps the honest gaps it already reports.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.ai.client import run_blocking
from app.config import settings

logger = logging.getLogger("acadvo.ai.research")

PLACEHOLDER_KEYS = {"placeholder", "your-gemini-key-here", "changeme", ""}

# Cap on how much grounded text we accept back.
#
# Sized for *thinking* models, which is not the obvious number. This budget is
# shared between the model's reasoning tokens and the answer it finally emits: a
# real extraction against a university calendar spent ~7.6k tokens thinking
# before writing ~2k of JSON, so the original 8192 truncated the answer
# mid-object. The failure is nasty because it is silent — `finish_reason` is
# MAX_TOKENS, the JSON simply ends early, and the caller sees "research output
# was not a list of rules", which reads like a bad model rather than a budget.
MAX_OUTPUT_TOKENS = 24576


class ResearchDisabledError(RuntimeError):
    """Raised when no Gemini API key is configured.

    Deliberately distinct from ``AIDisabledError``: Groq being configured says
    nothing about whether research is available, and callers degrade differently
    for the two (no Groq = no recommendations at all; no Gemini = recommendations
    without requirement-rule labelling).
    """

    def __init__(self):
        super().__init__(
            "Program research is disabled — set GEMINI_API_KEY to enable "
            "requirement-rule extraction from university pages."
        )


class UngroundedResearchError(RuntimeError):
    """The model answered without retrieving anything.

    This is the failure mode that matters. An answer produced from the model's
    training memory looks identical to one read off the university's calendar,
    and there is no way to check it later because there is nothing to check it
    against. Treated as a hard failure rather than a low-confidence result.
    """

    def __init__(self, detail: str = "no search grounding was returned"):
        super().__init__(f"Research result rejected: {detail}.")


@dataclass(frozen=True)
class Source:
    """One page the model actually retrieved."""

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


_client = None


def is_research_enabled() -> bool:
    return settings.GEMINI_API_KEY not in PLACEHOLDER_KEYS


def get_research_client():
    """Return the shared native Gemini client, creating it on first use.

    The native SDK, not an OpenAI-compatible shim: the compat layers do not
    expose Search grounding, and grounding is the entire reason this provider is
    here. Imported lazily so ``google-genai`` is not a hard import for anyone
    running without a key.
    """
    global _client
    if not is_research_enabled():
        raise ResearchDisabledError()
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def reset_research_client() -> None:
    """Drop the cached client (tests that swap the key)."""
    global _client
    _client = None


def _collect_sources(response) -> tuple[list[Source], list[str]]:
    """Pull the retrieved pages out of a response's grounding metadata.

    Reads defensively: grounding metadata is optional on every level of the
    response, and a missing field must mean "nothing was retrieved" rather than
    an AttributeError that a caller might mistake for a transport failure.
    """
    sources: list[Source] = []
    queries: list[str] = []
    seen: set[str] = set()

    for candidate in getattr(response, "candidates", None) or []:
        meta = getattr(candidate, "grounding_metadata", None)
        if meta is None:
            continue
        for q in getattr(meta, "web_search_queries", None) or []:
            if q and q not in queries:
                queries.append(q)
        for chunk in getattr(meta, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            if web is None:
                continue
            uri = (getattr(web, "uri", None) or "").strip()
            if not uri or uri in seen:
                continue
            seen.add(uri)
            sources.append(
                Source(
                    uri=uri,
                    title=(getattr(web, "title", None) or "").strip(),
                    # The API reports `domain` for some chunks and only a
                    # domain-shaped `title` for others; fall back so the
                    # official-domain check downstream has something to read.
                    domain=(getattr(web, "domain", None) or getattr(web, "title", None) or "").strip(),
                )
            )
    return sources, queries


def _response_text(response) -> str:
    text = getattr(response, "text", None)
    if text:
        return text.strip()
    # `.text` is None when the candidate has non-text parts (a grounded answer
    # can carry them); reassemble from the parts rather than reporting nothing.
    out: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in (getattr(content, "parts", None) or []) if content else []:
            if getattr(part, "text", None):
                out.append(part.text)
    return "".join(out).strip()


_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def strip_code_fence(text: str) -> str:
    """Remove a markdown fence the model was told not to emit.

    The Groq paths already do this inline; research output is fenced far more
    often (grounded answers are formatted for humans), so it gets a real
    function with the ``json``-tagged and bare forms both covered.
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
    # Grounded answers often wrap the JSON in a sentence of explanation.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


def _collect_retrieved_urls(response) -> tuple[list[Source], list[str]]:
    """Sources from ``url_context`` — the pages the API reports it actually fetched.

    Stronger evidence than search grounding, not weaker. ``groundingChunks`` say
    "these informed the answer"; ``url_context_metadata`` reports a per-URL
    ``URL_RETRIEVAL_STATUS``, so a page that failed to load is distinguishable
    from one that was read. That distinction matters here: in testing, a model
    handed an unreachable URL answered *anyway*, describing the page from its
    address alone. Only ``SUCCESS`` counts as a source; everything else is
    recorded as a failure so the caller can say which URL could not be read.
    """
    sources: list[Source] = []
    failed: list[str] = []
    seen: set[str] = set()

    for candidate in getattr(response, "candidates", None) or []:
        meta = getattr(candidate, "url_context_metadata", None)
        for item in (getattr(meta, "url_metadata", None) or []) if meta else []:
            uri = (getattr(item, "retrieved_url", None) or "").strip()
            if not uri or uri in seen:
                continue
            seen.add(uri)
            status = getattr(item, "url_retrieval_status", None)
            name = getattr(status, "name", str(status or ""))
            if name.endswith("SUCCESS"):
                host = uri.split("/")[2] if "://" in uri else ""
                sources.append(Source(uri=uri, title=host, domain=host))
            else:
                failed.append(uri)
    return sources, failed


async def research(
    prompt: str,
    *,
    urls: list[str] | None = None,
    system_instruction: str | None = None,
    temperature: float = 0.0,
    require_grounding: bool = True,
    use_search: bool | None = None,
) -> ResearchResult:
    """Run one grounded Gemini call and return the text plus the pages it read.

    Two retrieval modes, and the default is deliberate:

    * ``url_context`` (default) — the model reads URLs the caller names. Free on
      the Gemini free tier, and the citation is a page we asked for and the API
      confirmed it fetched.
    * ``google_search`` — the model finds pages itself. Better, and **billed**:
      on the free tier every grounded call returns 429, so this is opt-in via
      ``RESEARCH_USE_SEARCH_GROUNDING`` for deployments with billing enabled.

    Raises ``ResearchDisabledError`` when unconfigured and
    ``UngroundedResearchError`` when nothing was actually retrieved (see that
    class for why that is fatal rather than merely weak).
    """
    from google.genai import types

    if use_search is None:
        use_search = settings.RESEARCH_USE_SEARCH_GROUNDING

    tools = [types.Tool(url_context=types.UrlContext())]
    if use_search:
        tools.insert(0, types.Tool(google_search=types.GoogleSearch()))

    client = get_research_client()
    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        system_instruction=system_instruction,
        # Enabling tools rules out response_schema/JSON mode on this API, which
        # is why the output contract is enforced by parsing rather than the SDK.
        tools=tools,
    )

    if urls:
        # Named explicitly in the prompt as well as passed as a tool: the model
        # only fetches URLs it sees in the text it is given.
        listed = "\n".join(f"- {u}" for u in urls)
        prompt = f"{prompt}\n\nRead ONLY these pages and use ONLY what they say:\n{listed}"

    # The native SDK is synchronous and a grounded call takes many seconds;
    # calling it straight from an async handler would pin the event loop for the
    # whole round trip. Same reasoning as `app.ai.client.run_blocking`.
    response = await run_blocking(
        client.models.generate_content,
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=config,
    )

    # Both retrieval paths contribute citations; a run may use either or both.
    sources, failed = _collect_retrieved_urls(response)
    search_sources, queries = _collect_sources(response)
    known = {s.uri for s in sources}
    sources.extend(s for s in search_sources if s.uri not in known)

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

    text = _response_text(response)
    if not text:
        raise UngroundedResearchError("the model returned no text")

    logger.info(
        "research: model=%s retrieved=%d failed=%d queries=%s",
        settings.GEMINI_MODEL,
        len(sources),
        len(failed),
        queries,
    )
    return ResearchResult(
        text=text, sources=sources, queries=queries, model=settings.GEMINI_MODEL
    )
