// Pause the Reel on screen at a given second, so a screenshot can read its opening.
//
// The fallback: instagram-hooks.js's frame() shows frames without leaving the page and is
// the normal way. Use this only when frame() says the Reel has no plain video file or it
// would not load. Before sending it, `typeof window.__seek` says whether it is loaded.
//
// Runs on an instagram.com/reel/<code>/ page. Navigating reloads the page and loses this
// helper, so send this whole file once per Reel, followed by
//   await __seek(0.5)
// then take the screenshot. Later frames of the same Reel only need `await __seek(2.5)`.
// Verified against the live site on 2026-11-09.
//
// The page holds more than one <video>, and some have no size or no metadata yet, so it
// waits (up to 10 s) for a visible one with a known duration and uses the largest.
window.__seek = async (t) => {
  let v;
  for (let i = 0; i < 40 && !v; i++) {
    v = [...document.querySelectorAll('video')]
      .filter((x) => {
        const r = x.getBoundingClientRect();
        return r.width > 100 && r.top >= -5 && r.top < innerHeight / 2 && x.duration > 0;
      })
      .sort((a, b) => b.getBoundingClientRect().height - a.getBoundingClientRect().height)[0];
    if (!v) await new Promise((r) => setTimeout(r, 250));
  }
  if (!v) return { ok: false, note: 'no visible video with a known duration' };
  v.muted = true;
  v.pause();
  await new Promise((r) => {
    const done = () => r();
    v.addEventListener('seeked', done, { once: true });
    v.currentTime = t;
    setTimeout(done, 2500);
  });
  await new Promise((r) => setTimeout(r, 400));
  v.pause();
  return { ok: true, t: v.currentTime, duration: v.duration };
};
