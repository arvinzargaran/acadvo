"""Course-catalog ingestion pipeline.

Turns a real university course source (an official API or a scraper) into
authoritative ``CatalogCourse`` rows, so the app's advising is grounded in real
data instead of hand-typed guesses.

Layout:
- ``prereq_parser`` — parse a natural-language prerequisite string into the app's
  ``prerequisites`` structure (AND across groups, OR within a group).
- ``sfu`` — adapter for Simon Fraser University's public, keyless course-outlines
  API (the first real source). Add one module per new school.
- ``waterloo`` — adapter for the University of Waterloo's official Open Data API
  (v3). Sanctioned and documented like SFU's, but key-gated.
- ``uoft`` — adapter for the University of Toronto's divisional calendars, via
  the public Drupal JSON:API each of them exposes. Keyless.
- ``ubc`` — the University of British Columbia's two calendars, same Drupal
  JSON:API shape. Keyless; publishes credits, states prerequisites in prose.
- ``store`` — generalized idempotent upsert into ``CatalogCourse`` with provenance.

Each adapter is a plain function returning ``list[CatalogRow]``; the CLI
(``app.scripts.ingest_catalog``) wires an adapter to :func:`store.upsert_catalog`.
"""
from app.ingest.store import CatalogRow, upsert_catalog

__all__ = ["CatalogRow", "upsert_catalog"]
