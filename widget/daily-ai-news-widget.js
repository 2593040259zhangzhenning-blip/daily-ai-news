// 每日AI资讯 · 桌面小组件（Scriptable）
// 用法：在 Scriptable 里新建脚本，整段粘贴，命名为「每日AI资讯」。
// 然后长按主屏 → 添加小组件 → Scriptable → 选尺寸 → 编辑小组件 → Script 选「每日AI资讯」。
// 支持：小 / 中 / 大，以及锁屏的矩形和单行。点小组件打开网页。

const SITE = "https://2593040259zhangzhenning-blip.github.io/daily-ai-news/";

const CATS = {
  model:    ["#0071e3", "#2997ff"],
  policy:   ["#8944ab", "#bf5af2"],
  product:  ["#1a8a4a", "#30d158"],
  biz:      ["#d45a00", "#ff9f0a"],
  china:    ["#d70015", "#ff453a"],
  research: ["#00809a", "#40c8e0"],
};
const ED = { weekly: "周回顾", morning: "早刊", evening: "晚间增刊" };
const C = {
  bg:  Color.dynamic(new Color("#ffffff"), new Color("#1c1c1e")),
  ink: Color.dynamic(new Color("#1d1d1f"), new Color("#f5f5f7")),
  sub: Color.dynamic(new Color("#6e6e73"), new Color("#98989d")),
};
const catColor = (c) => {
  const x = CATS[c] || CATS.model;
  return Color.dynamic(new Color(x[0]), new Color(x[1]));
};

// 取数据：联网失败时用上次缓存
const fm = FileManager.local();
const cachePath = fm.joinPath(fm.cacheDirectory(), "daily-ai-news-latest.json");
async function getData() {
  try {
    const req = new Request(SITE + "data/latest.json?t=" + Date.now());
    req.timeoutInterval = 12;
    const data = await req.loadJSON();
    if (!data || !data.date) throw new Error("empty");
    fm.writeString(cachePath, JSON.stringify(data));
    return data;
  } catch (e) {
    return fm.fileExists(cachePath) ? JSON.parse(fm.readString(cachePath)) : null;
  }
}

function dayLine(data) {
  const dt = new Date(data.date + "T00:00:00+08:00");
  return `${dt.getMonth() + 1}月${dt.getDate()}日 · ${ED[data.edition] || "简报"}`;
}

function addLine(w, text, font, color) {
  const t = w.addText(text);
  t.font = font;
  t.textColor = color;
  return t;
}

function itemRow(w, it, size, lines) {
  const row = w.addStack();
  row.layoutHorizontally();
  row.topAlignContent();
  row.spacing = 7;
  const dotWrap = row.addStack();
  dotWrap.layoutVertically();
  dotWrap.addSpacer(size * 0.42);
  const dot = dotWrap.addStack();
  dot.size = new Size(6, 6);
  dot.cornerRadius = 3;
  dot.backgroundColor = catColor(it.cat);
  const t = row.addText(it.title);
  t.font = it.tier === "lead" ? Font.semiboldSystemFont(size) : Font.mediumSystemFont(size);
  t.textColor = C.ink;
  t.lineLimit = lines;
}

async function build() {
  const data = await getData();
  const fam = config.widgetFamily || "medium";
  const w = new ListWidget();
  w.url = SITE;
  w.refreshAfterDate = new Date(Date.now() + 30 * 60 * 1000);

  if (fam === "accessoryInline") {
    w.addText(data ? data.headline : "每日AI资讯");
    return w;
  }
  if (fam === "accessoryRectangular") {
    addLine(w, data ? dayLine(data) : "每日AI资讯", Font.semiboldSystemFont(11), Color.white());
    const b = addLine(w, data ? data.headline : "暂无内容", Font.systemFont(13), Color.white());
    b.lineLimit = 2;
    return w;
  }
  if (fam === "accessoryCircular") {
    const t = addLine(w, data ? String(data.items.length) : "–", Font.boldSystemFont(20), Color.white());
    t.centerAlignText();
    const s = addLine(w, "必看", Font.systemFont(10), Color.white());
    s.centerAlignText();
    return w;
  }

  w.backgroundColor = C.bg;
  w.setPadding(15, 15, 15, 15);

  if (!data) {
    addLine(w, "每日AI资讯", Font.semiboldSystemFont(12), C.sub);
    w.addSpacer();
    addLine(w, "联网后会自动显示今天的内容。", Font.systemFont(13), C.ink);
    w.addSpacer();
    return w;
  }

  addLine(w, dayLine(data), Font.semiboldSystemFont(11), C.sub);

  if (fam === "small") {
    w.addSpacer(6);
    const hl = addLine(w, data.headline, Font.boldSystemFont(16), C.ink);
    hl.lineLimit = 5;
    w.addSpacer();
    const dots = w.addStack();
    dots.spacing = 5;
    for (const it of data.items) {
      const d = dots.addStack();
      d.size = new Size(7, 7);
      d.cornerRadius = 3.5;
      d.backgroundColor = catColor(it.cat);
    }
    return w;
  }

  if (fam === "medium") {
    w.addSpacer(12);
    for (const it of data.items.slice(0, 3)) {
      itemRow(w, it, 13.5, 1);
      w.addSpacer(10);
    }
    w.addSpacer();
    return w;
  }

  // large / extraLarge
  w.addSpacer(8);
  const hl = addLine(w, data.headline, Font.boldSystemFont(18), C.ink);
  hl.lineLimit = 2;
  w.addSpacer(14);
  for (const it of data.items.slice(0, fam === "extraLarge" ? 6 : 5)) {
    itemRow(w, it, 14, 2);
    w.addSpacer(10);
  }
  w.addSpacer();
  return w;
}

const widget = await build();
if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentMedium();
}
Script.complete();
