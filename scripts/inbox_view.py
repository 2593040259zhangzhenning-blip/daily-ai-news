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
  python3 scripts/inbox_view.py --no-events      # 不打印开头的「共识事件」「圈外候选」
  python3 scripts/inbox_view.py --fresh          # 先在本机现抓一遍（写到 /tmp/signal-inbox，不动仓库），再读（早间任务用）
  python3 scripts/inbox_view.py --checked --fresh  # 同上，30 分钟内抓过就直接复用那一份

读法：
  「共识事件」：程序把报同一件事的条目合并起来，按几家独立来源在报排序（中转站、聚合站不当出处，只算票）。
  共识高不等于值得收，收不收仍按 watchlist.md 判断；它的用处是让你先看到「很多家都在报」的事，别漏。
  「圈外候选」：不在关注清单里、但共识很高的事件，圈外位每天最多收 1 条。
  [一手] 链接就是原文，可以当出处（再按 sources.md 判断层级）。
  [线索] 聚合站、中转站、Google 新闻、个人 X 账号：只用来发现事件，出处必须回到原文。
  「功能更新候选」：产品更新日志（Claude Code、Claude 应用、ChatGPT / Codex、OpenAI API）里的条目，单独成一节，
  不会再出现在下面按对象分的组里；是否写进当期的 updates 由定时任务按 watchlist.md 判断（只要用户能感觉到的变化）。
  时间前面的 ~ 表示来源没给发布时间，用的是「收件箱第一次发现它的时间」。
  「Grok 侦察」（2026-10-30 起）：Grok Bot 每天 06:15 前后写的 data/grok/scout/<日期>.json，X 上的官方账号帖子、关键人物帖子、
  X 上热议的事。[一手·Grok] 是官方账号的帖子，可以当出处（做头条或必看还要再有一个非 Grok 的来源）；[线索·Grok] 只用来发现事件。
  ChatGPT 发布说明也由 Grok 读，出现在「功能更新候选」里。
