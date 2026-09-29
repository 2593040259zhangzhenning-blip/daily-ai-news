// Signal · 桌面小组件（Scriptable）
// 用法：在 Scriptable 里新建脚本，整段粘贴，命名为「每日AI资讯」。
// 然后长按主屏 → 添加小组件 → Scriptable → 选尺寸 → 编辑小组件 → Script 选「每日AI资讯」。
// 小号：头条；中号：头条 + 两条必看；大号：头条 + 一句摘要 + 4 条动态。锁屏也能用。点小组件打开网页。

const SITE = "https://2593040259zhangzhenning-blip.github.io/daily-ai-news/";

// 每个分类：[浅色主屏的颜色, 深色主屏的颜色, 色块上的大字]
const CATS = {
  model:    ["#0071e3", "#2997ff", "模型"],
  policy:   ["#8944ab", "#bf5af2", "政策"],
  product:  ["#1a8a4a", "#30d158", "产品"],
  biz:      ["#d45a00", "#ff9f0a", "商业"],
  china:    ["#d70015", "#ff453a", "中国"],
  research: ["#00809a", "#40c8e0", "研究"],
};
const WK = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
const C = {
  bg:   Color.dynamic(new Color("#ffffff"), new Color("#1c1c1e")),
  ink:  Color.dynamic(new Color("#1d1d1f"), new Color("#f5f5f7")),
  sub:  Color.dynamic(new Color("#6e6e73"), new Color("#98989d")),
  line: Color.dynamic(new Color("#e5e5ea"), new Color("#38383a")),
};
const cat = (c) => CATS[c] || CATS.model;
const catColor = (c) => Color.dynamic(new Color(cat(c)[0]), new Color(cat(c)[1]));

// 把颜色往白色或黑色方向混一点，做色块的渐变
function mix(hex, toward, t) {
  const n = (h) => parseInt(h, 16);
  const a = [n(hex.slice(1, 3)), n(hex.slice(3, 5)), n(hex.slice(5, 7))];
  const b = toward === "white" ? [255, 255, 255] : [0, 0, 0];
  return "#" + a.map((v, i) => Math.round(v + (b[i] - v) * t).toString(16).padStart(2, "0")).join("");
}
function panelGradient(c) {
  const [l, d] = cat(c);
  const g = new LinearGradient();
  g.colors = [
    Color.dynamic(new Color(mix(l, "white", 0.22)), new Color(mix(d, "white", 0.18))),
    Color.dynamic(new Color(l), new Color(d)),
    Color.dynamic(new Color(mix(l, "black", 0.14)), new Color(mix(d, "black", 0.18))),
  ];
  g.locations = [0, 0.55, 1];
  g.startPoint = new Point(1, 0);
  g.endPoint = new Point(0, 1);
  return g;
}

// 取数据：联网失败时用上次缓存
const fm = FileManager.local();
const cachePath = fm.joinPath(fm.cacheDirectory(), "daily-ai-news-latest.json");
async function getData() {
  try {
    const req = new Request(SITE + "data/latest.json?t=" + Date.now());
    req.timeoutInterval = 12;
    const data = await req.loadJSON();
    if (!data || !data.date || !data.lead) throw new Error("empty");
    fm.writeString(cachePath, JSON.stringify(data));
    return data;
  } catch (e) {
    return fm.fileExists(cachePath) ? JSON.parse(fm.readString(cachePath)) : null;
  }
}
function shortDate(d) {
  const dt = new Date(d + "T00:00:00+08:00");
  return `${dt.getMonth() + 1}/${dt.getDate()}`;
}
function longDate(d) {
  const dt = new Date(d + "T00:00:00+08:00");
  return `${dt.getMonth() + 1}月${dt.getDate()}日 ${WK[dt.getDay()]}`;
}

function text(stack, s, font, color, lines) {
  const t = stack.addText(s);
  t.font = font;
  t.textColor = color;
  if (lines) t.lineLimit = lines;
  return t;
}

