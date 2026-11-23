"""Full-board fetchers for the AI job radar.

Unlike the original scrapers (which filtered by Austin/fintech at fetch time), these
return every posting with its description text, remote flags and comp where the ATS
exposes them, so scrapers/fit.py can make the call.
Fields starting with "_" are working data and are stripped before saving.
"""
from datetime import datetime

import requests

from scrapers.fit import ENGINEERING, EXCLUDE_TITLE, _hits, strip_html

UA = {"User-Agent": "Mozilla/5.0 (job-search-agent; +https://github.com/eukota/job-search-agent)"}


def _now():
    return datetime.now().isoformat()


def fetch_greenhouse(company: str, token: str, cfg: dict = None):
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


def fetch_ashby(company: str, token: str, cfg: dict = None):
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


def fetch_lever(company: str, token: str, cfg: dict = None):
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


BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# Searches used to narrow big boards (Workday / Eightfold hold thousands of postings).
SEARCH_TERMS = ["agent", "AI", "developer productivity", "platform engineer", "machine learning"]
MAX_DETAIL = 60  # cap on per-posting description fetches per company


def _get_json(url, params=None, retries=4, pause=0.4):
    """GET with a short pause between calls and backoff on 429 (Eightfold rate-limits quickly)."""
    import time
    for attempt in range(retries):
        time.sleep(pause)
        r = requests.get(url, params=params, headers=BROWSER_UA, timeout=60)
        if r.status_code == 429:
            time.sleep(min(float(r.headers.get("Retry-After", 5 * 2 ** attempt)), 60))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"rate limited (429) after {retries} tries: {url}")


def _worth_detail(title: str) -> bool:
    t = (title or "").lower()
    return any(k in t for k in ENGINEERING) and not _hits(t, EXCLUDE_TITLE)


def fetch_eightfold(company: str, token: str, cfg: dict = None):
    """Eightfold public API. token = careers host (e.g. explore.jobs.netflix.net); cfg["domain"] = tenant domain."""
    host, domain = token, (cfg or {}).get("domain") or token
    base = f"https://{host}/api/apply/v2/jobs"
    found = {}
    for term in SEARCH_TERMS:
        start = 0
        while start < 100:
            data = _get_json(base, {"domain": domain, "start": start, "num": 10, "query": term})
            positions = data.get("positions", [])
            for p in positions:
                found[p["id"]] = p
            start += 10
            if not positions or start >= data.get("count", 0):
                break
    out = []
    for pid, p in list(found.items()):
        title = p.get("name", "")
        text = p.get("job_description") or ""
        if not text and _worth_detail(title) and len(out) < MAX_DETAIL:
            try:
                text = _get_json(f"{base}/{pid}", {"domain": domain}).get("job_description", "")
            except Exception:
                pass
        out.append({
            "id": f"{company}-eightfold-{pid}",
            "title": title,
            "company": company,
            "url": p.get("canonicalPositionUrl") or f"https://{host}/careers/job/{pid}",
            "location": p.get("location") or "Unspecified",
            "date_found": _now(),
            "date_posted": datetime.fromtimestamp(int(p["t_create"])).isoformat() if p.get("t_create") else _now(),
            "source": "Eightfold",
            "_workplace": (p.get("work_location_option") or "").replace("onsite", "onsite"),
            "_text": strip_html(text),
        })
    return out


def fetch_workday(company: str, token: str, cfg: dict = None):
    """Workday CXS API. token = jobs API URL, e.g. https://x.wd12.myworkdayjobs.com/wday/cxs/x/site/jobs"""
    import re
    m = re.match(r"(https://[^/]+)/wday/cxs/([^/]+)/([^/]+)/jobs", token)
    if not m:
        raise ValueError(f"bad Workday api url: {token}")
    host, tenant, site = m.groups()
    headers = dict(BROWSER_UA, **{"Content-Type": "application/json"})
    found = {}
    for term in SEARCH_TERMS:
        offset = 0
        while offset < 100:
            r = requests.post(token, headers=headers, timeout=60,
                              json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": term})
            r.raise_for_status()
            data = r.json()
            postings = data.get("jobPostings", [])
            for p in postings:
                found[p.get("externalPath")] = p
            offset += 20
            if not postings or offset >= data.get("total", 0):
                break
    out, details = [], 0
    for path, p in found.items():
        if not path:
            continue
        title = p.get("title", "")
        info = {}
        if _worth_detail(title) and details < MAX_DETAIL:
            details += 1
            try:
                info = requests.get(f"{host}/wday/cxs/{tenant}/{site}{path}", headers=BROWSER_UA,
                                    timeout=60).json().get("jobPostingInfo", {})
            except Exception:
                pass
        remote_type = (info.get("remoteType") or "").lower()
        loc = info.get("location") or p.get("locationsText") or "Unspecified"
        extra = info.get("additionalLocations") or []
        if extra:
            loc = " / ".join([loc] + list(extra))
        is_remote = True if ("remote" in remote_type or "remote eligible" in title.lower()) else None
        out.append({
            "id": f"{company}-wd-{info.get('jobReqId') or path.rsplit('_', 1)[-1]}",
            "title": title,
            "company": company,
            "url": info.get("externalUrl") or f"{host}/en-US/{site}{path}",
            "location": loc,
            "date_found": _now(),
            "date_posted": info.get("startDate") or _now(),
            "source": "Workday",
            "_is_remote": is_remote,
            "_workplace": "remote" if "remote" in remote_type else ("hybrid" if "hybrid" in remote_type else ""),
            "_text": strip_html(info.get("jobDescription", "")),
        })
    return out


FETCHERS = {"greenhouse": fetch_greenhouse, "ashby": fetch_ashby, "lever": fetch_lever,
            "eightfold": fetch_eightfold, "workday": fetch_workday}
