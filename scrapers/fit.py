"""Fit scoring for Darrell's search.

Keeps only remote-US, senior-and-up engineering roles in four lanes:
  1. AI platform / agent infrastructure
  2. Developer productivity / AI enablement / internal AI tooling
  3. Applied AI / forward-deployed
  4. Founding / staff roles at AI-native companies
and drops SRE / on-call / ops-centered roles and PhD research roles.

Everything here is plain keyword matching so it runs free in GitHub Actions.
The daily Claude run (data/picks.json) adds the judgment on top.
"""
import re
from html import unescape

LANES = {
    "Agent / AI Platform": [
        "agent", "agentic", "ai platform", "ai infrastructure", "ai infra", "llm platform",
        "llm infrastructure", "inference platform", "model platform", "mcp", "orchestration",
        "ai gateway", "context", "retrieval", "rag", "copilot", "ai foundations", "core ai",
    ],
    "Dev Productivity / AI Enablement": [
        "developer productivity", "developer experience", "devex", "dev ex", "engineering productivity",
        "ai enablement", "ai productivity", "ai acceleration", "internal tools", "internal ai",
        "developer tools", "dev tools", "ai developer tools", "build systems", "platform engineering",
        "ai tooling", "coding agent",
    ],
    "Applied AI / Forward-Deployed": [
        "forward deployed", "forward-deployed", "deployed engineer", "applied ai", "ai engineer",
        "llm engineer", "solutions engineer, ai", "ai solutions",
    ],
    "Founding / AI-native": [
        "founding engineer", "founding", "member of technical staff", "member of the technical staff",
    ],
}

# Generic platform words: count a little, but not enough alone outside AI-native companies.
WEAK_LANE = ["platform", "automation", "infrastructure", "workflow", "ai", "ml", "llm"]

EXCLUDE_TITLE = [
    "site reliability", "sre", "devops", "on-call", "oncall", "production engineer",
    "support engineer", "reliability engineer", "incident", "operations engineer",
    "research scientist", "research engineer, pretraining", "phd", "intern", "new grad",
    "manager", "director", "recruiter", "sales", "account executive", "designer",
    "data analyst", "it engineer", "help desk", "security operations", "network engineer",
    "database reliability", "solutions architect",
    "frontend", "front-end", "front end", "mobile", "ios", "android",
]

ENGINEERING = ["engineer", "developer", "architect", "member of technical staff",
               "member of the technical staff", "mts", "programmer"]

SENIOR_OK = {
    "principal": 30, "distinguished": 25, "staff": 28, "founding": 26, "lead": 18,
    "senior": 15, "sr.": 15, "sr ": 15, "member of technical staff": 18,
    "member of the technical staff": 18, " iv": 18, " v": 22, "l6": 25, "l7": 30, "e6": 25,
}
TOO_JUNIOR = ["junior", "jr.", "associate", "entry", "intern", "new grad", " i ", " ii", "level 1", "level 2"]

OPS_TEXT = [
    "on-call", "on call rotation", "oncall", "pager", "pagerduty", "24/7", "incident response",
    "first-responder", "first responder", "post-mortem", "postmortem", "slo",
]

NON_US = [
    "london", "uk", "united kingdom", "ireland", "dublin", "berlin", "germany", "paris", "france",
    "amsterdam", "netherlands", "spain", "poland", "singapore", "india", "bangalore", "bengaluru",
    "australia", "sydney", "tokyo", "japan", "brazil", "toronto", "emea", "apac",
    "latam", "europe", "israel", "tel aviv", "mexico", "argentina", "portugal", "switzerland",
    "canada", "vancouver", "montreal",
]

SALARY_RE = re.compile(
    r"\$\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK])\s*(?:-|–|—|to)\s*\$?\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK])"
)


def strip_html(html: str) -> str:
    if not html:
        return ""
    text = unescape(unescape(html))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def _num(s: str) -> int:
    s = s.replace(",", "").replace(" ", "").lower()
    if s.endswith("k"):
        return int(float(s[:-1]) * 1000)
    return int(float(s))


