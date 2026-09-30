// Signal · Mac 桌面小组件（Übersicht）
// 读网站上的同一份数据，设计和手机上的大号小组件一致。每 30 分钟刷新一次。
// 轻点：在默认浏览器里打开网站。按住拖动：移动位置，松手后吸附到旁边的原生小组件并记住。
//
// 对齐方式：直接读系统里原生小组件的实际位置（窗口位置，不需要额外权限），
// 以离得最近的原生小组件为基准，按它的格子（每格 180，小组件 163 + 间距 17）找最近的空位，
// 不会压住原生小组件。原生小组件挪了，Signal 每分钟检查一次，被压住或错位就自动挪到最近的空位。
// 桌面上没有原生小组件时，退回按屏幕边缘对齐。

import { run } from "uebersicht";

const SITE = "https://2593040259zhangzhenning-blip.github.io/daily-ai-news/";

export const refreshFrequency = 30 * 60 * 1000;

// 位置记在本机
const POS_KEY = "daily-ai-news-pos-v3";
const loadPos = () => {
  try {
    const p = JSON.parse(localStorage.getItem(POS_KEY) || "null");
    if (p && Number.isFinite(p.left) && Number.isFinite(p.top)) return p;
  } catch (e) {}
  return null;
};
const savePos = (p) => { try { localStorage.setItem(POS_KEY, JSON.stringify(p)); } catch (e) {} };

const SIZE = 343;          // 和原生大号小组件同尺寸
const PITCH = 180;         // 原生网格每格
const CELL = PITCH * 2;    // Signal 占 2×2 格
const INSET = (CELL - SIZE) / 2; // 格子四周留出的间距（8.5）

// 读原生小组件的位置：列出屏幕上的窗口，挑出桌面层、尺寸是 180 整数倍的那些（就是原生小组件的格子），
// 同时拿到 Übersicht 窗口的位置，把屏幕坐标换成小组件坐标。
const PROBE = `osascript -l JavaScript -e 'ObjC.import("CoreGraphics");
var a = ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo(1, 0))) || [];
var o = { host: null, cells: [] };
var ok = function (v) { return v >= 179 && v <= 721 && Math.abs(v / 180 - Math.round(v / 180)) < 0.02; };
a.forEach(function (w) {
  var b = w.kCGWindowBounds, n = String(w.kCGWindowOwnerName || ""), L = w.kCGWindowLayer;
  if (!b) return;
  if (n.indexOf("bersicht") >= 0) { if (b.Width > 400 && (!o.host || b.Width * b.Height > o.host.w * o.host.h)) o.host = { x: b.X, y: b.Y, w: b.Width, h: b.Height }; return; }
  if (L < -2147483000 && ok(b.Width) && ok(b.Height)) o.cells.push({ x: b.X, y: b.Y, w: b.Width, h: b.Height });
});
JSON.stringify(o);'`;

const readNative = () =>
  run(PROBE)
    .then((out) => {
      const o = JSON.parse(out);
      const hx = o.host ? o.host.x : 0, hy = o.host ? o.host.y : 0;
      return o.cells
        .map((c) => ({ x: c.x - hx, y: c.y - hy, w: c.w, h: c.h }))
        .filter((c) => c.x + c.w > 0 && c.y + c.h > 0 && c.x < window.innerWidth && c.y < window.innerHeight);
    })
    .catch(() => []);

const overlaps = (a, b) => a.x < b.x + b.w - 1 && b.x < a.x + a.w - 1 && a.y < b.y + b.h - 1 && b.y < a.y + a.h - 1;

// 给定 Signal 左上角（小组件坐标），返回吸附后的位置
const snapTo = (left, top, cells) => {
  const W = window.innerWidth, H = window.innerHeight;
  const cx = left - INSET, cy = top - INSET; // 换成格子坐标
  const fits = (x, y) => x >= -1 && y >= -1 && x + CELL <= W + 1 && y + CELL <= H + 1;
  if (!cells.length) {
    // 没有原生小组件：靠哪边就按哪边的边距对齐
    const m = 8;
    const fromRight = cx + CELL / 2 > W / 2;
    const k = Math.max(0, Math.round((fromRight ? W - m - CELL - cx : cx - m) / PITCH));
    const x = fromRight ? W - m - CELL - k * PITCH : m + k * PITCH;
    const j = Math.max(0, Math.min(Math.floor((H - m - CELL) / PITCH), Math.round((cy - m) / PITCH)));
    return { left: x + INSET, top: m + j * PITCH + INSET };
  }
  // 以最近的原生小组件为基准
  const d2 = (c) => (c.x + c.w / 2 - (cx + CELL / 2)) ** 2 + (c.y + c.h / 2 - (cy + CELL / 2)) ** 2;
  const anchor = cells.reduce((a, c) => (d2(c) < d2(a) ? c : a));
  const i0 = Math.round((cx - anchor.x) / PITCH), j0 = Math.round((cy - anchor.y) / PITCH);
  let best = null;
  for (let di = -12; di <= 12; di++) {
    for (let dj = -8; dj <= 8; dj++) {
      const x = anchor.x + (i0 + di) * PITCH, y = anchor.y + (j0 + dj) * PITCH;
      if (!fits(x, y)) continue;
      const r = { x, y, w: CELL, h: CELL };
      if (cells.some((c) => overlaps(r, c))) continue;
      const dist = (x - cx) ** 2 + (y - cy) ** 2;
      if (!best || dist < best.dist) best = { x, y, dist };
    }
  }
  if (!best) return { left, top }; // 找不到空位就原地不动
  return { left: best.x + INSET, top: best.y + INSET };
};