// 色块：左上角日期，大字分类
function panel(parent, lead, dateLabel, size, bigSize, horizontal) {
  const p = parent.addStack();
  p.size = size;
  p.backgroundGradient = panelGradient(lead.cat);
  p.setPadding(11, 13, 11, 13);
  if (horizontal) {
    p.layoutHorizontally();
    text(p, dateLabel, Font.semiboldSystemFont(11), Color.white());
    p.addSpacer();
    const col = p.addStack();
    col.layoutVertically();
    col.addSpacer();
    text(col, cat(lead.cat)[2], Font.boldSystemFont(bigSize), Color.white());
  } else {
    // 宽度设为 0 时，Scriptable 的 stack 会缩到内容宽度；每一行里加一个弹性空白，让色块撑满整行
    p.layoutVertically();
    const top = p.addStack();
    top.layoutHorizontally();
    text(top, dateLabel, Font.semiboldSystemFont(11), Color.white());
    top.addSpacer();
    p.addSpacer();
    const bottom = p.addStack();
    bottom.layoutHorizontally();
    text(bottom, cat(lead.cat)[2], Font.boldSystemFont(bigSize), Color.white());
    bottom.addSpacer();
  }
  return p;
}

function rows(parent, items, size) {
  // 分隔线同理：用弹性空白把它撑满整行，否则宽度为 0 看不见
  const d = parent.addStack();
  d.size = new Size(0, 1);
  d.layoutHorizontally();
  d.addSpacer();
  d.backgroundColor = C.line;
  parent.addSpacer(8);
  items.forEach((it, i) => {
    const r = parent.addStack();
    r.layoutHorizontally();
    r.centerAlignContent();
    r.spacing = 7;
    const dot = r.addStack();
    dot.size = new Size(6, 6);
    dot.cornerRadius = 3;
    dot.backgroundColor = catColor(it.cat);
    text(r, it.title, Font.mediumSystemFont(size), C.ink, 1);
    if (i < items.length - 1) parent.addSpacer(7);
  });
}

async function build() {
  const data = await getData();
  const fam = config.widgetFamily || "medium";
  const w = new ListWidget();
  w.url = SITE;
  w.refreshAfterDate = new Date(Date.now() + 30 * 60 * 1000);

  // 锁屏
  if (fam === "accessoryInline") {
    w.addText(data ? data.lead.title : "Signal");
    return w;
  }
  if (fam === "accessoryRectangular") {
    text(w, data ? `${shortDate(data.date)} · ${cat(data.lead.cat)[2]}` : "Signal", Font.semiboldSystemFont(11), Color.white());
    text(w, data ? data.lead.title : "暂无内容", Font.systemFont(13), Color.white(), 2);
    return w;
  }
  if (fam === "accessoryCircular") {
    const t = text(w, data ? String(data.count) : "–", Font.boldSystemFont(20), Color.white());
    t.centerAlignText();
    const s = text(w, "条", Font.systemFont(10), Color.white());
    s.centerAlignText();
    return w;
  }

  w.backgroundColor = C.bg;
  w.setPadding(0, 0, 0, 0);

  if (!data) {
    w.setPadding(15, 15, 15, 15);
    text(w, "Signal", Font.semiboldSystemFont(12), C.sub);
    w.addSpacer();
    text(w, "联网后会自动显示今天的内容。", Font.systemFont(13), C.ink);
    w.addSpacer();
    return w;
  }
  const lead = data.lead;
  const musts = data.items.filter((it) => it.tier === "must");

  if (fam === "small") {
    panel(w, lead, shortDate(data.date), new Size(0, 64), 24, true);
    const b = w.addStack();
    b.layoutVertically();
    b.setPadding(9, 13, 12, 13);
    text(b, lead.title, Font.boldSystemFont(14), C.ink, 4);
    w.addSpacer();
    return w;
  }

  if (fam === "medium") {
    const root = w.addStack();
    root.layoutHorizontally();
    panel(root, lead, shortDate(data.date), new Size(118, 0), 30, false);
    const r = root.addStack();
    r.layoutVertically();
    r.setPadding(13, 14, 13, 14);
    text(r, lead.title, Font.boldSystemFont(15), C.ink, 3);
    r.addSpacer();
    rows(r, (musts.length ? musts : data.items).slice(0, 2), 12.5);
    return w;
  }

  // large / extraLarge
  panel(w, lead, longDate(data.date), new Size(0, 118), 40, false);
  const b = w.addStack();
  b.layoutVertically();
  b.setPadding(13, 15, 14, 15);
  text(b, lead.title, Font.boldSystemFont(17), C.ink, 2);
  b.addSpacer(6);
  if (lead.summary) text(b, lead.summary, Font.systemFont(13), C.sub, 2);
  b.addSpacer();
  rows(b, data.items.slice(0, fam === "extraLarge" ? 5 : 4), 13);
  w.addSpacer();
  return w;
}

const widget = await build();
if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentLarge();
}
Script.complete();
