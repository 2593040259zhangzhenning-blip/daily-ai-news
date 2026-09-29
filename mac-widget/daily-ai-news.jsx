// 每日AI资讯 · Mac 桌面小组件（Übersicht）
// 读网站上的同一份数据，设计和手机上的大号小组件一致。每 30 分钟刷新一次。
// 轻点：在默认浏览器里打开网站。按住拖动：移动位置，松手后吸附到系统小组件的网格并记住。
// 网格按这台 Mac 上原生小组件量出：单位 163、间距 17（每格 180），整列离屏幕右边 34。

import { run } from "uebersicht";

const SITE = "https://2593040259zhangzhenning-blip.github.io/daily-ai-news/";

export const refreshFrequency = 30 * 60 * 1000;

// 位置记在本机，拖动后下次启动还在原处
const POS_KEY = "daily-ai-news-pos";
const loadPos = () => {
  try {
    const p = JSON.parse(localStorage.getItem(POS_KEY) || "null");
    if (p && Number.isFinite(p.left) && Number.isFinite(p.top)) return p;
  } catch (e) {}
  return null;
};
// 和原生大号小组件同尺寸，吸附到原生小组件的网格
const SIZE = 343;
const GRID = { pitch: 180, right: 34, top: 127 }; // top 127：天气小组件（487）上方一格
const snap = (left, top) => {
  const W = window.innerWidth;
  const k = Math.max(0, Math.round((W - GRID.right - (left + SIZE)) / GRID.pitch));
  const j = Math.max(0, Math.round((top - GRID.top) / GRID.pitch));
  return { left: W - GRID.right - k * GRID.pitch - SIZE, top: GRID.top + j * GRID.pitch };
};
const saved = loadPos();
const start = saved ? snap(saved.left, saved.top) : null;

export const className = start
  ? `left: ${start.left}px; top: ${start.top}px;`
  : `right: ${GRID.right}px; top: ${GRID.top}px;`;

// 按住移动超过 4 像素算拖动，否则算点击
let dragging = null;
const onMouseDown = (e) => {
  if (e.button !== 0) return;
  const box = e.currentTarget.parentElement; // Übersicht 包在外面、带定位的那一层
  const rect = box.getBoundingClientRect();
  dragging = { box, dx: e.clientX - rect.left, dy: e.clientY - rect.top, x0: e.clientX, y0: e.clientY, moved: false };
  const move = (ev) => {
    if (!dragging) return;
    if (!dragging.moved && Math.hypot(ev.clientX - dragging.x0, ev.clientY - dragging.y0) < 4) return;
    dragging.moved = true;
    const left = Math.max(0, Math.min(window.innerWidth - 60, ev.clientX - dragging.dx));
    const top = Math.max(0, Math.min(window.innerHeight - 60, ev.clientY - dragging.dy));
    Object.assign(dragging.box.style, { left: left + "px", top: top + "px", right: "auto", bottom: "auto" });
  };
  const up = () => {
    window.removeEventListener("mousemove", move);
    window.removeEventListener("mouseup", up);
    const d = dragging;
    dragging = null;
    if (!d) return;
    if (d.moved) {
      const r = d.box.getBoundingClientRect();
      const p = snap(r.left, r.top);
      d.box.style.transition = "left .18s ease, top .18s ease";
      Object.assign(d.box.style, { left: p.left + "px", top: p.top + "px" });
      setTimeout(() => { d.box.style.transition = ""; }, 220);
      try { localStorage.setItem(POS_KEY, JSON.stringify(p)); } catch (err) {}
    } else {
      open();
    }
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
          <b>每日AI资讯</b>
          {error ? "暂时连不上网站，联网后会自动刷新。" : "正在加载…"}
        </div>
      </div>
    );
  }
  const lead = data.lead;
  return (
    <div className="dan" onMouseDown={onMouseDown} title="点一下打开每日AI资讯，按住可拖动">
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