// 第一次出现：放在原生小组件那一列的正上方（放不下就找最近的空位）；没有原生小组件就放右上角
const defaultPos = (cells) => {
  if (!cells.length) return snapTo(window.innerWidth, 0, cells);
  const topmost = cells.reduce((a, c) => (c.y < a.y ? c : a));
  return snapTo(topmost.x + INSET, topmost.y - CELL + INSET, cells);
};

const saved = loadPos();
export const className = saved
  ? `left: ${saved.left}px; top: ${saved.top}px;`
  : `right: 24px; top: 24px;`;

const box = () => {
  const el = document.querySelector(".dan");
  return el ? el.parentElement : null; // Übersicht 包在外面、带定位的那一层
};
const moveBox = (b, p, animate) => {
  if (animate) {
    b.style.transition = "left .18s ease, top .18s ease";
    setTimeout(() => { b.style.transition = ""; }, 220);
  }
  Object.assign(b.style, { left: p.left + "px", top: p.top + "px", right: "auto", bottom: "auto" });
};

// 每分钟看一眼原生小组件：被压住、错位或者第一次出现，就挪到最近的空位
let dragging = null;
const relayout = (animate) => {
  const b = box();
  if (!b || dragging) return;
  readNative().then((cells) => {
    if (dragging) return;
    const cur = loadPos();
    const r = b.getBoundingClientRect();
    const p = cur ? snapTo(r.left, r.top, cells) : defaultPos(cells);
    if (Math.abs(p.left - r.left) > 0.5 || Math.abs(p.top - r.top) > 0.5) moveBox(b, p, animate);
    savePos(p);
  });
};
if (window.__signalTimer) clearInterval(window.__signalTimer);
window.__signalTimer = setInterval(() => relayout(true), 60 * 1000);
setTimeout(() => relayout(false), 800);

// 按住移动超过 4 像素算拖动，否则算点击
const onMouseDown = (e) => {
  if (e.button !== 0) return;
  const b = e.currentTarget.parentElement;
  const rect = b.getBoundingClientRect();
  dragging = { b, dx: e.clientX - rect.left, dy: e.clientY - rect.top, x0: e.clientX, y0: e.clientY, moved: false };
  const cellsP = readNative(); // 按下时就开始读，松手时基本已经读完
  const move = (ev) => {
    if (!dragging) return;
    if (!dragging.moved && Math.hypot(ev.clientX - dragging.x0, ev.clientY - dragging.y0) < 4) return;
    dragging.moved = true;
    const left = Math.max(0, Math.min(window.innerWidth - 60, ev.clientX - dragging.dx));
    const top = Math.max(0, Math.min(window.innerHeight - 60, ev.clientY - dragging.dy));
    Object.assign(dragging.b.style, { left: left + "px", top: top + "px", right: "auto", bottom: "auto" });
  };
  const up = () => {
    window.removeEventListener("mousemove", move);
    window.removeEventListener("mouseup", up);
    const d = dragging;
    if (!d) return;
    if (!d.moved) { dragging = null; open(); return; }
    const r = d.b.getBoundingClientRect();
    cellsP.then((cells) => {
      const p = snapTo(r.left, r.top, cells);
      moveBox(d.b, p, true);
      savePos(p);
      dragging = null;
    });
  };
  window.addEventListener("mousemove", move);
  window.addEventListener("mouseup", up);
  e.preventDefault();
};

export const initialState = { data: null, error: null };