def extract_comp(text: str):
    """Returns (display string, max base in dollars) for the first plausible US salary range."""
    for m in SALARY_RE.finditer(text or ""):
        lo, hi = _num(m.group(1)), _num(m.group(2))
        if 80_000 <= lo <= 1_500_000 and lo <= hi <= 1_500_000:
            return f"${lo // 1000}k–${hi // 1000}k", hi
    return "", 0


def is_remote_us(location: str, text: str = "", workplace: str = "", is_remote_flag=None) -> bool:
    loc = (location or "").lower()
    wp = (workplace or "").lower()
    remote_signal = (
        is_remote_flag is True or "remote" in loc or wp == "remote"
        or "anywhere in the us" in loc or "united states (remote)" in loc
    )
    if not remote_signal:
        return False
    if "hybrid" in loc or wp == "hybrid":
        return False
    if any(k in loc for k in NON_US):
        # "Remote - US or Canada" style strings stay in
        return bool(re.search(r"(?<![a-z])(us|usa|u\.s\.|united states|north america|americas)(?![a-z])", loc))
    return True


def _hits(haystack: str, words) -> list:
    return [w for w in words if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", haystack)]


def score_job(job: dict, company: dict = None) -> dict:
    """Returns the job with fit fields added, or None if it's out of scope."""
    company = company or {}
    title = (job.get("title") or "").lower()
    padded = f" {title} "
    text = (job.get("_text") or "").lower()

    if not any(k in title for k in ENGINEERING):
        return None
    if _hits(title, EXCLUDE_TITLE):
        return None
    if any(k in padded for k in TOO_JUNIOR):
        return None
    if not is_remote_us(job.get("location", ""), text, job.get("_workplace", ""), job.get("_is_remote")):
        return None

    level_pts = max([pts for k, pts in SENIOR_OK.items() if k in padded] or [0])
    if level_pts == 0:
        return None  # untitled-level roles are usually mid; the Claude run can still add them as picks

    lanes, lane_pts = [], 0
    for lane, words in LANES.items():
        t_hits = _hits(title, words)
        d_hits = _hits(text[:6000], words) if text else []
        if t_hits:
            lanes.append(lane)
            lane_pts += 30
        elif len(d_hits) >= 2:
            lanes.append(lane)
            lane_pts += 12
    ai_native = company.get("ai_native", False)
    weak = _hits(title, WEAK_LANE)
    if not lanes:
        if ai_native and weak:
            lanes.append("Founding / AI-native")
            lane_pts += 15
        elif ai_native and "software engineer" in title:
            lanes.append("Founding / AI-native")
            lane_pts += 8
        else:
            return None
    lane_pts = min(lane_pts, 45) + min(len(weak) * 3, 6)

    comp = job.get("salary") or ""
    comp_max = job.get("_comp_max") or 0
    if not comp:
        comp, comp_max = extract_comp(job.get("_text") or "")
    pay_pts = 0
    if comp_max >= 300_000:
        pay_pts = 15
    elif comp_max >= 240_000:
        pay_pts = 10
    elif comp_max >= 200_000:
        pay_pts = 5
    elif comp_max and comp_max < 170_000:
        pay_pts = -10
    tier_pts = {"A": 8, "B": 3}.get(company.get("tier", ""), 0)

    ops_hits = _hits(text, OPS_TEXT)
    ops_pts = 0  # on-call text is flagged for visibility but is not a dealbreaker

    scored = dict(job)
    scored["lanes"] = lanes
    scored["fit_score"] = max(0, min(100, level_pts + lane_pts + pay_pts + tier_pts + ops_pts))
    scored["ops_flag"] = bool(ops_hits)
    scored["ops_terms"] = ops_hits[:3]
    if comp:
        scored["salary"] = comp
    scored["comp_max"] = comp_max
    return scored