"""
import shutil
import subprocess
import time
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inbox_config as C  # noqa: E402
import consensus as K  # noqa: E402
import grok_io as G  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox"
UTC = timezone.utc
BJ = timezone(timedelta(hours=8))
STALE_HOURS = 3
FRESH_DIR = Path("/tmp/signal-inbox")
FRESH_REUSE_MIN = 30

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
    if it.get("kind") == "changelog" and it.get("snippet"):
        s += "\n    摘要：" + it["snippet"]
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


def event_line(e, urls):
    tags = "、".join(e["watch"] + e["topics"]) or "清单外"
    flags = []
    if e["official"]:
        flags.append("官方已发")
    if "money_people" in e["flags"]:
        flags.append("融资/人事/股价")
    if "domestic" in e["flags"]:
        flags.append("国内")
    if "rumor" in e["flags"]:
        flags.append("传闻类")
    head = "[%s] %d 家在报%s%s · %s · %s" % (
        K.level(e), e["real_outlets"], ("+%d 张编辑票" % e["editors"]) if e["editors"] else "",
        ("（" + "、".join(flags) + "）") if flags else "", tags, e["title"])
    rows = [head]
    names = e["outlet_names"][:6]
    if names:
        rows.append("    在报：" + "、".join(names) + (" 等" if len(e["outlet_names"]) > 6 else ""))
    if e["editor_names"]:
        rows.append("    编辑挑了：" + "、".join(e["editor_names"]))
    for nm, u in e["primary_links"][:2]:
        rows.append("    一手：%s %s" % (nm, u))
    return "\n".join(rows)


def print_events(items, args):
    events = K.cluster(items, threshold=0.5)
    top = [e for e in events if K.level(e) in ("高", "中") and e["real_outlets"] >= 3]
    top = top[:25] if not args.all else top
    print("## 共识事件（几家独立来源在报；共 %d 个事件，下面是共识高、中档的前 %d 个）\n" % (len(events), len(top)))
    for e in top:
        print(event_line(e, args.urls))
    if not top:
        print("（这段时间没有共识中档以上的事件）")
    print()
    out = [e for e in events if K.is_outside(e)][:4]
    print("## 圈外候选（不在关注清单里；全科技圈都在报才收，每天最多 1 条，标「圈外」；没有就不收）\n")
    for e in out:
        print(event_line(e, args.urls))
    if not out:
        print("（今天没有够格的圈外候选）")
    print()


def print_status(status):
    sm = status.get("summary", {})
    print("抓取状态：%d 个源，成功 %d，失败 %d；生成于 %s" % (
        sm.get("sources", 0), sm.get("ok", 0), sm.get("failed", 0),
        pdt(status.get("generatedAt")).astimezone(BJ).strftime("%m-%d %H:%M") if pdt(status.get("generatedAt")) else "?"))
    for s in status.get("sources", []):
        mark = "OK  " if s["ok"] and not s.get("warn") else ("WARN" if s["ok"] else "FAIL")
        mark = "STAL" if s["ok"] and s.get("stale") and not s.get("warn") else mark
        print("  %s %-20s 抓到 %-5s 窗口内 %-4s 新增 %-4s %s" % (mark, s["id"], s["fetched"], s["inWindow"], s["new"],
                                                          s.get("error") or s.get("warn") or s.get("stale") or ""))


def refresh(args):
    """早间任务开跑时现抓一遍：GitHub 的每小时定时触发经常掉队（2026-10-25 起常常四五个小时才跑一次），
    靠这一步保证 06:50 读到的是几分钟前的消息。抓到临时目录，不提交，不会和机器人的每小时提交打架。
    抓不成就退回仓库里的收件箱，并返回一句说明。"""
    stamp = FRESH_DIR / ".refreshed"
    if stamp.exists() and time.time() - stamp.stat().st_mtime < FRESH_REUSE_MIN * 60:
        return FRESH_DIR, None
    try:
        if FRESH_DIR.exists():
            shutil.rmtree(FRESH_DIR)
        shutil.copytree(INBOX, FRESH_DIR)      # 带上旧状态：页面变动监测要靠它判断哪些链接是新的
        r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "fetch_inbox.py"), "--out", str(FRESH_DIR)],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1:] or ["退出码 %d" % r.returncode])
        stamp.write_text("ok")
        return FRESH_DIR, None
    except Exception as e:      # 现抓失败不能挡住任务
        return INBOX, "现抓失败（%s），用的是仓库里机器人上次抓的收件箱" % str(e)[:160]


def grok_time(t):
    return t.astimezone(BJ).strftime("%m-%d %H:%M") if t else "时间不明"


def grok_lines(sc):
    """把侦察文件里的 X 帖子和热议打印成候选行。"""
    rows = []
    posts = sorted(sc["x"]["posts"], key=lambda p: (not p["official"], -(p["postedAt"].timestamp() if p["postedAt"] else 0)))
    for p in posts:
        PRINTED[0] += 1
        kind = "一手·Grok" if p["official"] else "线索·Grok"
        r = "[%s] %s · %s · %s%s\n    %s" % (kind, grok_time(p["postedAt"]), p["account"],
                                           ("%s · " % p["watch"]) if p["watch"] else "", p["summary"], p["url"])
        if p["links"]:
            r += "\n    帖子里的链接：" + " ".join(p["links"])
        rows.append(r)
    post_urls = {p["url"] for p in sc["x"]["posts"]}
    for b in sc["x"]["buzz"]:
        if b["urls"] and any(u.split("?")[0] in post_urls for u in b["urls"]):
            continue                      # 热议里引的就是上面已列出的官方帖，不重复列
        PRINTED[0] += 1
        r = "[线索·Grok·热议] %s%s%s" % (("%s · " % b["watch"]) if b["watch"] else "", b["title"],
                                     "（Grok 说已有官方确认）" if b["confirmed"] else "")
        if b["accounts"]:
            r += "\n    在说的人：" + "、".join(b["accounts"])
        if b["urls"]:
            r += "\n    " + " ".join(b["urls"])
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=30)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--urls", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--checked", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-events", action="store_true")
    ap.add_argument("--dir", default=str(INBOX))
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()
    d = Path(args.dir)
    fresh_note = None
    if args.fresh:
        d, fresh_note = refresh(args)
    scout, scout_probs, _ = G.latest_scout()
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
        if scout and scout["x"]["ok"]:
            names.append("X 官方账号与关键人物（经 Grok，%d 个账号）" % len(scout["x"]["checked"]) if scout["x"]["checked"]
                         else "X 官方账号与关键人物（经 Grok）")
        if scout and scout["chatgptReleaseNotes"]["ok"]:
            names.append("ChatGPT 发布说明（经 Grok）")
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
    if fresh_note:
        print("⚠ " + fresh_note + "。")
    if age is None or age > STALE_HOURS:
        print("⚠ 收件箱已经 %s 小时没更新（正常每小时一次）：GitHub Actions 可能停了。"
              "不要只信收件箱，按旧流程用搜索补全，并在最终回复里提一句。" % ("%.0f" % age if age else "?"))
    gn_all = [s for s in status.get("sources", []) if s["id"].startswith("gn-")]
    gn_bad = [s for s in gn_all if not s["ok"]]
    if gn_all and len(gn_bad) * 2 >= len(gn_all):
        print("⚠ 谷歌新闻 %d 组里有 %d 组这次没抓到（%s）：关注对象的媒体报道会明显变少，第一层对象要用搜索逐个补查。" % (
            len(gn_all), len(gn_bad), gn_bad[0].get("error") or "未知"))
    if not scout:
        print("⚠ Grok 侦察：%s。X 部分照旧用 site:x.com 搜索，ChatGPT 发布说明照旧用 WebFetch 读。" % "；".join(scout_probs))
    else:
        if not scout["x"]["ok"]:
            print("⚠ Grok 侦察这次没查成 X（%s）：X 部分照旧用 site:x.com 搜索。" % scout["x"]["error"])
        if not scout["chatgptReleaseNotes"]["ok"]:
            print("⚠ Grok 这次没读到 ChatGPT 发布说明（%s）：照旧用 WebFetch 读。" % scout["chatgptReleaseNotes"]["error"])
        if scout_probs:
            print("（Grok 侦察文件有格式问题，已丢掉不合格的条目：%s）" % "；".join(scout_probs))
    bad = [s for s in status.get("sources", []) if not s["ok"] and s.get("failStreak", 0) >= 3]
    if bad:
        print("⚠ 连续失败 3 次以上的源（这些源当前没有数据，需要手动查）：" +
              "；".join("%s（%s）" % (s["name"], s.get("error") or "未知") for s in bad))
    print()

    if not args.no_events:
        try:
            print_events([i for i in items if i.get("kind") != "changelog"], args)
        except Exception as e:      # 共识打分出错不能挡住后面的清单
            print("（共识打分失败：%s %s，请直接看下面的清单）\n" % (type(e).__name__, e))

    cl = [i for i in items if i.get("kind") == "changelog"]
    items = [i for i in items if i.get("kind") != "changelog"]      # 更新日志只在「功能更新候选」里出现一次
    l1 = [i for i in items if i["layer"] == 1 and "domestic" not in i.get("flags", [])]
    l2 = [i for i in items if i["layer"] == 2 and "domestic" not in i.get("flags", [])]
    l3 = [i for i in items if i["layer"] == 3]
    l0 = [i for i in items if i["layer"] == 0 and "domestic" not in i.get("flags", [])]
    cn = [i for i in items if "domestic" in i.get("flags", [])]

    if scout:
        x = scout["x"]
        print("## Grok 侦察 · X（Grok Bot 北京时间 %s 写入；官方帖 %d 条、个人帖 %d 条、热议 %d 件）\n" % (
            grok_time(scout["generatedAt"]), sum(p["official"] for p in x["posts"]),
            sum(not p["official"] for p in x["posts"]), len(x["buzz"])))
        rows = grok_lines(scout)
        print("\n".join(rows) if rows else ("（Grok 查了，过去 24 小时关注对象在 X 上没有值得看的新帖）" if x["ok"] else "（X 没查成，见开头的 ⚠）"))
        print()

    rn = scout["chatgptReleaseNotes"] if scout else None
    rn_rows = []
    if rn and rn["ok"]:
        recent = (now.astimezone(BJ) - timedelta(days=3)).strftime("%Y-%m-%d")
        for e in rn["entries"]:
            if e["date"] >= recent:
                PRINTED[0] += 1
                rn_rows.append("[一手·Grok] %s（仅日期） · ChatGPT 发布说明 · %s%s\n    %s" % (
                    e["date"][5:], e["title"], ("——" + e["summary"]) if e["summary"] else "", rn["url"]))
    print("## 功能更新候选（产品更新日志，共 %d 条%s；工程细节居多，只挑用户能感觉到的变化写进 updates）\n" % (
        len(cl) + len(rn_rows), "，含 Grok 读的 ChatGPT 发布说明 %d 条" % len(rn_rows) if rn and rn["ok"] else ""))
    for i in cl:
        print(line(i, args.urls))
    for r in rn_rows:
        print(r)
    if rn and rn["ok"] and not rn_rows:
        print("（Grok 读了 ChatGPT 发布说明，最近 3 天没有新条目）")
    if not cl and not rn_rows:
        print("（这段时间更新日志类来源没有新条目）")
    print()

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
