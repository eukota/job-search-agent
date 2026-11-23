(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || '') ? u : '#');
  const day = (iso) => (iso ? String(iso).slice(0, 10) : '');
  const get = (url, fallback) => fetch(url, { cache: 'no-store' }).then((r) => (r.ok ? r.json() : fallback)).catch(() => fallback);

  const state = { jobs: [], picks: { picks: [] }, companies: { companies: [] } };

  // Tabs (remembered per browser)
  const tabs = document.querySelectorAll('.tab');
  function showTab(name) {
    tabs.forEach((t) => { const on = t.dataset.tab === name; t.classList.toggle('active', on); t.setAttribute('aria-selected', on); });
    ['picks', 'matches', 'companies'].forEach((n) => { $(`tab-${n}`).hidden = n !== name; });
    try { localStorage.setItem('radar_tab', name); } catch (e) { /* storage unavailable */ }
  }
  tabs.forEach((t) => t.addEventListener('click', () => showTab(t.dataset.tab)));

  function opsTag(flag, note) {
    return flag ? `<span class="tag warn">⚠️ ${esc(note || 'on-call / ops duties mentioned')}</span>` : '';
  }

  function renderPicks() {
    const { picks = [], updated, company_notes = [] } = state.picks;
    $('picks-note').textContent = picks.length
      ? `Hand-checked by the daily Claude scan · last updated ${day(updated)}`
      : 'No picks yet. The daily Claude scan adds them here.';
    $('picks').innerHTML = picks
      .slice()
      .sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))
      .map((p) => `
        <li class="item">
          <h3><span class="rank">${esc(p.rank ?? '')}.</span><a href="${esc(safeUrl(p.url))}" target="_blank" rel="noopener">${esc(p.company)} — ${esc(p.title)}</a></h3>
          <div class="meta">
            ${p.salary ? `<span>💵 ${esc(p.salary)}</span>` : ''}
            ${p.location ? `<span>${esc(p.location)}</span>` : ''}
            ${p.found_date ? `<span>found ${esc(p.found_date)}</span>` : ''}
          </div>
          ${p.why ? `<p class="why">${esc(p.why)}</p>` : ''}
          <div class="tags">${opsTag(p.ops_flag, p.ops_note)}${!p.ops_flag && p.ops_note ? `<span class="tag">${esc(p.ops_note)}</span>` : ''}</div>
        </li>`).join('');
    $('company-notes').innerHTML = company_notes.length
      ? `<h2>New on the company radar</h2><ul class="list">${company_notes.map((n) => `<li class="item"><b>${esc(n.name)}</b> — ${esc(n.note)}</li>`).join('')}</ul>`
      : '';
  }

  function filteredJobs() {
    const q = $('q').value.trim().toLowerCase();
    const lane = $('lane').value;
    const company = $('company').value;
    const minpay = Number($('minpay').value);
    const hideops = $('hideops').checked;
    const out = state.jobs.filter((j) => {
      if (hideops && j.ops_flag) return false;
      if (lane && !(j.lanes || []).includes(lane)) return false;
      if (company && j.company !== company) return false;
      if (minpay && (j.comp_max || 0) < minpay) return false;
      if (q && !`${j.title} ${j.company} ${j.location}`.toLowerCase().includes(q)) return false;
      return true;
    });
    const sort = $('sort').value;
    if (sort === 'new') out.sort((a, b) => String(b.first_seen_date).localeCompare(String(a.first_seen_date)));
    else if (sort === 'pay') out.sort((a, b) => (b.comp_max || 0) - (a.comp_max || 0));
    else out.sort((a, b) => (b.fit_score || 0) - (a.fit_score || 0));
    return out;
  }

  function renderMatches() {
    const jobs = filteredJobs();
    const now = Date.now();
    $('matches-count').textContent = `${jobs.length} of ${state.jobs.length} matching roles from the company radar`;
    $('matches').innerHTML = jobs.length ? jobs.map((j) => {
      const isNew = j.first_seen_date && now - Date.parse(j.first_seen_date) < 3 * 864e5;
      return `
        <li class="item">
          <h3><a href="${esc(safeUrl(j.url))}" target="_blank" rel="noopener">${esc(j.company)} — ${esc(j.title)}</a></h3>
          <div class="meta">
            <span class="score" title="Fit score (keyword based)">fit ${esc(j.fit_score)}</span>
            ${j.salary ? `<span>💵 ${esc(j.salary)}</span>` : ''}
            <span>${esc(j.location)}</span>
            <span>seen since ${esc(day(j.first_seen_date))}</span>
          </div>
          <div class="tags">
            ${isNew ? '<span class="tag good">new</span>' : ''}
            ${(j.lanes || []).map((l) => `<span class="tag">${esc(l)}</span>`).join('')}
            ${opsTag(j.ops_flag, j.ops_terms && j.ops_terms.length ? `mentions ${j.ops_terms.join(', ')}` : '')}
          </div>
        </li>`;
    }).join('') : '<li class="empty">No roles match these filters yet.</li>';
  }

  function renderCompanies() {
    const tier = $('tier').value;
    const list = (state.companies.companies || [])
      .filter((c) => !tier || c.tier === tier)
      .sort((a, b) => (a.tier || 'Z').localeCompare(b.tier || 'Z') || a.name.localeCompare(b.name));
    const counts = {};
    state.jobs.forEach((j) => { counts[j.company] = (counts[j.company] || 0) + 1; });
    $('companies').innerHTML = list.map((c) => {
      const s = c.scrape || {};
      const scrape = s.status === 'ok' ? `${s.open_roles} open · ${counts[c.name] || 0} match` : (s.status || 'not scraped yet');
      return `
        <div class="item">
          <h3><a href="${esc(safeUrl(c.careers_url))}" target="_blank" rel="noopener">${esc(c.name)}</a></h3>
          <div class="tags">
            <span class="tag ${c.tier === 'A' ? 'good' : ''}">Tier ${esc(c.tier || '?')}</span>
            ${c.ai_native ? '<span class="tag">AI-native</span>' : ''}
            ${c.added_by && c.added_by !== 'seed' ? `<span class="tag good">added ${esc(c.added)}</span>` : ''}
          </div>
          <p class="why">${esc(c.why)}</p>
          <div class="meta"><span>🏠 ${esc(c.remote_policy)}</span></div>
          <div class="meta"><span>💵 ${esc(c.pay_signal)}</span></div>
          <div class="meta"><span>📡 ${esc(scrape)}</span></div>
        </div>`;
    }).join('') || '<div class="empty">No companies yet.</div>';
  }

  function renderStats() {
    const picks = (state.picks.picks || []).length;
    const cos = (state.companies.companies || []).length;
    const now = Date.now();
    const fresh = state.jobs.filter((j) => j.first_seen_date && now - Date.parse(j.first_seen_date) < 3 * 864e5).length;
    $('stats').innerHTML = [[picks, 'top picks'], [state.jobs.length, 'matches'], [fresh, 'new (3d)'], [cos, 'companies']]
      .map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join('');
    $('updated').textContent = state.companies.updated ? ` Board refreshed ${day(state.companies.updated)}.` : '';
  }

  function fillSelect(id, values) {
    const el = $(id);
    values.forEach((v) => { const o = document.createElement('option'); o.value = v; o.textContent = v; el.appendChild(o); });
  }

  ['q', 'lane', 'company', 'minpay', 'sort', 'hideops'].forEach((id) => $(id).addEventListener('input', renderMatches));
  $('tier').addEventListener('input', renderCompanies);

  Promise.all([get('jobs.json', []), get('picks.json', { picks: [] }), get('companies.json', { companies: [] })]).then(([jobs, picks, companies]) => {
    state.jobs = Array.isArray(jobs) ? jobs : [];
    state.picks = picks || { picks: [] };
    state.companies = companies || { companies: [] };
    fillSelect('lane', [...new Set(state.jobs.flatMap((j) => j.lanes || []))].sort());
    fillSelect('company', [...new Set(state.jobs.map((j) => j.company))].sort());
    renderStats(); renderPicks(); renderMatches(); renderCompanies();
    let tab = 'picks';
    try { tab = localStorage.getItem('radar_tab') || 'picks'; } catch (e) { /* storage unavailable */ }
    showTab(tab);
  });
})();
