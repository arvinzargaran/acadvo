# Access request — University of Toronto

**Status: DRAFT. Not sent.** Fill in the bracketed fields and send it yourself.

**Who to contact:** the EASI / Enterprise Applications and Solutions Integration
group owns the Timetable Builder backend (`api.easi.utoronto.ca`); Arts & Science
Registrar for calendar data. Try EASI first — they own the actual API.

**Why this is needed:** the TTB backend is technically open (verified 2026-08-24:
`GET https://api.easi.utoronto.ca/ttb/reference-data` returns 200 anonymously)
but it is an undocumented private backend for a first-party UI, with no published
terms granting third-party use and no stability guarantee. `data.utoronto.ca`
allows crawling but publishes institutional statistics only — no course data.
See `backend/app/ingest/SOURCES.md`.

---

**Subject:** Requesting sanctioned access to UofT course/timetable data for a student advising tool

Hello,

I'm [NAME], [a UofT student / an independent developer] building Acadvo, a
[free, non-commercial] academic-advising tool that helps undergraduates track
their degree progress and plan future semesters against their program
requirements.

For that to work for UofT students the app needs course-level facts — code,
title, credit weight, and prerequisites — per session.

I know the Timetable Builder is backed by an API at `api.easi.utoronto.ca/ttb`,
and that it currently answers anonymous requests. I have deliberately not built
on it, because as far as I can tell it's an internal backend for your own
interface rather than a published integration point, and I don't want to depend
on — or add load to — something I haven't been invited to use. So I'd rather ask:

1. Is there a sanctioned way to access course and prerequisite data — an API
   programme, a data export, a licensing arrangement, or a documented feed?
2. If the TTB API can be used by third parties, are there documented terms, a
   registration process, or rate limits I should be following?
3. If this isn't the right team, could you point me to who owns this data?

I'm happy to accept any constraints — registration, rate limits, attribution,
caching rules, a written agreement — and to explain the project in more detail.

Thank you for your time,

[NAME]
[EMAIL] · [PROJECT URL]
