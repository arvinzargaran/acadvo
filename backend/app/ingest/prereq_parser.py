"""Parse a natural-language prerequisite string into the app's structured form.

The app models ``prerequisites`` as a list of requirement GROUPS: it is satisfied
when, for EVERY group, at least ONE code in that group is satisfied — i.e. AND
across groups, OR within a group (conjunctive normal form). See
``app.models.catalog.CatalogCourse`` and ``app.services.eligibility``.

Universities publish prerequisites as prose, e.g. SFU's::

    "(MACM 101 and (CMPT 125, CMPT 129 or CMPT 135)) or (ENSC 251 and ENSC 252),
     all with a minimum grade of C-."

We tokenize the codes and the boolean structure (``and`` / ``or`` / commas /
parentheses; ``or`` binds looser than ``and``), build an expression tree, and
convert it to CNF so the result plugs straight into the eligibility engine.

This is BEST-EFFORT: prose that carries no recognizable course codes (e.g.
"permission of the department", "60 units") yields ``[]`` (no machine-checkable
prerequisite). We never fabricate a code that is not literally present.
"""
from __future__ import annotations

import re

# A course code: 2-5 letter subject, optional space, 3-4 digit number, optional
# single trailing letter, and an optional campus digit after that letter
# (e.g. "CMPT 105W", "MACM 101", "EECS 2101", UofT's "CSC148H1").
#
# The campus digit is not cosmetic here. Without it the trailing ``\b`` could not
# close after "148H" (a digit follows), so the pattern matched **nothing at all**
# in UofT prose: every UofT prerequisite string parsed to ``[]`` and every UofT
# course looked like it had no prerequisites the app could check.
# ``camp`` is UBC's campus marker, which UBC writes into its own prerequisite
# prose: "Prerequisite: CPSC_V 213 and either CPSC_V 221 or DSCI_V 221." Without
# it the subject matched "CPSC" and then hit an underscore where a digit was
# required, so EVERY UBC prerequisite naming a course parsed to nothing — the
# first UBC ingest recorded prerequisites for 15% of courses where the real
# figure is far higher.
_CODE_RE = re.compile(
    r"\b(?P<subj>[A-Z]{2,5})(?P<camp>_[A-Z])?\s*(?P<num>[0-9]{3,4}[A-Z]?[0-9]?)\b"
)

# UofT Scarborough's shape: CSCA08H3 -> subject "CSC", number "A08H3". Tried
# first, for the same reason and with the same narrowness as in
# ``services/document_parser``: without it a UTSC prerequisite string parses to
# nothing at all.
_UTSC_CODE_RE = re.compile(r"\b(?P<subj>[A-Z]{3})\s*(?P<num>[A-Z][0-9]{2}[A-Z][0-9])\b")


def _canon(subject: str, number: str, campus: str = "") -> str:
    return f"{subject.upper()}{campus.upper()} {number.upper()}"


def _tokenize(text: str) -> list:
    """Turn the prerequisite prose into a flat token stream of course codes and
    the operators ``(``, ``)``, ``and``, ``or``. Commas are treated as ``or``
    (SFU lists alternatives comma-separated). Everything else is dropped."""
    tokens: list = []
    i = 0
    upper = text.upper()
    n = len(upper)
    while i < n:
        ch = upper[i]
        if ch in "()":
            tokens.append(ch)
            i += 1
            continue
        if ch == ",":
            tokens.append("or")
            i += 1
            continue
        # UTSC's shape is tried first: its subject is three letters followed by a
        # level letter, which the general pattern would otherwise mis-split.
        m = _UTSC_CODE_RE.match(upper, i)
        if m:
            tokens.append(_canon(m.group("subj"), m.group("num")))
            i = m.end()
            continue
        m = _CODE_RE.match(upper, i)
        if m:
            tokens.append(_canon(m.group("subj"), m.group("num"), m.group("camp") or ""))
            i = m.end()
            continue
        # word operators
        if upper[i:i + 3] == "AND" and (i + 3 >= n or not upper[i + 3].isalpha()):
            tokens.append("and")
            i += 3
            continue
        if upper[i:i + 2] == "OR" and (i + 2 >= n or not upper[i + 2].isalpha()):
            tokens.append("or")
            i += 2
            continue
        i += 1
    return tokens


# ── Recursive-descent parser → expression tree ───────────────────────
# Grammar (or binds looser than and):
#   or_expr  := and_expr ("or" and_expr)*
#   and_expr := atom ("and" atom)*
#   atom     := CODE | "(" or_expr ")"
# Tree nodes: ("code", str) | ("and", [nodes]) | ("or", [nodes])

class _Parser:
    def __init__(self, tokens: list):
        self.toks = tokens
        self.pos = 0

    def _peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def _next(self):
        tok = self._peek()
        self.pos += 1
        return tok

    def parse(self):
        if not self.toks:
            return None
        node = self._or_expr()
        return node

    def _or_expr(self):
        parts = [self._and_expr()]
        while self._peek() == "or":
            self._next()
            parts.append(self._and_expr())
        parts = [p for p in parts if p is not None]
        if not parts:
            return None
        return parts[0] if len(parts) == 1 else ("or", parts)

    def _and_expr(self):
        parts = [self._atom()]
        while self._peek() == "and":
            self._next()
            parts.append(self._atom())
        parts = [p for p in parts if p is not None]
        if not parts:
            return None
        return parts[0] if len(parts) == 1 else ("and", parts)

    def _atom(self):
        tok = self._peek()
        if tok == "(":
            self._next()
            node = self._or_expr()
            if self._peek() == ")":
                self._next()
            return node
        if tok in ("and", "or", ")", None):
            return None
        # a course code
        self._next()
        return ("code", tok)


# ── CNF conversion ───────────────────────────────────────────────────
# Represent CNF as a list of clauses; each clause is a frozenset of codes (OR).
# AND across clauses.

def _to_cnf(node) -> list[frozenset]:
    if node is None:
        return []
    kind = node[0]
    if kind == "code":
        return [frozenset({node[1]})]
    if kind == "and":
        clauses: list[frozenset] = []
        for child in node[1]:
            clauses.extend(_to_cnf(child))
        return clauses
    # or: distribute — product of one code from each child's clauses
    child_cnfs = [_to_cnf(c) for c in node[1]]
    child_cnfs = [c for c in child_cnfs if c]
    if not child_cnfs:
        return []
    result = child_cnfs[0]
    for nxt in child_cnfs[1:]:
        result = [a | b for a in result for b in nxt]
    return result


def _dedupe(clauses: list[frozenset]) -> list[frozenset]:
    """Drop duplicate clauses and clauses that are supersets of a smaller clause
    (a broader OR is implied by a stricter one) to keep the structure tight."""
    uniq: list[frozenset] = []
    seen: set[frozenset] = set()
    for c in sorted(clauses, key=len):
        if c in seen:
            continue
        if any(existing <= c for existing in uniq):
            continue
        uniq.append(c)
        seen.add(c)
    return uniq


def parse_prerequisites(text: str | None) -> list[list[str]]:
    """Parse a prerequisite string into ``list[list[str]]`` (AND of OR-groups).

    Returns ``[]`` when the text carries no recognizable course codes. Codes that
    are present are never dropped and never invented."""
    if not text:
        return []
    tokens = _tokenize(text)
    # No codes at all -> nothing machine-checkable.
    if not any(t not in ("and", "or", "(", ")") for t in tokens):
        return []
    tree = _Parser(tokens).parse()
    clauses = _dedupe(_to_cnf(tree))
    return [sorted(clause) for clause in clauses]
