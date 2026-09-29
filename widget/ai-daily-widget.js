// AI 每日情报 · 桌面小组件（Scriptable）
// 用法：在 Scriptable 里新建脚本，整段粘贴，命名为「AI 每日情报」。
// 然后长按主屏 → 添加小组件 → Scriptable → 选尺寸 → 编辑小组件 → Script 选「AI 每日情报」。
// 支持：小 / 中 / 大，以及锁屏的矩形和单行小组件。点小组件打开网页。

const SITE = "https://2593040259zhangzhenning-blip.github.io/ai-daily/";

const CATS = {
  model:    ["模型", "#2446d8", "#7d97ff"],
  policy:   ["政策", "#8a3ffc", "#b794ff"],
  product:  ["产品", "#0f8a6a", "#34d3a6"],
  biz:      ["商业", "#b45309", "#f5b454"],
  china:    ["中国", "#c0262d", "#ff7a7f"],
  research: ["研究", "#0e7490", "#4fc9e0"],
};
const ED = { weekly: "周回顾", morning: "早刊", evening: "晚间增刊" };

const C = {
  bg:    Color.dynamic(new Color("#ffffff"), new Color("#161b24")),
  ink:   Color.dynamic(new Color("#131821"), new Color("#e7ebf2")),
  muted: Color.dynamic(new Color("#5b6475"), new Color("#98a2b3")),
  hot:   Color.dynamic(new Color("#c2410c"), new Color("#fb923c")),
};
const catColor = (c) => {
  const x = CATS[c];
  return x ? Color.dynamic(new Color(x[1]), new Color(x[2])) : C.muted;
};

// —— 取数据：联网失败时用上次缓存 ——
const fm = FileManager.local();
const cachePath = fm.joinPath(fm.cacheDirectory(), "ai-daily-latest.json");
async function getData() {
  try {
    const req = new Request(SITE + "data/latest.json?t=" + Date.now());
    req.timeoutInterval = 12;
    const data = await req.loadJSON();
    if (!data || !data.date) throw new Error("empty");
    fm.writeString(cachePath, JSON.stringify(data));
    return { data, stale: false };
  } catch (e) {
    if (fm.fileExists(cachePath)) return { data: JSON.parse(fm.readString(cachePath)), stale: true };
    return { data: null, stale: true };
  }
}

function dateLabel(d) {
  const dt = new Date(d + "T00:00:00+08:00");
  const wk = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][dt.getDay()];
  return `${dt.getMonth() + 1}/${dt.getDate()} ${wk}`;
}
function timeLabel(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const f = new DateFormatter(); f.dateFormat = "HH:mm";
  return f.string(d);
}

function header(w, data, stale, compact) {
  const top = w.addStack(); top.centerAlignContent();
  const t = top.addText(compact ? "AI 情报" : "AI 每日情报");
  t.font = Font.heavySystemFont(compact ? 13 : 14); t.textColor = C.ink;
  top.addSpacer();
  const meta = top.addText(`${ED[data.edition] || ""} ${timeLabel(data.updatedAt)}${stale ? " · 离线" : ""}`);
  meta.font = Font.mediumMonospacedSystemFont(10); meta.textColor = stale ? C.hot : C.muted;
}

function itemRow(w, it, size, lines) {
  const row = w.addStack(); row.layoutHorizontally(); row.topAlignContent(); row.spacing = 6;
  const dotWrap = row.addStack(); dotWrap.layoutVertically(); dotWrap.addSpacer(size * 0.38);
  const dot = dotWrap.addStack(); dot.size = new Size(6, 6); dot.cornerRadius = 3;
  dot.backgroundColor = it.must ? C.hot : catColor(it.cat);
  const tx = row.addText(it.title);
  tx.font = it.must ? Font.semiboldSystemFont(size) : Font.systemFont(size);
  tx.textColor = C.ink; tx.lineLimit = lines;
}

async function build() {
  const { data, stale } = await getData();
  const fam = config.widgetFamily || "large";
  const w = new ListWidget();
  w.url = SITE;
  w.refreshAfterDate = new Date(Date.now() + 30 * 60 * 1000);

  // 锁屏：单行
  if (fam === "accessoryInline") {
    w.addText(data ? `AI · ${data.headline}` : "AI 情报 · 暂无数据");
    return w;
  }
  // 锁屏：矩形
  if (fam === "accessoryRectangular") {
    const t = w.addText(data ? `${ED[data.edition] || "AI"} · ${dateLabel(data.date)}` : "AI 情报");
    t.font = Font.semiboldSystemFont(11);
    const b = w.addText(data ? data.headline : "暂无数据");
    b.font = Font.systemFont(13); b.lineLimit = 2;
    return w;
  }
  if (fam === "accessoryCircular") {
    const t = w.addText(data ? String(data.count) : "–"); t.font = Font.boldSystemFont(18); t.centerAlignText();
    const s = w.addText("条"); s.font = Font.systemFont(10); s.centerAlignText();
    return w;
  }

  w.backgroundColor = C.bg;
  w.setPadding(14, 14, 14, 14);

  if (!data) {
    header(w, { edition: "", updatedAt: null }, true, fam === "small");
    w.addSpacer();
    const t = w.addText("还没拿到简报，联网后会自动刷新。");
    t.font = Font.systemFont(12); t.textColor = C.muted;
    w.addSpacer();
    return w;
  }

  if (fam === "small") {
    header(w, data, stale, true);
    w.addSpacer(6);
    const d = w.addText(dateLabel(data.date)); d.font = Font.mediumMonospacedSystemFont(11); d.textColor = C.muted;
    w.addSpacer(4);
    const h = w.addText(data.headline); h.font = Font.boldSystemFont(15); h.textColor = C.ink; h.lineLimit = 4;
    w.addSpacer();
    const mustN = data.items.filter((x) => x.must).length;
    const f = w.addText(`必看 ${mustN} · 共 ${data.count} 条`); f.font = Font.mediumSystemFont(11); f.textColor = C.hot;
    return w;
  }

  header(w, data, stale, false);
  w.addSpacer(fam === "medium" ? 6 : 8);

  if (fam === "medium") {
    for (const it of data.items.slice(0, 3)) { itemRow(w, it, 13, 1); w.addSpacer(5); }
    w.addSpacer();
    const f = w.addText(`${dateLabel(data.date)} · 共 ${data.count} 条`); f.font = Font.systemFont(10); f.textColor = C.muted;
    return w;
  }

  // large / extraLarge
  const h = w.addText(data.headline); h.font = Font.boldSystemFont(17); h.textColor = C.ink; h.lineLimit = 2;
  w.addSpacer(10);
  const n = fam === "extraLarge" ? 8 : 6;
  for (const it of data.items.slice(0, n)) { itemRow(w, it, 13, 2); w.addSpacer(7); }
  w.addSpacer();
  const f = w.addText(`${dateLabel(data.date)} · 共 ${data.count} 条 · 点开看全文`); f.font = Font.systemFont(10); f.textColor = C.muted;
  return w;
}

const widget = await build();
if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentLarge();
}
Script.complete();
