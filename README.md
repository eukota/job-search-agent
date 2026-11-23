# AI Job Radar

A daily board of **remote-US, Staff+ roles** in agent infrastructure, AI developer
productivity / AI enablement, forward-deployed AI, and founding roles at AI-native
companies, plus a **radar of companies that pay well** for that work.

## How it fills itself

| Piece | Runs | Writes |
|---|---|---|
| `main.py` (GitHub Action, daily + on push) | Pulls every posting from each company in `data/companies.json` (Greenhouse / Ashby / Lever), scores it with `scrapers/fit.py`, prunes roles gone 2 runs in a row | `data/jobs.json`, `web/*.json` |
| Daily Claude scan (scheduled task) | Searches the wider web (HN, aggregators, lab career pages), checks postings, finds new companies | `data/picks.json`, new entries in `data/companies.json` |

A push that changes `data/picks.json` or `data/companies.json` re-runs the Action, so the site picks up Claude's changes within a few minutes.

## Files

- `data/companies.json`: the company radar. One entry per company: `name`, `ats_type` (`greenhouse` / `ashby` / `lever` / `none`), `board_token`, `careers_url`, `tier` (A = top pay + remote in lane, B = strong on one), `ai_native`, `remote_policy`, `pay_signal`, `why`, `added`, `added_by`. Companies with `ats_type: none` are shown on the radar but not scraped.
- `data/picks.json`: `{updated, picks: [{rank, company, title, url, salary, location, why, ops_flag, ops_note, found_date}], company_notes: [{name, note}]}`.
- `data/digest_history.json`: 36 daily runs of the Claude desktop task (Oct 18-Nov 22, parsed from `docs/ai-job-search-all-results.md`). Reference only; `main.py` does not read it.
- `scrapers/fit.py`: the keyword fit rules (lanes, exclusions, remote-US check, pay parsing, on-call flag). Tune it here.

## Run locally

```bash
pip install -r requirements.txt
python main.py
cd web && python -m http.server
```
