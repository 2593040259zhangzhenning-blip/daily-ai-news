#!/usr/bin/env python3
"""每周信源复盘：读事件日志（data/inbox/events-log.json）、抓取状态和本周已发布的期数，写成 Markdown。

用法：
  python3 scripts/weekly_review.py                 # 打印到屏幕
  python3 scripts/weekly_review.py --write         # 同时写到 data/reviews/<年>-W<周>.md（每周六由 Actions 跑）
  python3 scripts/weekly_review.py --days 7

写了三块：
  1. 信源体检：失败的、解析到的最新一条已经很旧的、这一周一条新内容都没出过的源。
  2. 共识高但 Signal 没收的事件：程序判断，按规则本来就不收的（融资/人事/股价、国内）单列。判断「收没收」是用链接和关键词对的，
     可能有漏判，列出来是让你核对，不是结论。
  3. 建议关注：没在关注清单里、但在高共识事件里反复出现的名字，每条附一个例子。「为什么你可能会在意」留给读这份报告的 Claude 写。
  4. Grok 独立查漏（2026-10-30 起）：Grok Bot 每天 09:00 前后读当天这期写的 data/grok/review/<日期>.json——它认为该收没收的、
     已发条目里可疑的事实；外加 Grok 每天侦察文件（data/grok/scout/）到没到、X 和 ChatGPT 发布说明查没查成。
     这是另一个模型的看法，不是结论：读报告的 Claude 要逐条按 watchlist.md 判断是真漏、取舍，还是 Grok 判断错了。
信源体检里另有「抓取节奏」：一周里收件箱实际抓了几次、最长隔了多久（data/inbox/state.json 的 runs）。
关注 ≠ 喜欢：加不加由用户决定，系统不根据点击行为自动调整。
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inbox_config as C  # noqa: E402
import grok_io as G  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UTC = timezone.utc
BJ = timezone(timedelta(hours=8))

NAME_STOP = set("""The This That These Those There Their They Its And For With From Into Over Under After Before About
Why How What When Where Who Which Will Would Could Should May Might Can Does Did Has Have Had Are Was Were Not Now New Just More Most
One Two Three Four Five First Last Next Top Best Here Report Reports Says Said Say Sources Source Watch Video Opinion Analysis Update
Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April June July August September October November December
Jan Feb Mar Apr Jun Jul Aug Sep Sept Oct Nov Dec Inc Corp Ltd Group Company Companies Market Markets Stock Stocks Shares Share Deal Deals
Big Why Is Are Of In On At By As To Up Out Off Our Your His Her You We He She It If Or But So No Yes Q1 Q2 Q3 Q4 Update Updates
US UK EU AI CEO IPO USD GPU GPUs Today Tonight Week Year Years Day Days Time Plans Plan Launches Launch Unveils Adds Gets Takes Makes
Says Sues Wins Hits Beats Faces Could Tests Test Ahead Amid Over Than Then Also Still Even Only Many Some Every Each Other Another
Open Billion Million Trillion Duo Trump Biden White House Court Judge Senate Congress Federal State States American America China Chinese
Europe European Japan India Korea London York California Texas Washington Partnerships Elon Reuters Bloomberg Report Exclusive Breaking
Announces Announced Reportedly Reveals Introduces Brings Gets Turns Pulls Adds Sets Plans Wants Needs Says Seeks Eyes Nears Raises
""".split())


def pdt(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def latin_tokens(text):
    return {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9.\-]{3,}", text or "")} - {w.lower() for w in NAME_STOP}


def published_week(since):
    """本周已发布的期：返回 [(日期, 标题, 全文, 出处链接集合)]。"""
    out = []
    for f in sorted((ROOT / "data" / "issues").glob("*.json")):
        d = load(f, {})
        day = d.get("date", "")
        try:
            if datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=BJ) < since - timedelta(days=1):
                continue
        except ValueError:
            continue
        for it in d.get("items", []):
            text = " ".join([it.get("title", ""), it.get("body", ""), it.get("summary", "")])
            out.append((day, it.get("title", ""), text, {s.get("url", "").split("#")[0].rstrip("/") for s in it.get("sources", [])}))
    return out


def covered(ev, pubs):
    urls = {u.split("#")[0].rstrip("/") for u in ev.get("urls", [])}
    urls |= {u.split("#")[0].rstrip("/") for _, u in ev.get("primaryLinks", [])}
    toks = latin_tokens(ev["title"])
    best = None
    for day, title, text, pu in pubs:
        if urls & pu:
            return day, title
        shared = toks & latin_tokens(text)
        if len(shared) >= 3 or (toks and len(shared) >= 2 and len(shared) / len(toks) >= 0.5):
            best = best or (day, title)
    return best


def names_in(title):
    """标题里的专有名词（大写开头的词或连续的大写词组）。"""
    out = []
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9&.\-]{2,}(?:\s+[A-Z][A-Za-z0-9&.\-]{2,}){0,2})", title or ""):
        ph = m.group(1)
        words = [w for w in ph.split() if w not in NAME_STOP]
        if words:
            out.append(" ".join(words))
    return out


def known_names():
    pats = [rx for _, rx in C.WATCH_RULES] + [rx for _, rx in C.TOPIC_RULES]
    return pats


def build(days=7):
    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    status = load(ROOT / "data" / "inbox" / "source-status.json", {})
    log = load(ROOT / "data" / "inbox" / "events-log.json", {})
    evs = [e for e in log.get("events", []) if (pdt(e.get("first")) or since) >= since or (pdt(e.get("last")) or since) >= since]
    pubs = published_week(since.astimezone(BJ))
    L = []
    wk = now.astimezone(BJ).isocalendar()
    L.append("# Signal 信源复盘 · %d 年第 %d 周" % (wk[0], wk[1]))
    L.append("")
    L.append("统计范围：最近 %d 天（到北京时间 %s）；本周发布 %d 条新闻，事件日志里有 %d 个共识中档以上的事件。" % (
        days, now.astimezone(BJ).strftime("%m-%d %H:%M"), len(pubs), len(evs)))
    L.append("")

    # 1. 信源体检
    L.append("## 一、信源体检")
    L.append("")
    srcs = status.get("sources", [])
    bad = [s for s in srcs if not s.get("ok")]
    stale = [s for s in srcs if s.get("ok") and s.get("stale")]
    silent = []
    for s in srcs:
        ln = pdt(s.get("lastNewAt"))
        if s.get("ok") and not s.get("stale") and (ln is None or ln < since) and not s["id"].startswith("gn-"):
            silent.append(s)
    L.append("共 %d 个源，当前成功 %d 个。" % (len(srcs), len(srcs) - len(bad)))
    runs = sorted(t for t in (pdt(r) for r in load(ROOT / "data" / "inbox" / "state.json", {}).get("runs", [])) if t and t >= since)
    if len(runs) >= 2:
        gaps = [(b - a).total_seconds() / 3600 for a, b in zip(runs, runs[1:])]
        worst = max(gaps)
        L.append("")
        L.append("抓取节奏：这 %d 天收件箱实际抓了 %d 次（按计划约 %d 次），最长隔了 %.1f 小时%s。" % (
            days, len(runs), days * 24, worst,
            "，GitHub 定时触发明显掉队（早间任务开跑时会自己现抓，不影响当期，但白天的事件日志会稀）" if worst >= 3 else ""))
    if bad:
        L.append("")
        L.append("**现在抓取失败的：**")
        for s in bad:
            L.append("- %s：连续失败 %d 次，上次成功 %s；%s" % (s["name"], s.get("failStreak", 0), s.get("lastOkAt") or "从未", s.get("error") or ""))
    if stale:
        L.append("")
        L.append("**抓取成功但最新一条已经很旧的（要么源没更新，要么解析出了问题）：**")
        for s in stale:
            L.append("- %s：%s" % (s["name"], s["stale"]))
    if silent:
        L.append("")
        L.append("**这一周没有出过一条新内容的（官方页面本来更新慢的可以忽略，其余要查）：**")
        L.append("- " + "、".join(s["name"] for s in silent))
    dropped = sum(s.get("dropped", 0) for s in srcs)
    if dropped:
        L.append("")
        L.append("谷歌新闻最近一次抓取里，过滤掉了 %d 条股价、财经转载。" % dropped)
    L.append("")

    # 2. 没收的高共识事件
    L.append("## 二、共识高但 Signal 没收的事件")
    L.append("")
    hi = [e for e in evs if e.get("maxScore", 0) >= 9 and (pdt(e.get("first")) or since) >= since]
    hi.sort(key=lambda e: -e["maxScore"])
    missed, by_rule = [], []
    for e in hi:
        if covered(e, pubs):
            continue
        (by_rule if ({"money_people", "domestic"} & set(e.get("flags", []))) else missed).append(e)
    L.append("高共识（得分 9 以上）的事件 %d 个，其中判断已收 %d 个。" % (len(hi), len(hi) - len(missed) - len(by_rule)))
    L.append("")
    if missed:
        L.append("**可能漏了，请核对（%d 个）：**" % len(missed))
        L.append("（只列得分最高的 12 个；Signal 一天只收 4–7 条，高共识事件没收大多是取舍，不一定是漏。）")
        for e in missed[:12]:
            tags = "、".join(e.get("watch", []) + e.get("topics", [])) or "清单外"
            L.append("- [%s] %s · %d 家在报%s · %s" % ((pdt(e["first"]).astimezone(BJ).strftime("%m-%d") if pdt(e.get("first")) else "?"),
                     tags, e.get("maxOutlets", 0), "（官方已发）" if e.get("official") else "", e["title"]))
    else:
        L.append("没有发现明显漏掉的。")
    if by_rule:
        L.append("")
        L.append("**按规则本来就不收的（融资/人事/股价、国内非突破）：** %d 个，例如：" % len(by_rule))
        for e in by_rule[:5]:
            L.append("- %s" % e["title"])
    L.append("")

    # 3. 建议关注
    L.append("## 三、建议关注（不在清单里，但在高共识事件里反复出现）")
    L.append("")
    pats = known_names()
    cnt, example, where = Counter(), {}, defaultdict(set)
    for e in evs:
        if e.get("maxScore", 0) < 5:
            continue
        for nm in set(names_in(e["title"])):
            if any(p.search(nm) for p in pats) or len(nm) < 3:
                continue
            cnt[nm] += 1
            example.setdefault(nm, e["title"])
            where[nm].update(e.get("watch", []) + e.get("topics", []))
    sugg = [(nm, n) for nm, n in cnt.most_common(40) if n >= 3][:10]
    if sugg:
        L.append("| 名字 | 出现的事件数 | 常和谁一起出现 | 例子 |")
        L.append("|---|---|---|---|")
        for nm, n in sugg:
            L.append("| %s | %d | %s | %s |" % (nm, n, "、".join(sorted(where[nm])[:3]) or "—", example[nm][:70].replace("|", "/")))
        L.append("")
        L.append("加不加由你决定；不加的以后仍可通过「圈外位」进来。")
    else:
        L.append("这周没有名字反复出现 3 次以上的。")
    L.append("")
    # 4. Grok 独立查漏
    L.append("## 四、Grok 独立查漏（另一个模型的看法，逐条核对，不是结论）")
    L.append("")
    since_bj = since.astimezone(BJ).replace(hour=0, minute=0, second=0)
    scouts = G.files_between("scout", since_bj)
    reviews = G.files_between("review", since_bj)
    day_list = [(since_bj + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days + 1)]
    day_list = [d for d in day_list if d <= now.astimezone(BJ).strftime("%Y-%m-%d")]
    sc_by = {d: (doc, pr) for d, doc, pr in scouts}
    rv_by = {d: (doc, pr) for d, doc, pr in reviews}
    no_sc = [d[5:] for d in day_list if d not in sc_by or sc_by[d][0] is None]
    x_fail = [d[5:] for d, (doc, _) in sc_by.items() if doc and not doc["x"]["ok"]]
    rn_fail = [d[5:] for d, (doc, _) in sc_by.items() if doc and not doc["chatgptReleaseNotes"]["ok"]]
    no_rv = [d[5:] for d in day_list if d not in rv_by or rv_by[d][0] is None]
    if not scouts and not reviews:
        L.append("这段时间 Grok 一个文件都没写（例程没开，或还没接上仓库）。")
    else:
        L.append("侦察：%d 天里到了 %d 份%s%s%s。" % (
            len(day_list), len(day_list) - len(no_sc), ("；缺 " + "、".join(no_sc)) if no_sc else "",
            ("；X 没查成 " + "、".join(x_fail)) if x_fail else "", ("；ChatGPT 发布说明没读到 " + "、".join(rn_fail)) if rn_fail else ""))
        L.append("查漏：到了 %d 份%s。" % (len(day_list) - len(no_rv), ("；缺 " + "、".join(no_rv)) if no_rv else ""))
        probs = ["%s %s：%s" % (k, d[5:], "；".join(pr)) for k, lst in (("侦察", scouts), ("查漏", reviews)) for d, _, pr in lst if pr]
        if probs:
            L.append("格式问题（不合格的条目已丢掉）：" + " / ".join(probs[:6]))
        L.append("")
        missed = [(d, m) for d, (doc, _) in sorted(rv_by.items()) if doc for m in doc["missed"]]
        doubts = [(d, x) for d, (doc, _) in sorted(rv_by.items()) if doc for x in doc["doubts"]]
        if missed:
            L.append("**Grok 认为该收没收的（%d 条，高的在前）：**" % len(missed))
            for d, m in sorted(missed, key=lambda t: (t[1]["severity"] != "高", t[0])):
                L.append("- [%s · %s] %s%s——%s %s" % (d[5:], m["severity"], ("%s · " % m["watch"]) if m["watch"] else "",
                         m["title"], m["why"], " ".join(m["urls"][:2])))
        else:
            L.append("Grok 这周没报漏。")
        if doubts:
            L.append("")
            L.append("**Grok 觉得已发条目里可疑的（%d 条）：**" % len(doubts))
            for d, x in doubts:
                L.append("- [%s] 「%s」：%s %s" % (d[5:], x["item"], x["problem"], " ".join(x["urls"][:2])))
    L.append("")
    return "\n".join(L), wk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    text, wk = build(args.days)
    print(text)
    if args.write:
        d = ROOT / "data" / "reviews"
        d.mkdir(parents=True, exist_ok=True)
        (d / ("%d-W%02d.md" % (wk[0], wk[1]))).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
