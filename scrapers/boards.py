"""Full-board fetchers for the AI job radar.

Unlike the original scrapers (which filtered by Austin/fintech at fetch time), these
return every posting with its description text, remote flags and comp where the ATS
exposes them, so scrapers/fit.py can make the call.
Fields starting with "_" are working data and are stripped before saving.
"""
from datetime import datetime

import requests

from scrapers.fit import strip_html

UA = {"User-Agent": "Mozilla/5.0 (job-search-agent; +https://github.com/eukota/job-search-agent)"}


def _now():
    return datetime.now().isoformat()


def fetch_greenhouse(company: str, token: str):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        out.append({
            "id": f"{company}-gh-{j.get('id')}",
            "title": j.get("title", ""),
            "company": company,
            "url": j.get("absolute_url"),
            "location": (j.get("location") or {}).get("name", "") or "Unspecified",
            "date_found": _now(),
            "date_posted": j.get("first_published") or j.get("updated_at") or _now(),
            "source": "Greenhouse",
            "_text": strip_html(j.get("content", "")),
        })
    return out


def fetch_ashby(company: str, token: str):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        if j.get("isListed") is False:
            continue
        comp = j.get("compensation") or {}
        salary, comp_max = "", 0
        for tier in comp.get("compensationTiers", []) or []:
            for c in tier.get("components", []) or []:
                if c.get("compensationType") == "Salary" and c.get("currencyCode", "USD") == "USD":
                    lo, hi = c.get("minValue") or 0, c.get("maxValue") or 0
                    if hi and hi > comp_max:
                        comp_max = int(hi)
                        salary = f"${int(lo) // 1000}k–${int(hi) // 1000}k"
        if not salary:
            salary = comp.get("scrapeableCompensationSalarySummary") or ""
        locs = [j.get("location", "")] + [
            (s.get("location") or "") for s in (j.get("secondaryLocations") or []) if isinstance(s, dict)
        ]
        out.append({
            "id": f"{company}-ashby-{j.get('id')}",
            "title": j.get("title", ""),
            "company": company,
            "url": j.get("jobUrl") or f"https://jobs.ashbyhq.com/{token}/{j.get('id')}",
            "location": " / ".join(l for l in locs if l) or "Unspecified",
            "date_found": _now(),
            "date_posted": j.get("publishedAt") or _now(),
            "source": "Ashby",
            "salary": salary,
            "_comp_max": comp_max,
            "_is_remote": j.get("isRemote"),
            "_workplace": j.get("workplaceType") or "",
            "_text": j.get("descriptionPlain") or strip_html(j.get("descriptionHtml", "")),
        })
    return out


def fetch_lever(company: str, token: str):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    out = []
    for j in r.json():
        cats = j.get("categories") or {}
        sr = j.get("salaryRange") or {}
        salary, comp_max = "", 0
        if sr.get("max") and sr.get("currency", "USD") == "USD":
            comp_max = int(sr["max"])
            salary = f"${int(sr.get('min', 0)) // 1000}k–${comp_max // 1000}k"
        out.append({
            "id": f"{company}-lever-{j.get('id')}",
            "title": j.get("text", ""),
            "company": company,
            "url": j.get("hostedUrl"),
            "location": cats.get("location", "") or "Unspecified",
            "date_found": _now(),
            "date_posted": datetime.fromtimestamp(j["createdAt"] / 1000).isoformat() if j.get("createdAt") else _now(),
            "source": "Lever",
            "salary": salary,
            "_comp_max": comp_max,
            "_workplace": j.get("workplaceType") or "",
            "_text": (j.get("descriptionPlain") or "") + " " + (j.get("additionalPlain") or ""),
        })
    return out


FETCHERS = {"greenhouse": fetch_greenhouse, "ashby": fetch_ashby, "lever": fetch_lever}