export const command = (dispatch) =>
  fetch(SITE + "data/latest.json?t=" + Date.now(), { cache: "no-store" })
    .then((r) => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then((data) => dispatch({ type: "DATA", data }))
    .catch((e) => dispatch({ type: "ERROR", error: String(e) }));

export const updateState = (event, prev) => {
  if (event.type === "DATA") return { data: event.data, error: null };
  if (event.type === "ERROR") return { ...prev, error: event.error }; // 断网时保留上次内容
  return prev;
};

// 分类：[浅色, 深色, 色块大字]
const CATS = {
  model: ["#0071e3", "#2997ff", "模型"],
  policy: ["#8944ab", "#bf5af2", "政策"],
  product: ["#1a8a4a", "#30d158", "产品"],
  biz: ["#d45a00", "#ff9f0a", "商业"],
  china: ["#d70015", "#ff453a", "中国"],
  research: ["#00809a", "#40c8e0", "研究"],
};
const WK = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
const cat = (c) => CATS[c] || CATS.model;
const longDate = (d) => {
  const dt = new Date(d + "T00:00:00+08:00");
  return `${dt.getMonth() + 1}月${dt.getDate()}日 ${WK[dt.getDay()]}`;
};
const open = () => run(`open "${SITE}"`);

const CSS = `
.dan { --bg:#ffffff; --ink:#1d1d1f; --sub:#6e6e73; --line:#e5e5ea; --shadow:rgba(0,0,0,.12);
  width: 343px; height: 343px; display: flex; flex-direction: column; border-radius: 22px; overflow: hidden;
  background: var(--bg); color: var(--ink); box-shadow: 0 4px 16px var(--shadow); cursor: grab; user-select: none;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  -webkit-font-smoothing: antialiased; }
.dan .k-dark { display: none; }
@media (prefers-color-scheme: dark) {
  .dan { --bg:#1c1c1e; --ink:#f5f5f7; --sub:#98989d; --line:#38383a; --shadow:rgba(0,0,0,.35); }
  .dan .k-light { display: none; }
  .dan .dan-pan.k-dark { display: flex; }
  .dan .dan-dot.k-dark { display: block; } }
.dan-pan { position: relative; height: 100px; padding: 11px 15px 12px; display: flex; flex-direction: column;
  justify-content: space-between; color: #fff; overflow: hidden; }
.dan-pan::before { content: ""; position: absolute; inset: 0;
  background: radial-gradient(120% 90% at 90% 0%, rgba(255,255,255,.3), transparent 60%),
              linear-gradient(160deg, transparent 40%, rgba(0,0,0,.2)); }
.dan-pan > * { position: relative; }
.dan-d { font: 600 11px/1 -apple-system, sans-serif; opacity: .92; }
.dan-k { font: 700 40px/1 -apple-system, "PingFang SC", sans-serif; letter-spacing: .02em; }
.dan-b { flex: 1; min-height: 0; padding: 12px 15px 14px; display: flex; flex-direction: column; gap: 5px; }
.dan-t { flex: none; font: 700 17px/1.32 -apple-system, "PingFang SC", sans-serif; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.dan-s { flex: none; font: 400 13px/1.45 -apple-system, "PingFang SC", sans-serif; color: var(--sub); display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.dan-rows { flex: none; margin-top: auto; padding-top: 9px; border-top: 1px solid var(--line); display: flex;
  flex-direction: column; gap: 7px; }
.dan-row { display: flex; align-items: center; gap: 7px; font: 500 13px/1.25 -apple-system, "PingFang SC", sans-serif; min-width: 0; }
.dan-dot { width: 6px; height: 6px; border-radius: 50%; flex: none; }
.dan-row span:last-child { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.dan-empty { padding: 18px; font: 400 13px/1.5 -apple-system, "PingFang SC", sans-serif; color: var(--sub); }
.dan-empty b { display: block; color: var(--ink); font-size: 14px; margin-bottom: 4px; }
`;

// 分类色随深浅色切换：两份颜色都画出来，用 CSS 显示其中一份
const Dot = ({ c }) => (
  <span style={{ position: "relative", width: 6, height: 6, flex: "none" }}>
    <span className="dan-dot k-light" style={{ position: "absolute", inset: 0, background: cat(c)[0] }} />
    <span className="dan-dot k-dark" style={{ position: "absolute", inset: 0, background: cat(c)[1] }} />
  </span>
);
const Panel = ({ c, children }) => (
  <div style={{ position: "relative", flex: "none" }}>
    {[0, 1].map((i) => (
      <div
        key={i}
        className={"dan-pan " + (i === 0 ? "k-light" : "k-dark")}
        style={{ background: cat(c)[i] }}
      >
        {children}
      </div>
    ))}
  </div>
);

export const render = ({ data, error }) => {
  if (!data || !data.lead) {
    return (
      <div className="dan" onMouseDown={onMouseDown}>
        <style dangerouslySetInnerHTML={{ __html: CSS }} />
        <div className="dan-empty">
          <b>Signal</b>
          {error ? "暂时连不上网站，联网后会自动刷新。" : "正在加载…"}
        </div>
      </div>
    );
  }
  const lead = data.lead;
  return (
    <div className="dan" onMouseDown={onMouseDown} title="点一下打开 Signal，按住可拖动">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <Panel c={lead.cat}>
        <span className="dan-d">{longDate(data.date)}</span>
        <span className="dan-k">{cat(lead.cat)[2]}</span>
      </Panel>
      <div className="dan-b">
        <div className="dan-t">{lead.title}</div>
        {lead.summary ? <div className="dan-s">{lead.summary}</div> : null}
        <div className="dan-rows">
          {(data.items || []).slice(0, 4).map((it, i) => (
            <div className="dan-row" key={i}>
              <Dot c={it.cat} />
              <span>{it.title}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
