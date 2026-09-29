// 每日AI资讯 · Mac 桌面小组件（Übersicht）
// 读网站上的同一份数据，设计和手机上的大号小组件一致。点击任意位置在默认浏览器里打开网站。
// 位置：改下面 className 里的 top / right（或 left / bottom）。每 30 分钟刷新一次。

import { run } from "uebersicht";

const SITE = "https://2593040259zhangzhenning-blip.github.io/daily-ai-news/";

export const refreshFrequency = 30 * 60 * 1000;

export const className = `
  top: 64px;
  right: 40px;
`;

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
.dan { --bg:#ffffff; --ink:#1d1d1f; --sub:#6e6e73; --line:#e5e5ea; --shadow:rgba(0,0,0,.18);
  width: 338px; border-radius: 22px; overflow: hidden; background: var(--bg); color: var(--ink);
  box-shadow: 0 10px 30px var(--shadow); cursor: pointer; user-select: none;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  -webkit-font-smoothing: antialiased; }
.dan .k-dark { display: none; }
@media (prefers-color-scheme: dark) {
  .dan { --bg:#1c1c1e; --ink:#f5f5f7; --sub:#98989d; --line:#38383a; --shadow:rgba(0,0,0,.45); }
  .dan .k-light { display: none; }
  .dan .dan-pan.k-dark { display: flex; }
  .dan .dan-dot.k-dark { display: block; } }
.dan-pan { position: relative; height: 118px; padding: 11px 15px 12px; display: flex; flex-direction: column;
  justify-content: space-between; color: #fff; overflow: hidden; }
.dan-pan::before { content: ""; position: absolute; inset: 0;
  background: radial-gradient(120% 90% at 90% 0%, rgba(255,255,255,.3), transparent 60%),
              linear-gradient(160deg, transparent 40%, rgba(0,0,0,.2)); }
.dan-pan > * { position: relative; }
.dan-d { font: 600 11px/1 -apple-system, sans-serif; opacity: .92; }
.dan-k { font: 700 40px/1 -apple-system, "PingFang SC", sans-serif; letter-spacing: .02em; }
.dan-b { padding: 13px 15px 15px; display: flex; flex-direction: column; gap: 6px; }
.dan-t { font: 700 17px/1.32 -apple-system, "PingFang SC", sans-serif; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.dan-s { font: 400 13px/1.45 -apple-system, "PingFang SC", sans-serif; color: var(--sub); display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.dan-rows { margin-top: 8px; padding-top: 10px; border-top: 1px solid var(--line); display: flex;
  flex-direction: column; gap: 8px; }
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
  <div style={{ position: "relative" }}>
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
      <div className="dan" onClick={open}>
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
    <div className="dan" onClick={open} title="打开每日AI资讯">
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
