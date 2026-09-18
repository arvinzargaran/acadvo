# Access request — Toronto Metropolitan University

**Status: DRAFT. Not sent.** Fill in the bracketed fields and send it yourself.

**Who to contact:** the Office of the Registrar (curriculum/calendar) is the
right first door; `computerscience@torontomu.ca` for a CS-only pilot. If TMU
publishes a webmaster or open-data contact, prefer that.

**Why this is needed:** TMU's `robots.txt` disallows the calendar for every year
from 2005-2006 through 2025-2026. The current 2026-2027 path is not in the list,
but that reads as an oversight rather than a change of policy, so Acadvo is not
scraping it. See `backend/app/ingest/SOURCES.md`.

---

**Subject:** Permission to read TMU course-calendar data for a student advising tool

Hello,

I'm [NAME], [a TMU student / an independent developer] building Acadvo, a
[free, non-commercial] academic-advising tool that helps undergraduates track
degree progress and plan future semesters against their program requirements.

To do that accurately for TMU students, the app needs each course's code, title,
credit weight and prerequisites — the same facts published in the undergraduate
calendar at https://www.torontomu.ca/calendar/.

I'm writing rather than scraping. TMU's robots.txt disallows the calendar paths,
and I'd rather have your permission or your preferred source than work around
that. Specifically, I'd like to ask:

1. Is there an existing API, data export, or feed for course and prerequisite
   data that I could use?
2. If not, would TMU permit periodic, low-volume, attributed retrieval of the
   public calendar course pages — for example one crawl per term, rate-limited,
   with a clearly identified user agent and contact address?
3. If neither is possible, is there someone else I should be asking?

Happy to work within any constraints you'd want to set — crawl rate, timing,
caching, attribution, or a written agreement. I'm equally happy to describe the
project in more detail or show you what it does.

Thank you for your time,

[NAME]
[EMAIL] · [PROJECT URL]
