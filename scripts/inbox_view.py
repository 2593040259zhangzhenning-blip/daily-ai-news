#!/usr/bin/env python3
"""把收件箱（data/inbox/items.json）打印成给定时任务读的精简清单。

用法：
  python3 scripts/inbox_view.py                  # 最近 30 小时，按关注清单分组
  python3 scripts/inbox_view.py --hours 52       # 补做早间时放宽时间范围
  python3 scripts/inbox_view.py --all            # 连「清单外」和每组的全部线索都列出来
  python3 scripts/inbox_view.py --urls           # 线索类条目也带链接（Google 新闻是跳转地址，一般不需要）
  python3 scripts/inbox_view.py --status         # 只看各个源的抓取状态
  python3 scripts/inbox_view.py --checked        # 本次成功读取的来源名（直接抄进 scan.checked）
  python3 scripts/inbox_view.py --json           # 输出筛选后的原始 JSON

读法：
  [一手] 链接就是原文，可以当出处（再按 sources.md 判断层级）。
  [线索] 聚合站、中转站、Google 新闻、个人 X 账号：只用来发现事件，出处必须回到原文。
  时间前面的 ~ 表示来源没给发布时间，用的是「收件箱第一次发现它的时间」。
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inbox_config as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox"
UTC = timezone.utc
BJ = timezone(timedelta(hours=8))
STALE_HOURS = 3

LAYER1_ORDER = ["Anthropic/Claude", "OpenAI/ChatGPT", "Google/Gemini", "Meta/Muse", "英伟达", "苹果", "SpaceX",
                "AI与教育", "留学与签证政策", "英语教学与语言培训行业"]
RADAR_ORDER = ["AI全行业", "人形机器人", "芯片", "自动驾驶", "脑机接口"]


def pdt(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def when(it):
    t = pdt(it.get("publishedAt"))
    approx = ""
    if not t:
        t, approx = pdt(it.get("firstSeen")), "~"
    return t, approx


def fmt_time(t, approx="", date_only=False):
    if not t:
        return "时间不明"
    if date_only:
        return "%s（仅日期）" % t.strftime("%m-%d")      # 来源只给了日期，不显示时刻
    return "%s%s" % (approx, t.astimezone(BJ).strftime("%m-%d %H:%M"))


def flags_text(it):
    out = []
    if "rumor" in it.get("flags", []):
        out.append("传闻类来源")
    if "money_people" in it.get("flags", []):
        out.append("融资/人事/股价")
    if "domestic" in it.get("flags", []):
        out.append("国内")
    return "【%s】" % "、".join(out) if out else ""


def line(it, urls):
    PRINTED[0] += 1
    t, approx = when(it)
    kind = "一手" if it.get("role") == "primary" else "线索"
    src = it["sourceName"]
    if it.get("origin") and it["source"].startswith(("gn-", "hn", "ai-news-radar", "follow", "techmeme", "hf-papers")):
        src = "%s（经 %s）" % (it["origin"], it["sourceName"].split("：")[0])
    s = "[%s] %s · T%s · %s%s · %s" % (kind, fmt_time(t, approx, it.get("dateOnly", False)), it.get("tier", "?"),
                                      flags_text(it), src, it["title"])
    if it.get("eventAt"):
        ev = pdt(it["eventAt"])
        s += "（事件时间 %s）" % fmt_time(ev)
    if it.get("meta", {}).get("points"):
        s += "（HN %s 分）" % it["meta"]["points"]
    if urls or it.get("role") == "primary":
        s += "\n    " + it["url"]
    return s


_SEEN_LEADS = set()
PRINTED = [0]          # 实际打印出来的候选条数，scan.candidates 从这里起算


def show_group(title, items, args, lead_cap=10, rumor_cap=8):
    prim = [i for i in items if i.get("role") == "primary" and "rumor" not in i.get("flags", [])]
    rumor = [i for i in items if i.get("role") == "primary" and "rumor" in i.get("flags", [])]
    lead = []
    for i in items:
        if i.get("role") == "primary":
            continue
        key = " ".join(i["title"].lower().split())[:80]
        if key in _SEEN_LEADS:
            continue                      # 同一标题被多个关键词搜索重复搜到
        _SEEN_LEADS.add(key)
        lead.append(i)
    print("### %s（一手 %d 条 · 传闻类 %d 条 · 线索 %d 条）" % (title, len(prim), len(rumor), len(lead)))
    for i in prim:
        print(line(i, args.urls))
    r_shown = rumor if args.all else rumor[:rumor_cap]
    for i in r_shown:
        print(line(i, args.urls))
    if len(rumor) > len(r_shown):
        print("  …另有 %d 条传闻类（--all 查看全部）" % (len(rumor) - len(r_shown)))
    shown = lead if args.all else lead[:lead_cap]
    for i in shown:
        print(line(i, args.urls))
    if len(lead) > len(shown):
        print("  …另有 %d 条线索（--all 查看全部）" % (len(lead) - len(shown)))
    print()


def print_status(status):
    sm = status.get("summary", {})
    print("抓取状态：%d 个源，成功 %d，失败 %d；生成于 %s" % (
        sm.get("sources", 0), sm.get("ok", 0), sm.get("failed", 0),
        pdt(status.get("generatedAt")).astimezone(BJ).strftime("%m-%d %H:%M") if pdt(status.get("generatedAt")) else "?"))
    for s in status.get("sources", []):
        mark = "OK  " if s["ok"] and not s.get("warn") else ("WARN" if s["ok"] else "FAIL")
        print("  %s %-20s 抓到 %-5s 窗口内 %-4s 新增 %-4s %s" % (mark, s["id"], s["fetched"], s["inWindow"], s["new"],
                                                          s.get("error") or s.get("warn") or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=30)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--urls", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--checked", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dir", default=str(INBOX))
    args = ap.parse_args()
    d = Path(args.dir)
    try:
        doc = json.loads((d / "items.json").read_text(encoding="utf-8"))
        status = json.loads((d / "source-status.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print("读不到收件箱（%s）。请按旧流程用搜索补全，并在最终回复里说明收件箱不可用。" % e)
        return 1
    if args.status:
        print_status(status)
        return 0
    if args.checked:
        ok = [s for s in status.get("sources", []) if s["ok"]]
        names = [s["name"] for s in ok if not s["id"].startswith("gn-")]
        gn = [s for s in ok if s["id"].startswith("gn-")]
        if gn:
            names.append("Google 新闻关键词搜索（%d 组）" % len(gn))
        print(json.dumps(names, ensure_ascii=False))
        return 0

    now = datetime.now(UTC)
    gen = pdt(doc.get("generatedAt"))
    age = (now - gen).total_seconds() / 3600 if gen else None
    lo = now - timedelta(hours=args.hours)
    items = []
    for it in doc.get("items", []):
        if it.get("eventAt"):
            ev = pdt(it["eventAt"])
            if ev and lo <= ev <= now + timedelta(days=7):
                items.append(it)
            continue
        t, _ = when(it)
        if t and t >= lo:
            items.append(it)
    items.sort(key=lambda i: (when(i)[0] or lo), reverse=True)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=1))
        return 0

    print("# 收件箱（北京时间 %s 生成；最近 %g 小时内共 %d 条，下面按关注清单挑出相关的部分列出，实际列出的条数见末尾）" % (
        gen.astimezone(BJ).strftime("%m-%d %H:%M") if gen else "?", args.hours, len(items)))
    if age is None or age > STALE_HOURS:
        print("⚠ 收件箱已经 %s 小时没更新（正常每小时一次）：GitHub Actions 可能停了。"
              "不要只信收件箱，按旧流程用搜索补全，并在最终回复里提一句。" % ("%.0f" % age if age else "?"))
    bad = [s for s in status.get("sources", []) if not s["ok"] and s.get("failStreak", 0) >= 3]
    if bad:
        print("⚠ 连续失败 3 次以上的源（这些源当前没有数据，需要手动查）：" +
              "；".join("%s（%s）" % (s["name"], s.get("error") or "未知") for s in bad))
    print()

    l1 = [i for i in items if i["layer"] == 1 and "domestic" not in i.get("flags", [])]
    l2 = [i for i in items if i["layer"] == 2 and "domestic" not in i.get("flags", [])]
    l3 = [i for i in items if i["layer"] == 3]
    l0 = [i for i in items if i["layer"] == 0 and "domestic" not in i.get("flags", [])]
    cn = [i for i in items if "domestic" in i.get("flags", [])]

    print("## 第一层 · 盯死的对象\n")
    for w in LAYER1_ORDER:
        grp = [i for i in l1 if w in i["watch"]]
        if grp:
            show_group(w, grp, args)

    print("## 第二层 · 雷达领域（门槛高，只收多家独立来源都在报的）\n")
    used = set()
    for w in RADAR_ORDER[1:]:
        grp = [i for i in l2 if w in i["topics"]]
        used.update(i["id"] for i in grp)
        if grp:
            show_group(w, grp, args, lead_cap=6)
    rest = [i for i in l2 if i["id"] not in used]
    if rest:
        show_group("AI 全行业（国外）", rest, args, lead_cap=6)

    if l3:
        print("## 第三层 · 日程\n")
        show_group("发射与日程", l3, args)

    print("## 国内线索（只有「质的突破」才收；教育/留学/语培三项不在此列）\n")
    cn_show = cn if args.all else cn[:15]
    for i in cn_show:
        print(line(i, args.urls))
    if len(cn) > len(cn_show):
        print("  …另有 %d 条" % (len(cn) - len(cn_show)))
    print()

    if args.all:
        print("## 清单外（圈外位门槛极高：全科技圈都在报才收，每天最多 1 条）\n")
        for i in l0:
            print(line(i, args.urls))
    else:
        print("（清单外另有 %d 条，--all 查看）" % len(l0))
    print("\n---\n上面一共列出 %d 条候选（scan.candidates 从这个数起算，再加上你用搜索额外看过的条数）。"
          "成功读取的来源名用 --checked 取。" % PRINTED[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
