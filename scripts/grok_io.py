#!/usr/bin/env python3
"""Grok Bot 写进仓库的两种文件：读取、校验、检查。

Grok Bot（用户的另一个 AI 助手，xAI 出品，能原生实时读 X）每天跑两个例程，把结果提交到 main：

  data/grok/scout/<北京日期>.json   侦察（每天 06:15 前后）：X 上关注对象的官方账号和关键人物过去 24 小时的帖子，
                                     X 上热议的事，外加 ChatGPT 发布说明（help.openai.com 拦机房 IP，Grok 用真浏览器读）。
                                     早间任务通过 inbox_view.py 读。
  data/grok/review/<北京日期>.json  独立查漏（每天 09:00 前后）：读当天这期，找关注清单里该收没收的大事、已发条目里可疑的事实。
                                     只给周六复盘（weekly_review.py）用，不上网页、早间任务也不读。

这些文件是 Grok 写的，Claude 只当线索和一手链接的来源，不盲信：格式不对的条目直接丢掉，丢了几条会打印出来。

用法：
  python3 scripts/grok_io.py check data/grok/scout/2026-10-30.json     # 校验一个文件（Grok 提交前可以自己跑）
  python3 scripts/grok_io.py check data/grok/review/2026-10-30.json
  python3 scripts/grok_io.py example scout                             # 打印一份格式示例
  python3 scripts/grok_io.py example review
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROK = ROOT / "data" / "grok"
UTC = timezone.utc
BJ = timezone(timedelta(hours=8))

X_STATUS_RE = re.compile(r"^https://(x|twitter)\.com/([A-Za-z0-9_]{1,15})/status/(\d{5,25})")
ACCOUNT_RE = re.compile(r"^@[A-Za-z0-9_]{1,15}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

EXAMPLES = {
    "scout": {
        "date": "2026-10-30",
        "generatedAt": "2026-10-30T06:15:00+08:00",
        "by": "Grok Bot",
        "x": {
            "ok": True,
            "error": None,
            "checked": ["@OpenAI", "@AnthropicAI", "@claudeai"],
            "posts": [
                {"account": "@OpenAI", "official": True, "postedAt": "2026-10-29T18:02:00Z",
                 "url": "https://x.com/OpenAI/status/1234567890123456789",
                 "summary": "用一句中文说清这条帖子宣布了什么（60 字以内，自己的话，不照抄）",
                 "watch": "OpenAI/ChatGPT",
                 "links": ["https://openai.com/index/example"]}
            ],
            "buzz": [
                {"title": "X 上很多人在讨论的一件事，一句中文", "accounts": ["@sama", "@karpathy"],
                 "urls": ["https://x.com/sama/status/1234567890123456780"], "watch": "OpenAI/ChatGPT",
                 "confirmed": False}
            ]
        },
        "chatgptReleaseNotes": {
            "ok": True,
            "error": None,
            "url": "https://help.openai.com/en/articles/6825453-chatgpt-release-notes",
            "entries": [{"date": "2026-10-29", "title": "页面上的原标题", "summary": "一句中文：用户能感觉到什么变化"}]
        }
    },
    "review": {
        "date": "2026-10-30",
        "issue": "2026-10-30-1morning",
        "generatedAt": "2026-10-30T09:00:00+08:00",
        "by": "Grok Bot",
        "ok": True,
        "error": None,
        "missed": [
            {"title": "漏掉的事，一句中文", "why": "为什么按关注清单该收（对象/领域、有几家在报）",
             "watch": "英伟达", "layer": 1, "severity": "高",
             "happenedAt": "2026-10-29", "urls": ["https://nvidianews.nvidia.com/news/example"]}
        ],
        "doubts": [
            {"item": "当期某条的标题（原样）", "problem": "哪里可能不对，一句中文", "urls": ["https://example.com/source"]}
        ]
    },
}


def _s(v, n=None):
    if not isinstance(v, str):
        return None
    v = " ".join(v.split())
    if not v:
        return None
    return v[:n] if n else v


def _url(u):
    return u if isinstance(u, str) and u.startswith(("https://", "http://")) and len(u) < 600 else None


def _urls(v, cap=5):
    return [u for u in (v if isinstance(v, list) else []) if _url(u)][:cap]


def parse_time(s):
    if not isinstance(s, str) or not s.strip():
        return None
    s = s.strip()
    if DATE_RE.match(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=BJ)
        except ValueError:
            return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)
    except ValueError:
        return None


def clean_scout(doc):
    """返回 (清洗后的 scout, 问题列表)。结构坏到读不了时返回 (None, 问题)。"""
    probs = []
    if not isinstance(doc, dict):
        return None, ["顶层不是 JSON 对象"]
    out = {"date": doc.get("date") if DATE_RE.match(str(doc.get("date", ""))) else None,
           "generatedAt": parse_time(doc.get("generatedAt")), "by": _s(doc.get("by"), 40) or "Grok Bot"}
    if not out["date"]:
        probs.append("date 缺失或不是 YYYY-MM-DD")
    if not out["generatedAt"]:
        probs.append("generatedAt 缺失或不是 ISO 时间")

    x = doc.get("x") if isinstance(doc.get("x"), dict) else {}
    xo = {"ok": bool(x.get("ok")), "error": _s(x.get("error"), 200),
          "checked": [a for a in (x.get("checked") or []) if isinstance(a, str) and ACCOUNT_RE.match(a)][:80],
          "posts": [], "buzz": []}
    bad = 0
    for p in x.get("posts") or []:
        if not isinstance(p, dict):
            bad += 1
            continue
        url, acc, summ = _url(p.get("url")), _s(p.get("account"), 16), _s(p.get("summary"), 120)
        m = X_STATUS_RE.match(url or "")
        if not (url and m and acc and ACCOUNT_RE.match(acc) and summ):
            bad += 1
            continue
        if m.group(2).lower() != acc[1:].lower():
            bad += 1                      # 链接里的账号和 account 对不上，多半是编的，丢掉
            continue
        xo["posts"].append({"account": acc, "official": bool(p.get("official")), "postedAt": parse_time(p.get("postedAt")),
                            "url": url.split("?")[0], "summary": summ, "watch": _s(p.get("watch"), 30) or "",
                            "links": _urls(p.get("links"), 3)})
    if bad:
        probs.append("x.posts 丢掉 %d 条（缺字段、链接不是 x.com/<账号>/status/<数字>，或链接账号和 account 对不上）" % bad)
    bad = 0
    for b in x.get("buzz") or []:
        t = _s(b.get("title"), 120) if isinstance(b, dict) else None
        if not t:
            bad += 1
            continue
        xo["buzz"].append({"title": t, "accounts": [a for a in (b.get("accounts") or []) if isinstance(a, str) and ACCOUNT_RE.match(a)][:6],
                           "urls": _urls(b.get("urls"), 3), "watch": _s(b.get("watch"), 30) or "", "confirmed": bool(b.get("confirmed"))})
    if bad:
        probs.append("x.buzz 丢掉 %d 条（缺 title）" % bad)
    if not xo["ok"] and not xo["error"]:
        xo["error"] = "Grok 标记 X 没查成，没写原因"
    out["x"] = xo

    rn = doc.get("chatgptReleaseNotes") if isinstance(doc.get("chatgptReleaseNotes"), dict) else {}
    ro = {"ok": bool(rn.get("ok")), "error": _s(rn.get("error"), 200),
          "url": _url(rn.get("url")) or "https://help.openai.com/en/articles/6825453-chatgpt-release-notes", "entries": []}
    bad = 0
    for e in rn.get("entries") or []:
        if not (isinstance(e, dict) and DATE_RE.match(str(e.get("date", ""))) and _s(e.get("title"))):
            bad += 1
            continue
        ro["entries"].append({"date": e["date"], "title": _s(e["title"], 120), "summary": _s(e.get("summary"), 120) or ""})
    if bad:
        probs.append("chatgptReleaseNotes.entries 丢掉 %d 条（缺 date 或 title）" % bad)
    if not ro["ok"] and not ro["error"]:
        ro["error"] = "Grok 标记没读到，没写原因"
    out["chatgptReleaseNotes"] = ro
    return out, probs


def clean_review(doc):
    probs = []
    if not isinstance(doc, dict):
        return None, ["顶层不是 JSON 对象"]
    out = {"date": doc.get("date") if DATE_RE.match(str(doc.get("date", ""))) else None,
           "issue": _s(doc.get("issue"), 40), "generatedAt": parse_time(doc.get("generatedAt")),
           "ok": bool(doc.get("ok", True)), "error": _s(doc.get("error"), 200), "missed": [], "doubts": []}
    if not out["date"]:
        probs.append("date 缺失或不是 YYYY-MM-DD")
    bad = 0
    for m in doc.get("missed") or []:
        t = _s(m.get("title"), 120) if isinstance(m, dict) else None
        if not (t and _urls(m.get("urls"))):
            bad += 1
            continue
        lay = m.get("layer") if m.get("layer") in (0, 1, 2, 3) else None
        out["missed"].append({"title": t, "why": _s(m.get("why"), 200) or "", "watch": _s(m.get("watch"), 30) or "",
                              "layer": lay, "severity": m.get("severity") if m.get("severity") in ("高", "中") else "中",
                              "happenedAt": _s(m.get("happenedAt"), 30) or "", "urls": _urls(m.get("urls"), 3)})
    if bad:
        probs.append("missed 丢掉 %d 条（缺 title 或没有链接）" % bad)
    bad = 0
    for d in doc.get("doubts") or []:
        it, pb = (_s(d.get("item"), 80), _s(d.get("problem"), 200)) if isinstance(d, dict) else (None, None)
        if not (it and pb):
            bad += 1
            continue
        out["doubts"].append({"item": it, "problem": pb, "urls": _urls(d.get("urls"), 3)})
    if bad:
        probs.append("doubts 丢掉 %d 条（缺 item 或 problem）" % bad)
    return out, probs


def load_file(path, kind):
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, ["文件不存在"]
    except (OSError, json.JSONDecodeError) as e:
        return None, ["读不了或不是合法 JSON：%s" % e]
    return (clean_scout if kind == "scout" else clean_review)(doc)


def latest_scout(now=None, max_age_hours=30, root=GROK):
    """找最近一份侦察文件（今天，没有就昨天），太旧的不要。返回 (scout, 问题列表, 文件路径)。"""
    now = now or datetime.now(UTC)
    for back in (0, 1):
        day = (now.astimezone(BJ) - timedelta(days=back)).strftime("%Y-%m-%d")
        p = root / "scout" / ("%s.json" % day)
        if not p.exists():
            continue
        sc, probs = load_file(p, "scout")
        if sc is None:
            return None, probs, p
        gen = sc.get("generatedAt")
        if gen and (now - gen).total_seconds() > max_age_hours * 3600:
            return None, ["最近一份侦察文件是 %s 写的，已超过 %d 小时" % (gen.astimezone(BJ).strftime("%m-%d %H:%M"), max_age_hours)], p
        return sc, probs, p
    return None, ["没有今天或昨天的侦察文件（Grok 例程可能没跑，或还没提交）"], None


def files_between(kind, since, root=GROK):
    """since（含）以来每天的文件：返回 [(日期, 清洗结果或 None, 问题列表)]，按日期排。"""
    out = []
    for p in sorted((root / kind).glob("*.json")):
        day = p.stem
        if not DATE_RE.match(day):
            continue
        if datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=BJ) < since:
            continue
        doc, probs = load_file(p, kind)
        out.append((day, doc, probs))
    return out


def main(argv):
    if len(argv) >= 2 and argv[0] == "example" and argv[1] in EXAMPLES:
        print(json.dumps(EXAMPLES[argv[1]], ensure_ascii=False, indent=1))
        return 0
    if len(argv) >= 2 and argv[0] == "check":
        p = Path(argv[1])
        kind = "review" if "review" in p.parts else "scout"
        doc, probs = load_file(p, kind)
        if doc is None:
            print("不合格：" + "；".join(probs))
            return 1
        if kind == "scout":
            print("侦察文件可读：X %s，帖子 %d 条、热议 %d 条，查了 %d 个账号；ChatGPT 发布说明 %s，%d 条。" % (
                "成功" if doc["x"]["ok"] else "失败（%s）" % doc["x"]["error"], len(doc["x"]["posts"]), len(doc["x"]["buzz"]),
                len(doc["x"]["checked"]), "成功" if doc["chatgptReleaseNotes"]["ok"] else "失败（%s）" % doc["chatgptReleaseNotes"]["error"],
                len(doc["chatgptReleaseNotes"]["entries"])))
        else:
            print("查漏文件可读：漏报 %d 条、可疑 %d 条。" % (len(doc["missed"]), len(doc["doubts"])))
        if probs:
            print("有问题（已自动丢掉不合格的条目）：" + "；".join(probs))
            return 1
        print("格式全部合格。")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
