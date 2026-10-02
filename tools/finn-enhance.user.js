// ==UserScript==
// @name         FINN -> Pokemon price overlay (local agent)
// @namespace    marius-pokemonkort
// @version      1.0.0
// @description  Adds instant PokeWallet price overlays to finn.no Pokemon listings via the local matcher agent (tools/local_agent.py at 127.0.0.1:8765). Hover any result for a price, auto-enriches ad pages, follows SPA navigation, and logs every ad you view so you can ask "all the Pichu's I looked at in the last 4 weeks".
// @author       93andresen
// @match        https://www.finn.no/*
// @match        https://finn.no/*
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @grant        GM_getValue
// @grant        GM_setValue
// @connect      127.0.0.1
// @connect      localhost
// @connect      finn.no
// @connect      www.finn.no
// @noframes
// @run-at       document-idle
// ==/UserScript==

/*
 * This userscript is a THIN CLIENT. All the real work (set index, PokeWallet
 * API calls, cache, budget guard, history log) lives in the local agent:
 *
 *     uv run tools/local_agent.py            # live, cache-first, budget-aware
 *     uv run tools/local_agent.py --offline   # cache-only (never spends a call)
 *
 * Endpoints used:
 *     GET  /health   -> { ok, version, offline, budget }
 *     GET  /match    -> ?heading=&price=&kode=&url=&status=&location=  (overlay payload)
 *     POST /log      -> viewed-ad JSON appended to data/finn/history/viewed.jsonl
 *     GET  /history  -> ?since_days=&match=&kode=  (previously viewed ads)
 *
 * Nothing is ever sent anywhere except 127.0.0.1; the agent never talks to
 * finn.no. Clipboard/URL enrichment fetches finn.no directly from the browser.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------- config --
  const CFG = {
    agentUrl: GM_getValue('agentUrl', 'http://127.0.0.1:8765'),
    autoEnrichAd: GM_getValue('autoEnrichAd', true),
    autoLog: GM_getValue('autoLog', true),
    hoverOverlay: GM_getValue('hoverOverlay', true),
    throttleMs: GM_getValue('throttleMs', 450),
  };
  const TAG = '[finn-pke]';
  const log = (...a) => console.log(TAG, ...a);
  const warn = (...a) => console.warn(TAG, ...a);

  // ------------------------------------------------------------- transport --
  function gm(method, url, opts) {
    opts = opts || {};
    return new Promise((resolve, reject) => {
      if (typeof GM_xmlhttpRequest === 'function') {
        const req = {
          method: method,
          url: url,
          headers: { 'Content-Type': 'application/json' },
          timeout: 25000,
          onload: (r) => {
            let body = r.responseText;
            try { body = JSON.parse(r.responseText); } catch (_) {}
            if (r.status >= 200 && r.status < 300) resolve(body);
            else reject(new Error('HTTP ' + r.status + ': ' +
              (typeof body === 'string' ? body.slice(0, 200) : JSON.stringify(body))));
          },
          onerror: () => reject(new Error('network error')),
          ontimeout: () => reject(new Error('timeout')),
        };
        if (opts.data != null) req.data = JSON.stringify(opts.data);
        GM_xmlhttpRequest(req);
        return;
      }
      // Fallback: plain fetch. http://127.0.0.1 is a "potentially trustworthy"
      // origin, so this is NOT blocked as mixed content from an https page.
      const init = { method: method, headers: { 'Content-Type': 'application/json' } };
      if (opts.data != null) init.body = JSON.stringify(opts.data);
      fetch(url, init)
        .then(async (resp) => {
          const text = await resp.text();
          let parsed = text;
          try { parsed = JSON.parse(text); } catch (_) {}
          if (resp.ok) resolve(parsed);
          else reject(new Error('HTTP ' + resp.status + ': ' + text.slice(0, 200)));
        })
        .catch(reject);
    });
  }
  const agentGet = (path, params) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return gm('GET', CFG.agentUrl + path + qs);
  };
  const agentPost = (path, data) => gm('POST', CFG.agentUrl + path, { data: data });

  // -------------------------------------------------------------- generic --
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  // Entities are built by concatenation so no literal "&"-style sequence
  // exists in this source (it keeps editors/linters from mangling them).
  const ESC_MAP = {
    '&': '&' + 'amp;', '<': '&' + 'lt;', '>': '&' + 'gt;',
    '"': '&' + 'quot;', "'": '&' + '#39;',
  };
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ESC_MAP[c]);

  function setCfg(key, value) {
    CFG[key] = value;
    GM_setValue(key, value);
    log('cfg', key, '=', value);
  }

  // ------------------------------------------------------------ dom parsing --
  const KODE_RE = /[?&]finnkode=(\d+)/;
  function kodeFrom(href) {
    if (!href) return null;
    let m = href.match(KODE_RE);
    if (m) return m[1];
    m = href.match(/\/(?:item|ad)\/(\d{6,})/);
    if (m) return m[1];
    m = href.match(/\/(\d{7,})(?:[/?#]|$)/);
    if (m) return m[1];
    m = href.match(/finnkode=(\d+)/);
    if (m) return m[1];
    return null;
  }

  function parseNok(text) {
    if (!text) return null;
    const flat = String(text).replace(/\u00a0/g, ' ');
    const m = flat.match(/(\d[\d\s.,]*)\s*kr\b/i);
    if (!m) return null;
    let raw = m[1].replace(/[^\d]/g, '');
    if (!raw) return null;
    const n = parseInt(raw, 10);
    return isNaN(n) ? null : n;
  }

  // Ad detail page extraction. Mirrors the selectors documented for
  // finn/finn_ad.py (server-rendered data-testid anchors).
  function extractAdFromDoc(doc, url) {
    const q = (sel) => doc.querySelector(sel);
    const titleEl = q('[data-testid="object-title"]') || q('h1');
    let heading = titleEl ? titleEl.textContent.trim() : (doc.title || '').trim();
    heading = heading.replace(/\s*[|\-–]\s*finn\.no.*$/i, '').trim();

    // Price: first short "N kr" text that is not the "Til salgs" label.
    let price = null;
    const nodes = doc.querySelectorAll('p, span, div, h2, h3, b, strong');
    for (const el of nodes) {
      const t = (el.textContent || '').trim();
      if (!t || t.length > 40) continue;
      if (/til salgs/i.test(t)) continue;
      const p = parseNok(t);
      if (p != null) { price = p; break; }
    }

    let status = 'Aktiv';
    const neg = q('.badge--negative');
    if (neg) {
      const bt = neg.textContent.toLowerCase();
      if (bt.includes('solgt')) status = 'Solgt';
      else if (bt.includes('inaktiv')) status = 'Inaktiv';
    }

    const locEl = q('[data-testid="object-address"]') || q('[data-testid="map-link"]');
    const location = locEl ? locEl.textContent.trim() : null;

    return {
      heading: heading,
      finn_price_nok: price,
      status: status,
      location: location,
      finn_kode: kodeFrom(url || (doc.location && doc.location.href)),
      url: url || (doc.location && doc.location.href) || null,
    };
  }

  // Search-result card detection.
  function headingIn(container) {
    if (!container) return '';
    const h = container.querySelector('h1, h2, h3, [data-testid*="title"], .headline');
    return h ? h.textContent.trim() : '';
  }

  function cardFromAnchor(a) {
    if (!a || !a.href) return null;
    const kode = kodeFrom(a.href);
    if (!kode) return null;
    let container = a.closest('article') || a.parentElement || a;
    // Climb a few levels until the block looks like a card (image or price).
    let el = container;
    for (let i = 0; i < 4 && el && el.parentElement; i++) {
      const txt = el.textContent || '';
      if (el.querySelector('img') || /\d\s*kr\b/i.test(txt)) break;
      el = el.parentElement;
    }
    container = el || container;
    const heading = (a.textContent || '').trim() || headingIn(container);
    const finn_price_nok = parseNok(container.textContent || '');
    return {
      kode: kode,
      anchor: a,
      container: container,
      heading: heading,
      finn_price_nok: finn_price_nok,
      url: a.href,
    };
  }

  function isAdPage() {
    const p = location.pathname;
    return /\/(?:item|ad)\/\d+/.test(p) ||
      /finnkode=\d+/.test(location.search) ||
      /\/(?:recommerce|bap)\/.*ad/i.test(p) ||
      !!document.querySelector('[data-testid="object-title"]');
  }

  // ------------------------------------------------------------- rich UI ----
  const CSS = [
    '.pke-badge{position:absolute;top:6px;right:6px;z-index:2147480000;',
    'font:600 11px/1.35 -apple-system,Segoe UI,Roboto,sans-serif;padding:3px 8px;',
    'border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.35);cursor:pointer;',
    'max-width:72%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.pke-badge.pke-loading{background:#3b3b3b;color:#e6e6e6}',
    '.pke-badge.pke-good{background:#0b3d2e;color:#eafff5}',
    '.pke-badge.pke-warn{background:#5a4a1f;color:#fff6df}',
    '.pke-badge.pke-bad{background:#5a1f1f;color:#ffecec}',
    '#pke-panel{position:fixed;right:14px;bottom:14px;width:370px;max-height:74vh;',
    'overflow:auto;z-index:2147483647;background:#12151b;color:#e8eef7;',
    'font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;border:1px solid #2a3242;',
    'border-radius:12px;box-shadow:0 12px 34px rgba(0,0,0,.55)}',
    '#pke-panel .pke-hd{display:flex;align-items:center;gap:8px;padding:10px 12px;',
    'border-bottom:1px solid #232b39;position:sticky;top:0;background:#12151b}',
    '#pke-panel .pke-hd b{flex:1;font-size:13px}',
    '#pke-panel .pke-hd button{background:#1d2531;color:#cfe0f5;border:1px solid #2f3a4c;',
    'border-radius:7px;padding:3px 8px;cursor:pointer;font-size:12px}',
    '#pke-panel .pke-body{padding:12px}',
    '#pke-panel .pke-row{margin:0 0 8px}',
    '#pke-panel .pke-k{color:#8fa3bd;font-size:11px;text-transform:uppercase;letter-spacing:.04em}',
    '#pke-panel .pke-big{font-size:22px;font-weight:700}',
    '#pke-panel .pke-good{color:#7ff0bb}',
    '#pke-panel .pke-bad{color:#ff9c9c}',
    '#pke-panel .pke-chip{display:inline-block;background:#1d2531;border:1px solid #2f3a4c;',
    'border-radius:999px;padding:1px 8px;margin:0 4px 4px 0;font-size:11px}',
    '#pke-panel a{color:#7fb2ff;text-decoration:none}',
    '#pke-panel ul{margin:6px 0 0;padding-left:16px}',
    '#pke-panel li{margin:0 0 4px}',
    '#pke-dot{width:9px;height:9px;border-radius:50%;background:#666;flex:0 0 auto}',
    '#pke-dot.ok{background:#37d67a}#pke-dot.off{background:#c94a4a}',
    '#pke-toast{position:fixed;left:14px;bottom:14px;z-index:2147483647;',
    'background:#12151b;color:#e8eef7;border:1px solid #2a3242;border-radius:10px;',
    'padding:8px 12px;font:12px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;',
    'box-shadow:0 8px 22px rgba(0,0,0,.5);max-width:340px}',
  ].join('');

  function injectCSS() {
    if (document.getElementById('pke-css')) return;
    const s = document.createElement('style');
    s.id = 'pke-css';
    s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }

  let toastTimer = null;
  function toast(msg, ms) {
    injectCSS();
    let el = document.getElementById('pke-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'pke-toast';
      document.body.appendChild(el);
    }
    el.innerHTML = msg;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.remove(); }, ms || 4200);
  }

  let panelEl = null;
  function panel(title) {
    injectCSS();
    if (!panelEl) {
      panelEl = document.createElement('div');
      panelEl.id = 'pke-panel';
      panelEl.innerHTML =
        '<div class="pke-hd">' +
        '<span id="pke-dot"></span>' +
        '<b id="pke-title">Pokemon price overlay</b>' +
        '<button id="pke-close">x</button>' +
        '</div><div class="pke-body" id="pke-body"></div>';
      document.body.appendChild(panelEl);
      panelEl.querySelector('#pke-close').addEventListener('click', () => {
        panelEl.style.display = 'none';
      });
    }
    if (title) panelEl.querySelector('#pke-title').textContent = title;
    panelEl.style.display = 'block';
    return panelEl.querySelector('#pke-body');
  }
  function setDot(state) {
    const d = document.getElementById('pke-dot');
    if (d) d.className = state || '';
  }

  function overlayHTML(ov) {
    if (!ov) return '<div class="pke-row">No data.</div>';
    if (ov.error) {
      return '<div class="pke-row pke-bad">' + esc(ov.error) + '</div>';
    }
    const p = ov.parsed || {};
    const parts = [];
    const titleLine = [p.card_name || ov.heading || '(untitled)',
      p.card_number ? '#' + p.card_number : '',
      p.set_hint ? '(' + p.set_hint + ')' : ''].filter(Boolean).join(' ');
    parts.push('<div class="pke-row"><div class="pke-k">FINN listing</div>' +
      esc(titleLine) + '</div>');

    if (ov.finn_price_nok != null) {
      parts.push('<div class="pke-row"><span class="pke-chip">FINN ' +
        ov.finn_price_nok.toLocaleString('nb-NO') + ' kr</span>' +
        (ov.status ? '<span class="pke-chip">' + esc(ov.status) + '</span>' : '') +
        (ov.location ? '<span class="pke-chip">' + esc(ov.location) + '</span>' : '') +
        '</div>');
    }

    const v = ov.value;
    if (v && v.est_nok != null) {
      const delta = v.delta_nok;
      const cls = delta == null ? '' : (delta >= 0 ? 'pke-bad' : 'pke-good');
      const dTxt = delta == null ? '' :
        (delta >= 0 ? 'FINN is ' + delta.toLocaleString('nb-NO') + ' kr over' :
          'FINN is ' + Math.abs(delta).toLocaleString('nb-NO') + ' kr under');
      parts.push('<div class="pke-row"><div class="pke-k">Market value (est.)</div>' +
        '<span class="pke-big ' + cls + '">~' + v.est_nok.toLocaleString('nb-NO') +
        ' kr</span> <span class="pke-chip">' + v.native +
        ' ' + esc(v.currency) + ' &middot; ' + esc(v.source || '') + '</span></div>' +
        (dTxt ? '<div class="pke-row ' + cls + '">' + esc(dTxt) + '</div>' : ''));
    } else {
      parts.push('<div class="pke-row pke-warn">No confident price match.</div>');
    }

    if (ov.best) {
      parts.push('<div class="pke-row"><div class="pke-k">Best match (score ' +
        ov.best.score + ')</div>' + esc(ov.best.name) + ' [' +
        esc(ov.best.set_name || '?') + '] #' + esc(ov.best.card_number || '?') +
        '</div>');
    }

    if (ov.candidates && ov.candidates.length) {
      const items = ov.candidates.map((c) => {
        const pr = c.price_native != null ?
          (c.price_native + ' ' + (c.price_currency || '')) : 'no price';
        return '<li>' + esc(c.name) + ' <span class="pke-chip">' +
          esc(c.set_name || '?') + ' #' + esc(c.card_number || '?') +
          '</span> <span class="pke-chip">' + esc(pr) + '</span> <span class="pke-chip">s' +
          c.score + '</span></li>';
      }).join('');
      parts.push('<div class="pke-row"><div class="pke-k">Candidates</div><ul>' +
        items + '</ul></div>');
    }

    if (ov.pricecharting_url) {
      parts.push('<div class="pke-row"><a href="' + esc(ov.pricecharting_url) +
        '" target="_blank" rel="noopener">PriceCharting search</a>' +
        '<span class="pke-chip">unconfirmed</span></div>');
    }

    const meta = [];
    meta.push(ov.cache_hit ? 'cache' : 'live');
    meta.push('calls ' + (ov.calls_spent || 0));
    if (ov.budget_note) meta.push(esc(ov.budget_note));
    parts.push('<div class="pke-row"><span class="pke-chip">' + meta.join('</span><span class="pke-chip">') +
      '</span></div>');

    return parts.join('');
  }

  // ---------------------------------------------------------- throttle q ----
  const queue = [];
  let processing = false;
  function enqueue(job) {
    queue.push(job);
    processQueue();
  }
  async function processQueue() {
    if (processing) return;
    processing = true;
    while (queue.length) {
      const job = queue.shift();
      try { await job(); } catch (e) { warn('job failed', e); }
      await sleep(CFG.throttleMs);
    }
    processing = false;
  }

  // ------------------------------------------------------------- matching ---
  const memo = new Map(); // kode -> overlay

  async function matchListing(listing) {
    if (listing.finn_kode && memo.has(listing.finn_kode)) {
      return memo.get(listing.finn_kode);
    }
    const params = {};
    if (listing.heading) params.heading = listing.heading;
    if (listing.finn_price_nok != null) params.price = listing.finn_price_nok;
    if (listing.finn_kode) params.kode = listing.finn_kode;
    if (listing.url) params.url = listing.url;
    if (listing.status) params.status = listing.status;
    if (listing.location) params.location = listing.location;
    const ov = await agentGet('/match', params);
    if (listing.finn_kode) memo.set(listing.finn_kode, ov);
    return ov;
  }

  async function maybeLog(listing, ov) {
    if (!CFG.autoLog) return;
    const rec = Object.assign({}, ov || {}, listing);
    delete rec.candidates; // keep the log compact; candidates live in the cache
    try { await agentPost('/log', rec); }
    catch (e) { warn('log failed', e); }
  }

  // Enrich the ad page: match, show panel, log.
  async function enrichCurrentAd(opts) {
    opts = opts || {};
    const listing = extractAdFromDoc(document, location.href);
    if (!listing.heading) {
      toast('No ad title found on this page.');
      return null;
    }
    setDot('');
    const body = panel('Ad: ' + (listing.heading || '').slice(0, 46));
    body.innerHTML = '<div class="pke-row">Querying local agent…</div>';
    try {
      const ov = await matchListing(listing);
      body.innerHTML = overlayHTML(ov);
      setDot('ok');
      await maybeLog(listing, ov);
      if (opts.toast && ov.value && ov.value.est_nok != null) {
        toast('Est. market value ~' + ov.value.est_nok.toLocaleString('nb-NO') + ' kr');
      }
      return ov;
    } catch (e) {
      setDot('off');
      body.innerHTML = overlayHTML({ error: String(e.message || e), parsed: { card_name: listing.heading } });
      toast('Local agent not reachable at ' + esc(CFG.agentUrl) + '. Is it running?');
      return null;
    }
  }

  // Enrich a search-result card (hover / batch).
  function badgeFor(card) {
    let badge = card.container.querySelector(':scope > .pke-badge');
    if (!badge) {
      if (getComputedStyle(card.container).position === 'static') {
        card.container.style.position = 'relative';
      }
      badge = document.createElement('span');
      badge.className = 'pke-badge pke-loading';
      badge.textContent = '…';
      badge.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        enrichCard(card, { force: true, open: true });
      });
      card.container.appendChild(badge);
    }
    return badge;
  }

  const cardSeen = new Set();
  function enrichCard(card, opts) {
    opts = opts || {};
    if (!card || !card.kode) return;
    if (!opts.force && cardSeen.has(card.kode)) return;
    cardSeen.add(card.kode);
    const badge = badgeFor(card);
    badge.className = 'pke-badge pke-loading';
    badge.textContent = '…';
    enqueue(async () => {
      const listing = {
        heading: card.heading,
        finn_price_nok: card.finn_price_nok,
        finn_kode: card.kode,
        url: card.url,
      };
      try {
        const ov = await matchListing(listing);
        const v = ov && ov.value;
        if (badge.isConnected) {
          if (v && v.est_nok != null) {
            badge.className = 'pke-badge ' + (v.delta_nok >= 0 ? 'pke-warn' : 'pke-good');
            badge.textContent = '~' + v.est_nok.toLocaleString('nb-NO') + ' kr';
            badge.title = 'FINN ' + (card.finn_price_nok || '?') + ' kr vs market ~' +
              v.est_nok + ' kr (' + v.native + ' ' + v.currency + ')';
          } else if (ov && ov.best) {
            badge.className = 'pke-badge pke-warn';
            badge.textContent = 's' + ov.best.score + ' ?';
            badge.title = 'Best: ' + ov.best.name + ' [' + (ov.best.set_name || '?') + ']';
          } else {
            badge.className = 'pke-badge pke-bad';
            badge.textContent = 'no match';
          }
        }
        if (opts.open) {
          const body = panel('Result: ' + (card.heading || '').slice(0, 44));
          body.innerHTML = overlayHTML(ov);
        }
        await maybeLog(listing, ov);
      } catch (e) {
        badge.className = 'pke-badge pke-bad';
        badge.textContent = 'agent?';
        badge.title = String(e.message || e);
      }
    });
  }

  function enrichVisibleCards() {
    const anchors = document.querySelectorAll('a[href]');
    let n = 0;
    for (const a of anchors) {
      const card = cardFromAnchor(a);
      if (card) { enrichCard(card); n++; }
    }
    toast('Queued <b>' + n + '</b> visible cards.');
    log('batch queued', n);
  }

  // ------------------------------------------------------------ clipboard ---
  function clipboardFinnUrl(text) {
    if (!text) return null;
    const m = String(text).match(/https?:\/\/(?:www\.)?finn\.no\/[^\s"'<>]+/i);
    return m ? m[0] : null;
  }

  async function enrichFromUrl(url) {
    if (!url) { toast('Clipboard has no finn.no link.'); return; }
    const body = panel('Clipboard: ' + url.slice(-40));
    body.innerHTML = '<div class="pke-row">Fetching listing…</div>';
    try {
      const html = await gm('GET', url);
      const text = typeof html === 'string' ? html : (html && html.responseText) || '';
      const doc = new DOMParser().parseFromString(text, 'text/html');
      const listing = extractAdFromDoc(doc, url);
      body.innerHTML = '<div class="pke-row">Matching…</div>';
      const ov = await matchListing(listing);
      body.innerHTML = overlayHTML(ov);
      setDot('ok');
      await maybeLog(listing, ov);
    } catch (e) {
      body.innerHTML = overlayHTML({ error: 'Fetch/match failed: ' + String(e.message || e) });
      setDot('off');
    }
  }

  async function enrichFromClipboard() {
    let text = '';
    try { text = await navigator.clipboard.readText(); }
    catch (e) { toast('Clipboard read blocked by the browser.'); return; }
    await enrichFromUrl(clipboardFinnUrl(text));
  }

  // -------------------------------------------------------------- history ---
  async function showHistory(sinceDays, match) {
    const body = panel('Viewed ads (last ' + (sinceDays || 28) + ' days' +
      (match ? ', "' + match + '"' : '') + ')');
    body.innerHTML = '<div class="pke-row">Loading history…</div>';
    try {
      const params = { since_days: sinceDays || 28, limit: 300 };
      if (match) params.match = match;
      const data = await agentGet('/history', params);
      const rows = (data && data.records) || [];
      if (!rows.length) { body.innerHTML = '<div class="pke-row">Nothing logged yet.</div>'; return; }
      const items = rows.map((r) => {
        const v = r.value;
        const price = r.finn_price_nok != null ? r.finn_price_nok + ' kr' : '?';
        const est = v && v.est_nok != null ? '~' + v.est_nok + ' kr' : '';
        const when = (r.viewed_at || '').replace('T', ' ').slice(0, 16);
        const link = r.url ? '<a href="' + esc(r.url) + '" target="_blank" rel="noopener">open</a>' : '';
        return '<li>' + esc(r.heading || '(untitled)') + ' <span class="pke-chip">' +
          esc(price) + (est ? ' / ' + esc(est) : '') + '</span> <span class="pke-chip">' +
          esc(when) + '</span> ' + link + '</li>';
      }).join('');
      body.innerHTML = '<div class="pke-row"><div class="pke-k">' + rows.length +
        ' viewed ad(s)</div><ul>' + items + '</ul></div>';
    } catch (e) {
      body.innerHTML = '<div class="pke-row pke-bad">History failed: ' + esc(String(e.message || e)) + '</div>';
    }
  }

  // ------------------------------------------------------- navigation/SPA ---
  let lastHref = location.href;
  let navTimer = null;
  function onUrlMaybeChanged() {
    if (location.href === lastHref) return;
    lastHref = location.href;
    clearTimeout(navTimer);
    navTimer = setTimeout(() => handleNavigation(), 900);
  }

  async function handleNavigation() {
    log('navigation ->', location.href);
    memo.clear();
    cardSeen.clear();
    if (isAdPage() && CFG.autoEnrichAd) {
      // Wait for the SPA to render the title, then enrich.
      for (let i = 0; i < 12; i++) {
        if (document.querySelector('[data-testid="object-title"], h1')) break;
        await sleep(250);
      }
      enrichCurrentAd({ toast: true });
    }
  }

  function hookHistory() {
    const wrap = (type) => {
      const orig = history[type];
      history[type] = function () {
        const ret = orig.apply(this, arguments);
        onUrlMaybeChanged();
        return ret;
      };
    };
    wrap('pushState');
    wrap('replaceState');
    window.addEventListener('popstate', onUrlMaybeChanged);
    // Safety net for frameworks that swap content without touching history.
    setInterval(onUrlMaybeChanged, 1200);
  }

  // --------------------------------------------------------------- hotkeys --
  function onKey(e) {
    if (!e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === 'e') {
      e.preventDefault();
      if (e.shiftKey) enrichFromClipboard();
      else if (isAdPage()) enrichCurrentAd({ toast: true });
      else enrichFromClipboard();
    } else if (k === 'h') {
      e.preventDefault();
      showHistory(28);
    } else if (k === 'o') {
      e.preventDefault();
      setCfg('hoverOverlay', !CFG.hoverOverlay);
      toast('Hover overlays ' + (CFG.hoverOverlay ? 'ON' : 'OFF'));
    } else if (k === 'a') {
      e.preventDefault();
      enrichVisibleCards();
    }
  }

  // -------------------------------------------------------------- hover -----
  function onHover(e) {
    if (!CFG.hoverOverlay) return;
    const a = e.target && e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    const card = cardFromAnchor(a);
    if (card) enrichCard(card);
  }

  // ---------------------------------------------------------- health check --
  async function refreshHealth() {
    try {
      const h = await agentGet('/health');
      setDot('ok');
      if (h) log('agent health', h);
      return h;
    } catch (e) {
      setDot('off');
      warn('agent unreachable at', CFG.agentUrl);
      return null;
    }
  }

  // ------------------------------------------------------------- menu ------
  function registerMenus() {
    if (typeof GM_registerMenuCommand !== 'function') return;
    GM_registerMenuCommand('Enrich current ad', () => enrichCurrentAd({ toast: true }));
    GM_registerMenuCommand('Enrich from clipboard link', () => enrichFromClipboard());
    GM_registerMenuCommand('Enrich all visible cards', () => enrichVisibleCards());
    GM_registerMenuCommand('Show history (last 4 weeks)', () => showHistory(28));
    GM_registerMenuCommand('Toggle ad auto-enrich (' + (CFG.autoEnrichAd ? 'ON' : 'OFF') + ')',
      () => { setCfg('autoEnrichAd', !CFG.autoEnrichAd); toast('Ad auto-enrich ' + (CFG.autoEnrichAd ? 'ON' : 'OFF')); });
    GM_registerMenuCommand('Toggle hover overlays (' + (CFG.hoverOverlay ? 'ON' : 'OFF') + ')',
      () => { setCfg('hoverOverlay', !CFG.hoverOverlay); toast('Hover overlays ' + (CFG.hoverOverlay ? 'ON' : 'OFF')); });
    GM_registerMenuCommand('Toggle viewed-ad logging (' + (CFG.autoLog ? 'ON' : 'OFF') + ')',
      () => { setCfg('autoLog', !CFG.autoLog); toast('Logging ' + (CFG.autoLog ? 'ON' : 'OFF')); });
  }

  // ---------------------------------------------------------------- init ----
  async function init() {
    log('userscript v1.0.0 loading; agent =', CFG.agentUrl);
    injectCSS();
    document.addEventListener('keydown', onKey, true);
    document.addEventListener('mouseover', onHover, true);
    hookHistory();
    registerMenus();
    const h = await refreshHealth();
    if (!h) {
      toast('Local agent not detected at <b>' + esc(CFG.agentUrl) +
        '</b>.<br>Start it with <code>uv run tools/local_agent.py</code>.<br>' +
        'Alt+E enrich &middot; Alt+H history &middot; Alt+A all cards.');
    } else {
      toast('FINN Pokemon overlay ready. Alt+E enrich &middot; Alt+H history &middot; Alt+A all cards.');
    }
    if (isAdPage() && CFG.autoEnrichAd) enrichCurrentAd({ toast: false });
  }

  init();
})();
