Run Darrell's daily AI job scan. Update his AI Job Radar repo (github.com/eukota/job-search-agent, branch main) and email him a short digest.

## Who he is (for judging fit)
- About 20 years in software engineering. Expert in C++ (8 years, a 3M-line codebase) and AWS (8 years). Former agility lead, product owner and engineering manager.
- Senior (L9) software engineer at Axon. Hired into the SRE org to build platform software that replaces operational toil. He is a builder, NOT an SRE, and dislikes SRE/ops work.
- Part of Axon's AI vanguard. He builds agent infrastructure (a central context/memory system for agent swarms), internal AI tooling and training around Claude primitives (skills, hooks, commands, MCP), autonomous Claude Code runs, and multi-agent orchestration designs.
- Career theme: replacing manual human work with systems.

## Targets
- REMOTE ONLY (US-remote is fine). Senior, Staff or Principal level, or founding engineer at a startup.
- Lanes: (1) AI platform / agent infrastructure, (2) developer productivity / AI enablement / internal AI tooling, (3) applied AI / forward-deployed, (4) founding or staff roles at AI-native agent or dev-tool startups.
- Exclude: roles centered on SRE, incident response, production ops or DevOps support (on-call is only flagged, never a reason to exclude or downrank; required travel is not a dealbreaker either); PhD research roles; hybrid or onsite roles; junior or mid-level roles.
- Pay matters. Favor companies with published Staff base ranges of about $220k or more, or top-of-market levels.fyi bands.

## Steps
1. Clone the repo. Read data/companies.json (the company radar), data/picks.json (current picks) and data/jobs.json (roles the scraper already matched).
2. ROLES: search the web for roles posted in the last ~3 days. Use extended WebSearch where it helps, and cover HN "Who is hiring", Greenhouse/Ashby/Lever boards, Wellfound, LinkedIn and AI-lab career pages. Open each posting and check that it is open, its remote policy, its level, its pay and any on-call duties. Skip anything already in data/picks.json (same company + title). Never invent postings.
3. COMPANIES: find 1–3 companies NOT already in companies.json that pay well AND hire remote-US engineers in his lanes. Use posted salary ranges, levels.fyi and funding news. For each one, find its job board token from a real job URL (job-boards.greenhouse.io/<token>, jobs.ashbyhq.com/<token>, jobs.lever.co/<token>). If it uses another ATS, set ats_type "none". Append it with the same fields as the existing entries, with added = today and added_by = "claude-daily". Do not remove companies. If a company has clearly gone onsite-only or its pay has dropped below the bar, update its tier and notes.
4. PICKS: rewrite data/picks.json with the best 5–10 open roles, ranked by fit. Combine today's new finds, still-open earlier picks, and strong matches from data/jobs.json. Each pick needs: rank, company, title, url, salary, location, why (one line), ops_flag, ops_note, found_date. Drop picks whose posting has closed. Set "updated" to today. Put one line per new company in company_notes.
5. Commit to main with the message "daily scan: <Mon DD>" and push. The push re-runs the GitHub Action, which rebuilds dev.eukota.com/job-search-agent.
6. Email eukota@gmail.com with the Gmail send_message tool. Subject: "AI job digest — <Mon DD>". Body:
   - the new picks (Company — Title, link, pay, one line on why, ⚠️ if there is any on-call flavor)
   - the new companies, with one line each on pay and remote policy
   - one or two trend-note lines
   - a link to https://dev.eukota.com/job-search-agent/
   If nothing new and good turned up, send one line saying so.
7. If the push or the email fails, send a push notification with the picks and what failed.
