// What a few chosen Reels say and show: the source of their hooks and breakdowns.
//
// Runs INSIDE a signed-in instagram.com tab (any page). Before sending this file, check
// whether it is already loaded: `window.__ighooks && window.__ighooks.version` returns 2
// when it is, and then nothing needs sending again. Otherwise paste this whole file into
// one javascript_exec call, followed by
//   __ighooks.start({codes: ['<code>', ...]})
// then poll `await __ighooks.wait(25000)` until phase is "done" or "error", then read
// `__ighooks.dump(0, 10)`. For one Reel, `__ighooks.transcript('<code>')` gives the whole
// caption track and `__ighooks.caption('<code>')` the post's written caption.
// Frames: `await __ighooks.frame('<code>', 0.5)` shows that Reel paused at 0.5 s over the
// page, for a screenshot; `__ighooks.close()` takes it away. The tab never navigates, so
// this file is sent once for the whole step, not once per Reel.
// Verified against the live site on 2026-11-16.
//
// For each Reel: one media/<pk>/info lookup (paced 1.5 to 2.5 s apart, stopping at the
// first sign of pushback), then the caption track Instagram generated for it
// (video_subtitles_uri), when it has one. Nothing is saved to disk.
//
// Every result is an array of short strings, never one long string: the browser tool cuts
// a single string off at about 1,000 characters but returns an array whole. Return these
// calls' values as they are; wrapping one in JSON.stringify or a template string turns it
// into one long string and cuts it off.
(() => {
  const VERSION = 2;
  if (window.__ighooks && window.__ighooks.version === VERSION) return;
  const APP_ID = '936619743392459';
  const OPEN_S = 12; // the opening: the spoken hook
  const END_S = 10; // the ending: the payoff and the ask
  const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
  const pkOf = (c) => { let n = 0n; for (const ch of c.slice(0, 11)) n = n * 64n + BigInt(A.indexOf(ch)); return n.toString(); };
  const pushedBack = (status, text) => status === 429 || /wait a few minutes|rate.?limit|checkpoint_required|login_required/i.test(text || '');
  const clean = (s) => String(s == null ? '' : s).replace(/[\t\r\n]+/g, ' ').replace(/\s{2,}/g, ' ').trim();
  const mmss = (t) => Math.floor(t / 60) + ':' + String(Math.floor(t % 60)).padStart(2, '0');
  const S = { phase: 'idle', note: null, rows: [], errors: [], by: {} };

  // The track is SRT: "1\n00:00:00,000 --> 00:00:02,001\ntext\ntext\n\n2\n..."
  function cues(srt) {
    const out = [];
    for (const block of srt.split(/\r?\n\r?\n+/)) {
      const lines = block.split(/\r?\n/);
      const i = lines.findIndex((l) => l.includes('-->'));
      if (i < 0) continue;
      const m = lines[i].match(/^(\d+):(\d+):(\d+)/);
      if (!m) continue;
      const text = clean(lines.slice(i + 1).join(' '));
      if (text) out.push({ t: +m[1] * 3600 + +m[2] * 60 + +m[3], text });
    }
    return out;
  }

  async function one(code) {
    const r = await fetch('/api/v1/media/' + pkOf(code) + '/info/', {
      credentials: 'include',
      headers: { 'X-IG-App-ID': APP_ID, 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf() },
    });
    const t = await r.text();
    if (pushedBack(r.status, r.ok ? '' : t)) throw new Error('pushback');
    if (!r.ok) return { code, error: 'lookup HTTP ' + r.status };
    const m = JSON.parse(t).items[0];
    let track = [];
    if (m.video_subtitles_uri) {
      const res = await fetch(m.video_subtitles_uri);
      if (res.ok) track = cues(await res.text());
    }
    const d = typeof m.video_duration === 'number' ? m.video_duration : 0;
    const music = m.music_metadata && m.music_metadata.music_info && m.music_metadata.music_info.music_asset_info;
    return {
      code,
      user: clean(m.user && m.user.username),
      duration: d,
      track,
      opening: clean(track.filter((c) => c.t < OPEN_S).map((c) => c.text).join(' ')),
      ending: d > OPEN_S ? clean(track.filter((c) => c.t >= Math.max(OPEN_S, d - END_S)).map((c) => c.text).join(' ')) : '',
      caption: clean(m.caption && m.caption.text),
      song: music ? clean([music.title, music.display_artist].filter(Boolean).join(' - ')) : '',
      video: (m.video_versions && m.video_versions[0] && m.video_versions[0].url) || '',
    };
  }

  async function run(codes) {
    for (const code of codes) {
      const got = await one(code);
      if (got.error) S.errors.push(code + ': ' + got.error);
      else { S.rows.push(got); S.by[code] = got; }
      await sleep(1500 + Math.random() * 1000);
    }
  }

  // Split long text into pieces under the browser tool's per-string limit.
  const pieces = (s, n = 400) => { const out = []; for (let i = 0; i < s.length; i += n) out.push(s.slice(i, i + n)); return out; };

  async function frame(code, t) {
    const r = S.by[code];
    if (!r) return { ok: false, note: 'Not looked up: run start({codes}) with this code first.' };
    if (!r.video) return { ok: false, note: 'No plain video file for this Reel: open https://www.instagram.com/reel/' + code + '/ and use instagram-seek.js instead.' };
    let box = document.getElementById('__igframe');
    if (!box) {
      box = document.createElement('div');
      box.id = '__igframe';
      box.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:#000;display:flex;align-items:center;justify-content:center';
      document.body.appendChild(box);
    }
    let v = box.querySelector('video');
    if (!v || v.dataset.code !== code) {
      box.innerHTML = '';
      v = document.createElement('video');
      v.muted = true; v.playsInline = true; v.preload = 'auto'; v.dataset.code = code;
      v.style.cssText = 'height:100vh;max-width:100vw;object-fit:contain';
      v.src = r.video;
      box.appendChild(v);
      const meta = await new Promise((res) => {
        v.addEventListener('loadedmetadata', () => res('ok'), { once: true });
        v.addEventListener('error', () => res('error'), { once: true });
        setTimeout(() => res('timeout'), 10000);
      });
      if (meta !== 'ok') return { ok: false, note: 'The video did not load (' + meta + '): open https://www.instagram.com/reel/' + code + '/ and use instagram-seek.js instead.' };
    }
    const at = Math.max(0, Math.min(Number(t) || 0, v.duration - 0.1));
    v.pause();
    await new Promise((res) => {
      v.addEventListener('seeked', () => res(), { once: true });
      v.currentTime = at;
      setTimeout(res, 3000);
    });
    await sleep(300);
    return { ok: true, code, t: Math.round(v.currentTime * 10) / 10, duration: Math.round(v.duration * 10) / 10 };
  }

  window.__ighooks = {
    version: VERSION,
    state: S,
    start({ codes = [] } = {}) {
      if (!codes.length) return { phase: 'error', note: 'Give the Reel codes.' };
      if (codes.length > 10) return { phase: 'error', note: 'At most 10 Reels per batch.' };
      if (codes.some((c) => !/^[A-Za-z0-9_-]{6,}$/.test(c))) return { phase: 'error', note: 'Codes must be Reel codes, e.g. DfXcY28peC5.' };
      Object.assign(S, { phase: 'running', note: null, rows: [], errors: [] });
      run(codes.map(String)).then(() => { S.phase = 'done'; })
        .catch((e) => { S.phase = 'error'; S.note = e.message === 'pushback' ? 'Instagram pushed back; stopped. Try later.' : String(e); });
      return { phase: S.phase };
    },
    async wait(ms = 25000) {
      const end = Date.now() + ms;
      while (S.phase === 'running' && Date.now() < end) await sleep(1000);
      return { phase: S.phase, note: S.note, rows: S.rows.length, errors: S.errors };
    },
    // One "code<TAB>username<TAB>seconds<TAB>opening<TAB>ending" line per Reel. opening is
    // the first 12 s of the caption track (the spoken hook), ending its last 10 s (payoff
    // and ask); both are empty when the Reel has no track.
    dump(offset = 0, count = 10) {
      return S.rows.slice(offset, offset + count)
        .map((r) => [r.code, r.user, r.duration ? r.duration.toFixed(1) : '', r.opening, r.ending].join('\t'));
    },
    // The whole caption track of one Reel, one "[m:ss] text" line per cue.
    transcript(code) {
      const r = S.by[code];
      return r ? r.track.map((c) => '[' + mmss(c.t) + '] ' + c.text) : ['not looked up: ' + code];
    },
    // The post's written caption (first 1,200 characters) and its sound, in short pieces.
    caption(code) {
      const r = S.by[code];
      if (!r) return ['not looked up: ' + code];
      return pieces(r.caption.slice(0, 1200)).concat(r.song ? ['sound: ' + r.song] : []);
    },
    frame,
    close() { const b = document.getElementById('__igframe'); if (b) b.remove(); return { ok: true }; },
  };
})();
