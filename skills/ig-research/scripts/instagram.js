// Instagram keyword search for one idea, across several phrasings -> videos with stats.
//
// Runs INSIDE a signed-in instagram.com tab that is already open at
//   https://www.instagram.com/explore/search/keyword/?q=<first phrasing>
// Paste this whole file into one javascript_exec call, followed by
//   __igsearch.start({queries: ['phrasing 1', 'phrasing 2', ...], limit: 50})
// then poll with `await __igsearch.wait(25000)` until phase is "done" or "error",
// then read rows with `__igsearch.dump(offset, count)` and `__igsearch.checksum()`.
// It stays loaded until the tab navigates: `window.__igsearch && window.__igsearch.version`
// returns 2 while it is, so a second search in the same tab needs only a new start(),
// not the file again. Return dump()'s array as it is: JSON.stringify (or a template
// string) around it makes one long string, which the browser tool cuts off.
// Verified against the live site on 2026-11-06.
//
// How it works. Instagram has no public keyword-search API. The search page loads
// results through a GraphQL query whose root field is xdt_fbsearch__top_serp_graphql,
// 24 posts per page, cursor-paginated. We let the page send one such request (by
// scrolling), keep its body as a template, and replay it with each phrasing in turn
// and our own cursor. Instagram's own infinite scroll sends the same request; the
// replay only skips the scrolling. Results from the phrasings are interleaved by
// position (every phrasing's 1st result, then every 2nd, ...) so no single phrasing
// crowds out the rest, and duplicates are merged. Search results carry likes and
// comments but not views, so each kept video then gets one /api/v1/media/<pk>/info/
// lookup, which returns plays, likes, comments, shares and duration. Everything runs
// with the browser's own session; no cookie or token leaves the page.
//
// If no search request can be captured (fewer than one page of results, or Instagram
// renamed the query), it falls back to the post links visible on the page, for the
// page's own phrasing only.
(() => {
  const prev = window.__igsearch;
  if (prev && prev.state && ['capturing', 'searching', 'enriching'].includes(prev.state.phase)) {
    return; // a run is in progress in this tab; keep it
  }

  const APP_ID = '936619743392459'; // Instagram web app id, public, sent by every web client
  const ROOT = 'xdt_fbsearch__top_serp_graphql';
  const MAX_ROUNDS = 8; // pages per phrasing
  const WORKERS = 3;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const jitter = (a, b) => a + Math.random() * (b - a);
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx'.replace(/x/g, () => ((Math.random() * 16) | 0).toString(16)));

  const S = {
    phase: 'idle', queries: [], limit: 50, mode: null, template: null,
    pages: 0, resultsSeen: 0, videos: [], rows: [], enriched: 0,
    errors: [], note: null, startedAt: null, finishedAt: null,
  };

  // ---- capture the page's own search request -------------------------------------
  function hook() {
    if (window.__igsearchHooked) return;
    window.__igsearchHooked = true;
    const XO = XMLHttpRequest.prototype.open;
    const XS = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (m, u) {
      this.__igsU = String(u);
      return XO.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function (body) {
      const x = this;
      if (x.__igsU && x.__igsU.includes('/graphql') && typeof body === 'string') {
        x.addEventListener('load', () => {
          const st = window.__igsearch && window.__igsearch.state;
          if (st && !st.template && typeof x.responseText === 'string' && x.responseText.includes(ROOT)) {
            st.template = { url: x.__igsU, body };
          }
        });
      }
      return XS.apply(this, arguments);
    };
    const F = window.fetch;
    window.fetch = async function (input, init) {
      const res = await F.apply(this, arguments);
      try {
        const u = typeof input === 'string' ? input : input.url;
        const body = init && init.body;
        const st = window.__igsearch && window.__igsearch.state;
        if (st && !st.template && u.includes('/graphql') &&
            (typeof body === 'string' || body instanceof URLSearchParams)) {
          res.clone().text().then((t) => {
            if (!st.template && t.includes(ROOT)) st.template = { url: u, body: String(body) };
          });
        }
      } catch (e) { /* never break the page */ }
      return res;
    };
  }

  async function captureTemplate(timeoutMs) {
    const end = Date.now() + timeoutMs;
    while (!S.template && Date.now() < end) {
      window.scrollTo(0, document.documentElement.scrollHeight);
      await sleep(1500);
    }
    window.scrollTo(0, 0);
    return !!S.template;
  }

  // ---- requests ------------------------------------------------------------------
  function rateLimited(status, text) {
    return status === 429 || /wait a few minutes|rate.?limit|checkpoint_required|login_required/i.test(text || '');
  }

  async function searchPage(query, sessionId, after) {
    const p = new URLSearchParams(S.template.body);
    const v = JSON.parse(p.get('variables'));
    v.query = query;
    v.search_session_id = sessionId;
    v.serp_session_id = sessionId;
    if (after) v.after = after; else delete v.after;
    p.set('variables', JSON.stringify(v));
    const headers = {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': csrf(),
      'X-IG-App-ID': APP_ID,
    };
    if (p.get('lsd')) headers['X-FB-LSD'] = p.get('lsd');
    if (p.get('fb_api_req_friendly_name')) headers['X-FB-Friendly-Name'] = p.get('fb_api_req_friendly_name');
    const r = await fetch(S.template.url, { method: 'POST', credentials: 'include', headers, body: p.toString() });
    const t = await r.text();
    if (rateLimited(r.status, r.ok ? '' : t)) throw new Error('rate_limited');
    let d;
    try { d = JSON.parse(t).data[ROOT]; } catch (e) { throw new Error('bad_search_response_http_' + r.status); }
    if (!d || !Array.isArray(d.edges)) throw new Error('bad_search_response_http_' + r.status);
    const items = d.edges.flatMap((e) => (e && e.node && e.node.items) || []);
    return { items, next: !!(d.page_info && d.page_info.has_next_page), cursor: d.page_info && d.page_info.end_cursor };
  }

  async function mediaInfo(pk) {
    const r = await fetch('/api/v1/media/' + pk + '/info/', {
      credentials: 'include',
      headers: { 'X-IG-App-ID': APP_ID, 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf() },
    });
    const t = await r.text();
    if (rateLimited(r.status, r.ok ? '' : t)) throw new Error('rate_limited');
    if (!r.ok) throw new Error('http_' + r.status);
    const d = JSON.parse(t);
    return d.items && d.items[0];
  }

  // ---- collection ------------------------------------------------------------------
  function codeToPk(code) {
    const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
    let n = 0n;
    for (const c of code.slice(0, 11)) n = n * 64n + BigInt(A.indexOf(c));
    return n.toString();
  }

  // Interleave every phrasing's videos by position and merge duplicates.
  // Returns [{pk, code, rank (best position in any phrasing), queries:Set, search}].
  function interleave(lists) {
    const byPk = new Map();
    const order = [];
    const longest = Math.max(0, ...lists.map((l) => l.length));
    for (let i = 0; i < longest; i++) {
      lists.forEach((list, qi) => {
        const e = list[i];
        if (!e) return;
        let v = byPk.get(e.pk);
        if (!v) {
          v = { pk: e.pk, code: e.code, rank: e.pos, queries: new Set(), search: e.item };
          byPk.set(e.pk, v);
          order.push(v);
        }
        v.rank = Math.min(v.rank, e.pos);
        v.queries.add(qi + 1);
      });
    }
    return order;
  }

  async function collectFromSearch() {
    const qs = S.queries.map((q) => ({ q, session: uuid(), after: null, done: false, seen: 0, list: [], pks: new Set() }));
    for (let round = 0; round < MAX_ROUNDS; round++) {
      for (const st of qs) {
        if (st.done) continue;
        let pg;
        try { pg = await searchPage(st.q, st.session, st.after); }
        catch (e) {
          if (e.message === 'rate_limited') throw e;
          S.errors.push('"' + st.q + '": ' + e.message);
          st.done = true;
          continue;
        }
        S.pages += 1;
        for (const it of pg.items) {
          if (!it || !it.pk) continue;
          st.seen += 1;
          S.resultsSeen += 1;
          if (st.pks.has(it.pk)) continue;
          st.pks.add(it.pk);
          if (it.media_type !== 2) continue; // videos only; photos and carousels are skipped
          st.list.push({ pk: String(it.pk), code: it.code, pos: st.seen, item: it });
        }
        if (!pg.next || !pg.cursor) st.done = true;
        else st.after = pg.cursor;
        await sleep(jitter(800, 1500));
      }
      if (interleave(qs.map((s) => s.list)).length >= S.limit || qs.every((s) => s.done)) break;
    }
    S.videos = interleave(qs.map((s) => s.list)).slice(0, S.limit);
    if (!S.videos.length && S.errors.length) throw new Error('search_failed');
  }

  function collectFromDom() {
    const seen = new Set();
    let rank = 0;
    for (const a of document.querySelectorAll('a[href*="/reel/"], a[href*="/p/"]')) {
      const m = a.getAttribute('href').match(/\/(?:reel|p)\/([A-Za-z0-9_-]+)/);
      if (!m || seen.has(m[1])) continue;
      seen.add(m[1]);
      rank += 1;
      // media type is unknown until the info lookup; non-videos are dropped there
      S.videos.push({ rank, pk: codeToPk(m[1]), code: m[1], queries: new Set([1]), search: null });
    }
  }

  const clean = (s) => String(s == null ? '' : s).replace(/[\t\r\n]+/g, ' ').replace(/\s{2,}/g, ' ').trim();
  const day = (ts) => (ts ? new Date(ts * 1000).toISOString().slice(0, 10) : '');
  const num = (x) => (typeof x === 'number' && isFinite(x) ? String(Math.round(x)) : '');

  function toRow(v, info) {
    const src = info || v.search || {};
    const user = src.user || (v.search && v.search.user) || {};
    // play_count is the number Instagram displays as views; for reels cross-posted to
    // Facebook it includes Facebook plays. ig_play_count is Instagram plays alone.
    const views = info ? (info.play_count ?? info.ig_play_count ?? info.view_count) : null;
    // When the creator hides like counts the API still sends like_count, but as a
    // placeholder (seen: 3 likes on 265K views). Leave it blank rather than report it.
    const hidden = src.like_and_view_counts_disabled === true;
    return {
      rank: String(v.rank),
      code: clean(v.code || src.code),
      username: clean(user.username),
      posted: day(src.taken_at),
      duration_s: typeof src.video_duration === 'number' ? src.video_duration.toFixed(1) : '',
      views: num(views),
      ig_views: num(info && info.ig_play_count),
      likes: hidden ? '' : num(src.like_count),
      comments: num(src.comment_count),
      shares: num(info && info.reshare_count),
      type: clean(src.product_type || (src.media_type === 2 ? 'video' : '')),
      queries: [...v.queries].sort((a, b) => a - b).join(','),
      caption: clean(src.caption && src.caption.text).slice(0, 70),
    };
  }

  async function enrich() {
    const out = new Array(S.videos.length);
    let next = 0;
    let stop = false;
    async function worker() {
      while (!stop) {
        const i = next++;
        if (i >= S.videos.length) return;
        const v = S.videos[i];
        try {
          const info = await mediaInfo(v.pk);
          if (S.mode === 'dom' && (!info || info.media_type !== 2)) { out[i] = null; }
          else out[i] = toRow(v, info);
        } catch (e) {
          if (e.message === 'rate_limited') {
            stop = true;
            S.note = 'Instagram rate-limited the per-post lookups; rows after that point have no views.';
          } else {
            S.errors.push(v.code + ': ' + e.message);
          }
          out[i] = S.mode === 'dom' ? null : toRow(v, null);
        }
        S.enriched += 1;
        await sleep(jitter(300, 700));
      }
    }
    await Promise.all(Array.from({ length: WORKERS }, worker));
    // anything never reached (after a rate limit) keeps its search-level stats
    for (let i = 0; i < S.videos.length; i++) {
      if (out[i] === undefined) out[i] = S.mode === 'dom' ? null : toRow(S.videos[i], null);
    }
    S.rows = out.filter(Boolean).slice(0, S.limit);
  }

  async function run() {
    try {
      S.phase = 'capturing';
      hook();
      const got = await captureTemplate(20000);
      S.phase = 'searching';
      if (got) {
        S.mode = 'search';
        try { await collectFromSearch(); }
        catch (e) {
          if (e.message === 'rate_limited') throw e;
          S.errors.push('search replay failed: ' + e.message);
          S.mode = 'dom';
          S.note = 'Search replay failed; used the post links on the page instead (first phrasing only).';
          collectFromDom();
        }
      } else {
        S.mode = 'dom';
        S.note = 'No search request captured while scrolling; used the post links on the page instead (first phrasing only).';
        collectFromDom();
      }
      S.phase = 'enriching';
      await enrich();
      S.phase = 'done';
    } catch (e) {
      S.phase = 'error';
      S.note = e.message === 'rate_limited'
        ? 'Instagram rate-limited the search itself. Wait several minutes before trying again.'
        : 'Failed: ' + e.message;
    } finally {
      S.finishedAt = new Date().toISOString();
    }
  }

  // ---- public surface ---------------------------------------------------------------
  const COLS = ['rank', 'code', 'username', 'posted', 'duration_s', 'views', 'ig_views', 'likes',
    'comments', 'shares', 'type', 'queries', 'caption'];

  function status() {
    return {
      phase: S.phase, mode: S.mode, queries: S.queries, limit: S.limit,
      pages: S.pages, resultsSeen: S.resultsSeen, videosFound: S.videos.length,
      enriched: S.enriched, rows: S.rows.length,
      errors: S.errors.slice(0, 10), errorCount: S.errors.length, note: S.note,
      startedAt: S.startedAt, finishedAt: S.finishedAt,
    };
  }

  window.__igsearch = {
    version: 2,
    state: S,
    start({ queries, limit = 50 } = {}) {
      if (['capturing', 'searching', 'enriching'].includes(S.phase)) return status(); // already running
      if (!location.pathname.startsWith('/explore/search/keyword')) {
        return { phase: 'error', note: 'Open https://www.instagram.com/explore/search/keyword/?q=<query> first (now at ' + location.pathname + ').' };
      }
      if (!csrf()) return { phase: 'error', note: 'Not signed in to Instagram in this browser.' };
      const pageQ = new URLSearchParams(location.search).get('q');
      S.queries = (Array.isArray(queries) && queries.length ? queries : [pageQ]).map(String).filter(Boolean).slice(0, 8);
      S.limit = Math.max(1, Math.min(200, Number(limit) || 50));
      // a second search in the same tab keeps the captured template, nothing else
      Object.assign(S, { phase: 'idle', mode: null, pages: 0, resultsSeen: 0, videos: [], rows: [],
        enriched: 0, errors: [], note: null, finishedAt: null });
      S.startedAt = new Date().toISOString();
      run();
      return status();
    },
    status,
    async wait(ms = 25000) {
      const end = Date.now() + ms;
      while (['capturing', 'searching', 'enriching'].includes(S.phase) && Date.now() < end) await sleep(1000);
      return status();
    },
    // Rows [offset, offset+count) as an array of TSV lines, header first when offset is 0.
    // An array, not one string: the browser tool truncates any single string near 1000
    // characters, but returns a 50-element array whole. So the caller must return it raw:
    // `__igsearch.dump(0, 50)`, never `JSON.stringify(__igsearch.dump(0, 50))`. Nothing in
    // here can stop a wrapper from making it one string; report.py's checksum catches a
    // cut-off copy (exit 2).
    dump(offset = 0, count = 50) {
      const lines = S.rows.slice(offset, offset + count).map((r) => COLS.map((c) => r[c]).join('\t'));
      return (offset === 0 ? [COLS.join('\t')] : []).concat(lines);
    },
    // Verifies a transcribed copy: djb2 over every row's fields except the caption.
    checksum() {
      let h = 5381;
      const body = S.rows.map((r) => COLS.slice(0, -1).map((c) => r[c]).join('\t')).join('\n');
      for (let i = 0; i < body.length; i++) h = (Math.imul(h, 33) + body.charCodeAt(i)) >>> 0;
      return { rows: S.rows.length, hash: h.toString(16).padStart(8, '0') };
    },
  };
})();
