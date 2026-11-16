// Read one Instagram post's caption and comments, read-only, in your own signed-in tab.
//
// Runs INSIDE a signed-in instagram.com tab (any page). Paste this whole file into one
// javascript_exec call, followed by
//   __igcomments.start({code: '<post code>', max: 300, replies: true})
// then poll `await __igcomments.wait(25000)` until phase is "done" or "error", then read
// `__igcomments.checksum()` and `__igcomments.dump(0, 100)`, `dump(100, 100)`, ...
//
// What it reads. One media/<pk>/info lookup for the caption and the owner, then the
// comment pages the post page itself loads (media/<pk>/comments, cursor-paginated),
// then, with replies: true, the replies under each comment that has any
// (media/<pk>/comments/<id>/child_comments), so it can tell which comments the owner
// already answered. Every request is a GET with the browser's own session, paced 1.5 to
// 3 s apart like a person scrolling, and it stops at the first sign of pushback.
// Nothing is posted, liked or sent, and nothing leaves the page.
//
// For someone else's post, read only the caption and the first page of top comments:
//   __igcomments.start({code: '<post code>', max: 20, replies: false})
(() => {
  const APP_ID = '936619743392459'; // Instagram web app id, public, sent by every web client
  const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
  const MAX_COMMENTS = 1000;
  const MAX_REPLY_THREADS = 120;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const pace = () => sleep(1500 + Math.random() * 1500);
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
  const pkOf = (c) => { let n = 0n; for (const ch of c.slice(0, 11)) n = n * 64n + BigInt(A.indexOf(ch)); return n.toString(); };
  const pushedBack = (status, text) => status === 429 || /wait a few minutes|rate.?limit|checkpoint_required|login_required/i.test(text || '');
  const clean = (s) => String(s == null ? '' : s).replace(/[\t\r\n]+/g, ' ').replace(/\s{2,}/g, ' ').trim();
  const S = { phase: 'idle', note: null, post: null, rows: [], errors: [], pages: 0 };

  async function get(path) {
    const r = await fetch(path, {
      credentials: 'include',
      headers: { 'X-IG-App-ID': APP_ID, 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf() },
    });
    const t = await r.text();
    if (pushedBack(r.status, r.ok ? '' : t)) throw new Error('pushback');
    if (!r.ok) throw new Error('HTTP ' + r.status + ' on ' + path.split('?')[0]);
    return JSON.parse(t);
  }

  const row = (c, parent) => ({
    id: String(c.pk || c.id),
    parent: parent || '',
    user: clean(c.user && c.user.username),
    ts: c.created_at || c.created_at_utc || 0,
    likes: c.comment_like_count || 0,
    replies: c.child_comment_count || 0,
    text: clean(c.text),
  });

  async function run({ code, max, replies }) {
    const pk = pkOf(code);
    const info = await get('/api/v1/media/' + pk + '/info/');
    const m = info.items[0];
    S.post = {
      code, owner: clean(m.user && m.user.username), ts: m.taken_at || 0,
      comments: m.comment_count || 0, likes: m.like_count || 0,
      caption: clean(m.caption && m.caption.text),
    };
    // max counts comments, not rows: replies never use it up. Preview replies are kept
    // only with replies: true, so replies: false gives exactly the first max comments.
    let cursor = null;
    let top = 0;
    while (top < max) {
      await pace();
      const q = new URLSearchParams({ can_support_threading: 'true', permalink_enabled: 'false' });
      if (cursor) q.set('min_id', cursor);
      const page = await get('/api/v1/media/' + pk + '/comments/?' + q.toString());
      S.pages++;
      for (const c of page.comments || []) {
        if (top >= max) break;
        S.rows.push(row(c, ''));
        top++;
        if (replies) for (const p of c.preview_child_comments || []) S.rows.push(row(p, String(c.pk)));
      }
      cursor = page.next_min_id;
      if (!cursor || !(page.comments || []).length) break;
    }
    if (!replies) return;
    const seen = new Set(S.rows.map((r) => r.id));
    const threads = S.rows.filter((r) => !r.parent && r.replies > 0).slice(0, MAX_REPLY_THREADS);
    if (S.rows.filter((r) => !r.parent && r.replies > 0).length > MAX_REPLY_THREADS) {
      S.note = 'Read replies under the first ' + MAX_REPLY_THREADS + ' threads only.';
    }
    for (const t of threads) {
      let rc = null;
      for (let guard = 0; guard < 5; guard++) {
        await pace();
        const q = new URLSearchParams();
        if (rc) q.set('max_id', rc);
        const page = await get('/api/v1/media/' + pk + '/comments/' + t.id + '/child_comments/?' + q.toString());
        for (const c of page.child_comments || []) {
          const r = row(c, t.id);
          if (!seen.has(r.id)) { seen.add(r.id); S.rows.push(r); }
        }
        rc = page.has_more_tail_child_comments ? page.next_max_child_cursor : null;
        if (!rc) break;
      }
    }
  }

  // The browser tool cuts any string past about a thousand characters, so long text goes
  // out in CHUNK-sized pieces: the first on the line itself, the rest on "#more" lines.
  const CHUNK = 400;
  const split = (fields, text) => {
    const out = [fields.concat(text.slice(0, CHUNK)).join('\t')];
    for (let i = CHUNK; i < text.length; i += CHUNK) out.push(['#more', '', '', '', '', text.slice(i, i + CHUNK)].join('\t'));
    return out;
  };
  const lines = () => (S.post ? split(['#post', S.post.code, S.post.owner, S.post.ts, S.post.comments], S.post.caption)
    .concat(...S.rows.map((r) => split([r.id, r.parent, r.user, r.ts, r.likes], r.text))) : []);

  window.__igcomments = {
    state: S,
    start({ code, max = 300, replies = true } = {}) {
      if (!code || !/^[A-Za-z0-9_-]{6,}$/.test(code)) return { phase: 'error', note: 'Give the post code, e.g. DfXcY28peC5 from /reel/DfXcY28peC5/.' };
      if (S.phase === 'running') return { phase: 'running' };
      Object.assign(S, { phase: 'running', note: null, post: null, rows: [], errors: [], pages: 0 });
      run({ code, max: Math.min(+max || 300, MAX_COMMENTS), replies: !!replies })
        .then(() => { S.phase = 'done'; })
        .catch((e) => {
          S.phase = S.post ? 'done' : 'error';
          S.note = e.message === 'pushback' ? 'Instagram pushed back; stopped with what was read. Try later, do not retry in a loop.' : String(e.message || e);
        });
      return { phase: S.phase };
    },
    async wait(ms = 25000) {
      const end = Date.now() + ms;
      while (S.phase === 'running' && Date.now() < end) await sleep(1000);
      return { phase: S.phase, note: S.note, pages: S.pages, rows: S.rows.length, post: S.post && { owner: S.post.owner, comments: S.post.comments } };
    },
    // First line "#post<TAB>code<TAB>owner<TAB>taken_at<TAB>comment_count<TAB>caption", then one
    // "id<TAB>parent_id<TAB>username<TAB>created_at<TAB>likes<TAB>text" line per comment; text
    // longer than CHUNK continues on "#more<TAB><TAB><TAB><TAB><TAB>rest" lines.
    // An array of short lines, because the browser tool truncates any single long string.
    dump(offset = 0, count = 100) {
      return lines().slice(offset, offset + count);
    },
    checksum() {
      let h = 5381;
      const all = lines();
      const body = all.join('\n');
      for (let i = 0; i < body.length; i++) h = (Math.imul(h, 33) + body.charCodeAt(i)) >>> 0;
      return { lines: all.length, comments: S.rows.length, hash: h.toString(16).padStart(8, '0') };
    },
  };
})();
