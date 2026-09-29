// Signal · 小组件加载器（Scriptable）
// 这段只需要粘贴一次。每次刷新时，它会从网站取最新的小组件代码来运行，
// 以后改小组件的设计，手机和 Mac 上会自动跟着变，不用再重新粘贴。
// 断网时用上次取到的代码。

const CODE_URL = "https://2593040259zhangzhenning-blip.github.io/daily-ai-news/widget/daily-ai-news-widget.js";

const fm = FileManager.local();
const codePath = fm.joinPath(fm.documentsDirectory(), "daily-ai-news-widget-code.js");

let code = null;
try {
  const req = new Request(CODE_URL + "?t=" + Date.now());
  req.timeoutInterval = 10;
  const fetched = await req.loadString();
  if (!fetched.includes("Script.setWidget")) throw new Error("unexpected content");
  fm.writeString(codePath, fetched);
  code = fetched;
} catch (e) {
  if (fm.fileExists(codePath)) code = fm.readString(codePath);
}

if (code) {
  await eval("(async () => {\n" + code + "\n})()");
} else {
  const w = new ListWidget();
  const t = w.addText("Signal：联网后会自动显示");
  t.font = Font.systemFont(13);
  if (config.runsInWidget) Script.setWidget(w);
  else await w.presentMedium();
  Script.complete();
}
