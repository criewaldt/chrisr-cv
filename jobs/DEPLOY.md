# Deploying the `jobs` app

## 1. Heroku config vars

```bash
heroku config:set ANTHROPIC_API_KEY=sk-ant-...
heroku config:set JOBS_DIGEST_TO=criewaldt@gmail.com
heroku config:set JOBS_SITE_URL=https://chrisriewaldt.com
# optional overrides (defaults shown)
heroku config:set JOBS_TRIAGE_MODEL=claude-haiku-4-5
heroku config:set JOBS_TAILOR_MODEL=claude-opus-5
heroku config:set JOBS_TAILOR_EFFORT=medium
```

`GMAIL_USER` / `GMAIL_PW` must already be set for digests to send — they drive the
existing SMTP config in settings.py.

## 2. Migrations

Already applied to the production CockroachDB (additive only: 9 new tables plus 3
fields on `jobs_searchprofile`). Nothing in `resume`, `bonnaroo`, or `reimbursable`
was touched.

## 3. Heroku Scheduler — six entries

Scheduler is free but UTC-only, so each slot needs two entries; `jobs_run` guards on
local time and on whether the slot already ran today, so exactly one of each pair
does the work in any season.

| Command | UTC time | Fires at |
|---|---|---|
| `python manage.py jobs_run morning` | 12:30 | 8:30am ET (EDT) |
| `python manage.py jobs_run morning` | 13:30 | 8:30am ET (EST) |
| `python manage.py jobs_run midday`  | 16:00 | 12:00pm ET (EDT) |
| `python manage.py jobs_run midday`  | 17:00 | 12:00pm ET (EST) |
| `python manage.py jobs_run evening` | 21:00 | 5:00pm ET (EDT) |
| `python manage.py jobs_run evening` | 22:00 | 5:00pm ET (EST) |

The off-season twin exits in ~3 seconds having done nothing.

No worker dyno. Tailoring runs in a background thread inside the web dyno; the kit
page polls for the result.

## Commands

```bash
manage.py jobs_discover [--source KIND] [--config JSON] [--dry-run]
manage.py jobs_triage [--days N] [--limit N] [--dry-run]
manage.py jobs_run {morning|midday|evening} [--force] [--skip-email] [--limit N]
```

## Costs (measured, not estimated)

| Stage | Model | Per unit | Notes |
|---|---|---|---|
| Discovery + pre-filter | none | $0 | ~16.5k postings in 23s; ~95% rejected free |
| Triage | Haiku 4.5 | $0.0049 | no prompt cache — prefix is 2.1k, Haiku needs 4k |
| Tailoring | Opus 5, effort=medium | $0.11–0.13 | 1h prompt cache on the resume block |

Roughly **$7/mo triage + $0.12 per application you prep**. At 15 applications/day
that is about $55/mo; the only real dial is how many you prep.

## Scope note: no autofill

Form autofill was considered and deliberately dropped. Chris fills the online forms
himself. The kit's job is to make that fast, not to automate it:

- tailored resume as PDF and DOCX, one click each
- cover letter in an editable box (only when the posting expects one)
- screener answers pre-drafted for the questions this employer is likely to ask
- the "Be ready to defend" list, so nothing on the resume is a surprise later

This also removes the need for `django-cors-headers` and a browser extension, and
sidesteps the fact that browsers block JavaScript from attaching a resume file
anyway — the part of an application that actually takes the longest.

## Known gap

A prep in flight is lost if the dyno restarts. The row shows as stale with a retry
path rather than spinning forever. See the ephemeral-filesystem section above.

## Heroku's ephemeral filesystem

Nothing in this app writes to disk, so a dyno cycle loses nothing:

- Resume PDFs and DOCX are rendered into memory on each request from
  `TailoredApplication.resume_json`. There is no file store and no S3 bucket to
  configure — regenerating is cheap and always reflects the current data.
- All state lives in CockroachDB: postings, scores, tailored applications, cover
  letters, screener answers, digest history.
- `collectstatic` runs at build time and whitenoise serves from the slug.

**The one thing a dyno restart does cost** is a prep that is mid-flight. Tailoring
runs in a background thread inside the web dyno (no worker dyno by design), and
Heroku cycles dynos at least daily. A killed prep leaves its row `pending`; after
five minutes the kit page shows it as stale with a retry, rather than spinning
forever. Cost is one click, and only if a restart lands inside the ~60s window.

If that ever becomes annoying, add `worker: celery -A chrisr worker -B` to the
Procfile and swap `jobs/prep.py`'s thread for a task. Nothing in the AI layer or
the views changes.
