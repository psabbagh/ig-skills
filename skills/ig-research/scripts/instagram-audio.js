// Fetch the audio of a few picked Instagram Reels, for transcription.
//
// Runs INSIDE a signed-in instagram.com tab (any page). Paste this whole file into one
// javascript_exec call, followed by
//   __igaudio.start({codes: ['<code>', ...]})
// then poll `await __igaudio.wait(25000)` until phase is "done" or "error".
// Verified against the live site on 2026-11-06.
//
// For each Reel: one media/<pk>/info lookup (paced 1.5 to 2.5 s apart, stopping at the
// first sign of pushback), then the audio-only track from its DASH manifest, the same
// file the page streams when the Reel plays (about 7 KB per second of video). If a Reel
// has no separate audio track, the smallest video file is used instead. All tracks go
// into ONE tar file that Chrome saves to the Downloads folder as
// ig-research-audio-<id>.tar: one file per batch, so Chrome never asks about
// multiple downloads. transcribe.py takes it from there and deletes it.
// Saving a file is a download: run this only when the person asked for transcripts.
(() => {
  const APP_ID = '936619743392459';
  const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
  const pkOf = (c) => { let n = 0n; for (const ch of c.slice(0, 11)) n = n * 64n + BigInt(A.indexOf(ch)); return n.toString(); };
  const pushedBack = (status, text) => status === 429 || /wait a few minutes|rate.?limit|checkpoint_required|login_required/i.test(text || '');
  const S = { phase: 'idle', note: null, result: null };

  async function trackFor(code) {
    const r = await fetch('/api/v1/media/' + pkOf(code) + '/info/', {
      credentials: 'include',
      headers: { 'X-IG-App-ID': APP_ID, 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf() },
    });
    const t = await r.text();
    if (pushedBack(r.status, r.ok ? '' : t)) throw new Error('pushback');
    if (!r.ok) return { code, error: 'lookup HTTP ' + r.status };
    const m = JSON.parse(t).items[0];
    let url = null, kind = 'audio';
    if (m.video_dash_manifest) {
      const doc = new DOMParser().parseFromString(m.video_dash_manifest, 'application/xml');
      const reps = [...doc.getElementsByTagName('Representation')].filter((rp) =>
        ((rp.getAttribute('mimeType') || rp.parentNode.getAttribute('mimeType') || rp.parentNode.getAttribute('contentType') || '')).includes('audio'));
      reps.sort((a, b) => +a.getAttribute('bandwidth') - +b.getAttribute('bandwidth'));
      const base = reps[0] && reps[0].getElementsByTagName('BaseURL')[0];
      if (base) url = base.textContent.trim();
    }
    if (!url && m.video_versions && m.video_versions.length) {
      const v = [...m.video_versions].sort((a, b) => (a.width * a.height) - (b.width * b.height))[0];
      url = v.url; kind = 'video';
    }
    if (!url) return { code, error: 'no audio or video track' };
    const res = await fetch(url);
    if (!res.ok) return { code, error: 'track HTTP ' + res.status };
    const bytes = new Uint8Array(await res.arrayBuffer());
    return { code, kind, bytes, seconds: m.video_duration, user: m.user && m.user.username };
  }

  // Minimal ustar archive: a 512-byte header per file, data padded to 512, two empty blocks.
  function tar(files) {
    const enc = new TextEncoder();
    const chunks = [];
    for (const f of files) {
      const h = new Uint8Array(512);
      const put = (s, off, len) => h.set(enc.encode(s).slice(0, len), off);
      const oct = (n, len) => n.toString(8).padStart(len - 1, '0') + '\0';
      put(f.name, 0, 100); put(oct(0o644, 8), 100, 8); put(oct(0, 8), 108, 8); put(oct(0, 8), 116, 8);
      put(oct(f.bytes.length, 12), 124, 12); put(oct(Math.floor(Date.now() / 1000), 12), 136, 12);
      put('        ', 148, 8); put('0', 156, 1); put('ustar\0' + '00', 257, 8);
      let sum = 0; for (const b of h) sum += b;
      put(sum.toString(8).padStart(6, '0') + '\0 ', 148, 8);
      chunks.push(h, f.bytes);
      const pad = (512 - (f.bytes.length % 512)) % 512;
      if (pad) chunks.push(new Uint8Array(pad));
    }
    chunks.push(new Uint8Array(1024));
    return new Blob(chunks, { type: 'application/x-tar' });
  }

  async function run(codes) {
    const files = [], errors = [];
    for (const code of codes) {
      const got = await trackFor(code);
      if (got.error) errors.push(code + ': ' + got.error);
      else files.push({ name: code + (got.kind === 'audio' ? '.m4a' : '.mp4'), bytes: got.bytes, code, kind: got.kind, seconds: got.seconds, user: got.user });
      await sleep(1500 + Math.random() * 1000);
    }
    if (!files.length) throw new Error('nothing fetched: ' + errors.join('; '));
    const id = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14) + '-' + Math.random().toString(36).slice(2, 6);
    const name = 'ig-research-audio-' + id + '.tar';
    const blob = tar(files);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    S.result = {
      archive: name, bytes: blob.size, errors,
      files: files.map((f) => ({ code: f.code, user: f.user, kind: f.kind, bytes: f.bytes.length, seconds: f.seconds && Math.round(f.seconds) })),
    };
  }

  window.__igaudio = {
    version: 1,
    state: S,
    start({ codes = [] } = {}) {
      if (!codes.length) return { phase: 'error', note: 'Give the Reel codes.' };
      if (codes.length > 10) return { phase: 'error', note: 'At most 10 Reels per batch.' };
      if (codes.some((c) => !/^[A-Za-z0-9_-]{6,}$/.test(c))) return { phase: 'error', note: 'Codes must be Reel codes, e.g. DfXcY28peC5.' };
      Object.assign(S, { phase: 'running', note: null, result: null });
      run(codes.map(String)).then(() => { S.phase = 'done'; })
        .catch((e) => { S.phase = 'error'; S.note = e.message === 'pushback' ? 'Instagram pushed back; stopped. Try later.' : String(e); });
      return { phase: S.phase };
    },
    async wait(ms = 25000) {
      const end = Date.now() + ms;
      while (S.phase === 'running' && Date.now() < end) await sleep(1000);
      return S.phase === 'done' ? { phase: 'done', ...S.result } : { phase: S.phase, note: S.note };
    },
  };
})();
