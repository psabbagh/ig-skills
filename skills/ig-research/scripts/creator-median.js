// "Versus this creator's recent Reels": a candidate video's Instagram-only views
// divided by the median Instagram-only views of the creator's recent Reels.
//
// Runs INSIDE a signed-in instagram.com tab open at https://www.instagram.com/<handle>/reels/
// Paste this whole file into one javascript_exec call, followed by
//   __cmedian.start({videos: ['<code>', ...], reels: 15})
// with the codes of that creator's candidate videos, then poll
//   await __cmedian.wait(25000)
// until phase is "done" or "error". The result is small JSON; nothing else to copy.
// Verified against the live site on 2026-11-06.
//
// This is NOT the usual "outlier score", which divides by the median of the channel's
// Reels from the 90 days up to each video; building that needs months of history per
// creator, which Instagram's web app no longer lists cheaply. Compared with such a score
// on 12 videos, this one ranked them alike but its levels differed.
//
// How it works, cheapest first:
//   1. One media/<pk>/info lookup per candidate gives its Instagram-only views
//      (ig_play_count) and the total shown on the Reel (play_count, which adds
//      Facebook plays). If they differ by more than 5%, the creator cross-posts to
//      Facebook.
//   2. The Reels grid lists recent Reels with the shown total. For a creator who
//      doesn't cross-post that total is Instagram-only already, so the grid is enough.
//      The grid's own data carries no Instagram-only count (checked 2026-11-06).
//   3. Only for a creator who cross-posts, each of the recent Reels gets one
//      media/<pk>/info lookup for its Instagram-only views, paced 1.5 to 2.5 s apart,
//      stopping at the first sign of pushback.
// Pinned Reels, the candidates themselves and Reels under 3 days old (still climbing)
// are left out of the median.
(() => {
  const APP_ID = '936619743392459';
  const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
  const DAY = 86400000;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
  const pkOf = (c) => { let n = 0n; for (const ch of c.slice(0, 11)) n = n * 64n + BigInt(A.indexOf(ch)); return n; };
  const tsOf = (c) => Number((pkOf(c) >> 23n) + 1314220021721n); // Instagram ids carry their upload time
  const day = (t) => new Date(t).toISOString().slice(0, 10);
  const num = (s) => { const m = String(s).replace(/,/g, '').match(/([\d.]+)\s*([KMB]?)/i); if (!m) return null; return Math.round(parseFloat(m[1]) * ({ K: 1e3, M: 1e6, B: 1e9 }[(m[2] || '').toUpperCase()] || 1)); };
  const median = (a) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); const k = s.length >> 1; return s.length % 2 ? s[k] : (s[k - 1] + s[k]) / 2; };
  const pushedBack = (status, text) => status === 429 || /wait a few minutes|rate.?limit|checkpoint_required|login_required/i.test(text || '');

  const S = { phase: 'idle', requests: 0, note: null, result: null };

  async function info(code) {
    S.requests += 1;
    const r = await fetch('/api/v1/media/' + pkOf(code).toString() + '/info/', {
      credentials: 'include',
      headers: { 'X-IG-App-ID': APP_ID, 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf() },
    });
    const t = await r.text();
    if (pushedBack(r.status, r.ok ? '' : t)) throw new Error('pushback');
    if (!r.ok) return null;
    const m = JSON.parse(t).items[0];
    return { user: m.user && m.user.username, ig: m.ig_play_count ?? m.play_count ?? null, shown: m.play_count ?? null };
  }

  function gridReels() {
    const out = [];
    for (const a of document.querySelectorAll('a[href*="/reel/"]')) {
      const code = ((a.getAttribute('href') || '').match(/\/reel\/([A-Za-z0-9_-]+)/) || [])[1];
      if (code && !out.some((x) => x.code === code)) out.push({ code, t: tsOf(code), shown: num(a.innerText.replace(/\s+/g, ' ').trim()) });
    }
    return out;
  }

  async function run(videos, want) {
    const handle = location.pathname.split('/').filter(Boolean)[0];
    // 1. the candidates
    const cands = [];
    for (const code of videos) {
      const v = await info(code);
      cands.push({ code, ...(v || { ig: null, shown: null }) });
      await sleep(1500 + Math.random() * 1000);
    }
    const crossPoster = cands.some((c) => c.ig && c.shown && (c.shown - c.ig) / c.shown > 0.05);
    // 2. the grid: recent Reels, minus pinned ones, candidates and anything under 3 days old.
    // The grid adds only a few Reels per scroll, so keep scrolling (at most 8 times) until
    // there are `want` usable ones; a median of 10 Reels from 5 days proved unstable.
    let reels = gridReels();
    const first = reels.slice(0, 4);
    const pinned = new Set(first.slice(0, 3).filter((x) => first[3] && x.t < first[3].t).map((x) => x.code));
    const now = Date.now();
    const usable = (rs) => rs.filter((x) => !pinned.has(x.code) && !videos.includes(x.code) && now - x.t >= 3 * DAY);
    let still = 0;
    for (let i = 0; i < 8 && usable(reels).length < want && still < 2; i++) {
      const before = reels.length;
      window.scrollTo(0, document.documentElement.scrollHeight);
      await sleep(2500 + Math.random() * 1000);
      reels = gridReels();
      still = reels.length === before ? still + 1 : 0;
    }
    window.scrollTo(0, 0);
    const pool = usable(reels).sort((a, b) => b.t - a.t).slice(0, want);
    // 3. Instagram-only views for the pool, only when the creator cross-posts
    let basis = 'grid (creator does not cross-post, so the grid count is Instagram-only)';
    if (crossPoster) {
      basis = 'Instagram-only lookups (creator cross-posts to Facebook)';
      for (const x of pool) {
        const v = await info(x.code);
        x.ig = v ? v.ig : null;
        await sleep(1500 + Math.random() * 1000);
      }
    }
    const vals = pool.map((x) => (crossPoster ? x.ig : x.shown)).filter((v) => v != null);
    const med = median(vals);
    S.result = {
      handle, crossPoster, basis, n: vals.length,
      from: pool.length ? day(pool[pool.length - 1].t) : null, to: pool.length ? day(pool[0].t) : null,
      median: med,
      gridMedianShown: median(pool.map((x) => x.shown).filter((v) => v != null)),
      videos: cands.map((c) => ({ code: c.code, igViews: c.ig, shownViews: c.shown, vsRecentReels: c.ig && med ? +(c.ig / med).toFixed(2) : null })),
      requests: S.requests,
    };
  }

  window.__cmedian = {
    state: S,
    start({ videos = [], reels = 15 } = {}) {
      if (!/^\/[^/]+\/reels\/?$/.test(location.pathname)) return { phase: 'error', note: 'Open https://www.instagram.com/<handle>/reels/ first.' };
      if (!videos.length) return { phase: 'error', note: 'Give the codes of this creator\'s candidate videos.' };
      Object.assign(S, { phase: 'running', requests: 0, note: null, result: null });
      run(videos.map(String), Math.max(5, Math.min(30, Number(reels) || 15)))
        .then(() => { S.phase = 'done'; })
        .catch((e) => { S.phase = 'error'; S.note = e.message === 'pushback' ? 'Instagram pushed back; stopped. Try later.' : String(e); });
      return { phase: S.phase };
    },
    async wait(ms = 25000) {
      const end = Date.now() + ms;
      while (S.phase === 'running' && Date.now() < end) await sleep(1000);
      return S.phase === 'done' ? { phase: 'done', ...S.result } : { phase: S.phase, note: S.note, requests: S.requests };
    },
  };
})();
