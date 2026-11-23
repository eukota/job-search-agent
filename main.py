"""AI Job Radar pipeline.

1. Reads target companies from data/companies.json (the "company radar").
2. Pulls every posting from each company's Greenhouse / Ashby / Lever board.
3. Keeps only roles that pass scrapers/fit.py (remote US, Senior+, AI-platform /
   dev-productivity / forward-deployed / AI-native lanes, no SRE/on-call titles).
4. Tracks first/last seen dates and prunes roles missing from two runs in a row.
5. Writes data/jobs.json and mirrors jobs, picks and companies into web/.

data/picks.json and data/companies.json are also edited by the daily Claude run;
this script only reads them (it adds scrape stats to the web copy of companies).
"""
import json
import os
from datetime import datetime

from scrapers.boards import FETCHERS
from scrapers.fit import score_job

DATA, WEB = "data", "web"


def load(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def public(job):
    return {k: v for k, v in job.items() if not k.startswith("_")}


def main():
    now = datetime.now().isoformat()
    print(f"[{now}] AI Job Radar: starting")
    companies = load(f"{DATA}/companies.json", [])
    names = {c["name"] for c in companies}
    seen = {j["url"]: j for j in load(f"{DATA}/jobs.json", [])}

    scraped_ok, active_urls, stats = set(), {}, {}
    for c in companies:
        name, ats, token = c["name"], c.get("ats_type"), c.get("board_token")
        fetch = FETCHERS.get(ats)
        if not fetch or not token:
            stats[name] = {"status": "not scrapable (watch manually)"}
            continue
        try:
            postings = fetch(name, token, c)
        except Exception as e:  # keep going; one bad board shouldn't sink the run
            print(f"  ! {name}: {e}")
            stats[name] = {"status": f"error: {type(e).__name__}"}
            continue
        scraped_ok.add(name)
        matches = [m for m in (score_job(p, c) for p in postings) if m]
        active_urls[name] = {m["url"] for m in matches}
        stats[name] = {"status": "ok", "open_roles": len(postings), "matches": len(matches)}
        print(f"  {name}: {len(postings)} postings -> {len(matches)} matches")
        for m in matches:
            m = public(m)
            prev = seen.get(m["url"], {})
            m["first_seen_date"] = prev.get("first_seen_date", now)
            m["last_seen_date"] = now
            m["miss_count"] = 0
            seen[m["url"]] = m

    kept = []
    for url, job in seen.items():
        comp = job.get("company")
        if comp not in names:
            continue  # company was removed from the radar
        if comp in scraped_ok and url not in active_urls.get(comp, set()):
            job["miss_count"] = job.get("miss_count", 0) + 1
            if job["miss_count"] >= 2:
                continue
        kept.append(job)
    kept.sort(key=lambda j: (-j.get("fit_score", 0), j.get("company", "")))

    dump(f"{DATA}/jobs.json", kept)
    dump(f"{WEB}/jobs.json", kept)
    dump(f"{WEB}/picks.json", load(f"{DATA}/picks.json", {"updated": None, "picks": []}))
    web_companies = [dict(c, scrape=stats.get(c["name"], {})) for c in companies]
    dump(f"{WEB}/companies.json", {"updated": now, "companies": web_companies})
    print(f"[{datetime.now().isoformat()}] Done: {len(kept)} matching roles across {len(scraped_ok)} boards")


if __name__ == "__main__":
    main()
