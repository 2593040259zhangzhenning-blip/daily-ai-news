#!/usr/bin/env python3
"""Signal（每日AI资讯）数据脚本。

用法：
  python3 scripts/add_issue.py path/to/issue.json          # 校验并写入一期，然后重建索引
  python3 scripts/add_issue.py path/to/issue.json --force  # 覆盖同名一期
  python3 scripts/add_issue.py --exists 2026-09-30-1morning  # 已存在则退出码 0，否则 1
  python3 scripts/add_issue.py --recent 3                  # 打印最近 N 期（定时任务去重用）
  python3 scripts/add_issue.py --rebuild                   # 只重建 data/index.json、data/days/ 和 data/latest.json
  python3 scripts/add_issue.py --special path/to/special.json [--force]  # 写入一份发布会专题（格式见 specials.md）
  python3 scripts/add_issue.py --special-exists devday-2026  # 该专题已存在则退出码 0，否则 1
  python3 scripts/add_issue.py --specials                  # 列出已有专题（slug、日期、标题）

每条新闻必须有：
  cat    model | policy | product | biz | china | research
  title  标题（30 字以内）
  body   1–3 句说明
  score  重要度 1–10（打分标准见 README）
  tier   lead（头条）| must（必看，0–3 条）| brief（其余）
         早间一期恰好 1 条 lead；晚间一期没有 lead，只有 must / brief
  summary 仅头条需要：一句话摘要（40 字以内），小组件大号显示
每期还要有 scan：{"checked": [实际检查过的来源名称], "candidates": 看过的候选条数}，见 sources.md
写入时按 头条 → 必看 → 其余、同档内按 score 从高到低 自动排序。

写入的文件：
  data/issues/<key>.json   单期原始数据
  data/index.json          网页读取的日期目录：每天有哪几期、当天标题（很小）
  data/days/<date>.json    网页按需加载的某一天全部内容（早间 + 晚间）
  data/specials/<slug>.json 发布会专题，挂在所属日期的页面最上方
  data/latest.json         小组件读取：最新一期的摘要（当天有专题时，头条换成专题）
"""
import json, re, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISSUES = ROOT / "data" / "issues"
SPECIALS = ROOT / "data" / "specials"
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CATS = {"model", "policy", "product", "biz", "china", "research"}
TIERS = {"lead": 0, "must": 1, "brief": 2}
EDITIONS = {"morning": "1", "evening": "2"}
KEY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[12](morning|evening)$")


def fail(msg):
    print(f"错误：{msg}", file=sys.stderr)
    sys.exit(2)


def normalize(d):
    """校验一期数据并按档位、分数排序。出错直接退出。"""
    for f in ("key", "date", "edition", "createdAt", "headline", "items"):
        if f not in d:
            fail(f"缺少字段 {f}")
    if d["edition"] not in EDITIONS:
        fail(f"edition 只能是 {sorted(EDITIONS)}")
    expect = f'{d["date"]}-{EDITIONS[d["edition"]]}{d["edition"]}'
    if d["key"] != expect or not KEY_RE.match(d["key"]):
        fail(f'key 应为 {expect}，实际是 {d["key"]}')
    try:
        datetime.fromisoformat(d["createdAt"])
    except ValueError:
        fail("createdAt 不是 ISO 8601 时间")
    items = d["items"]
    if not isinstance(items, list) or not items:
        fail("items 必须是非空数组")
    for i, it in enumerate(items):
        for f in ("cat", "title", "body", "score", "tier"):
            if it.get(f) in (None, ""):
                fail(f"items[{i}] 缺少 {f}")
        if it["cat"] not in CATS:
            fail(f'items[{i}].cat 只能是 {sorted(CATS)}，实际是 {it["cat"]}')
        if it["tier"] not in TIERS:
            fail(f'items[{i}].tier 只能是 lead / must / brief，实际是 {it["tier"]}')
        if not isinstance(it["score"], int) or not 1 <= it["score"] <= 10:
            fail(f"items[{i}].score 必须是 1–10 的整数")
        for s in it.get("sources", []):
            if not str(s.get("url", "")).startswith(("http://", "https://")):
                fail(f"items[{i}] 有无效来源链接")
        it.pop("must", None)
    leads = [it for it in items if it["tier"] == "lead"]
    musts = [it for it in items if it["tier"] == "must"]
    for it in leads:
        if not it.get("summary") or len(it["summary"]) > 45:
            fail("头条需要 summary（一句话摘要，40 字以内）")
    want = 1 if d["edition"] == "morning" else 0
    if len(leads) != want:
        fail(f"{'早间一期的头条（lead）必须恰好 1 条' if want else '晚间一期不能有头条（lead）'}，现在是 {len(leads)} 条")
    if len(musts) > 3:
        fail(f"必看（must）最多 3 条，现在是 {len(musts)} 条")
    items.sort(key=lambda it: (TIERS[it["tier"]], -it["score"]))
    if "watch" in d and not isinstance(d["watch"], list):
        fail("watch 必须是数组")
    scan = d.get("scan")
    if scan is not None:
        if not isinstance(scan.get("checked"), list) or not all(isinstance(x, str) for x in scan["checked"]):
            fail("scan.checked 必须是来源名称的数组")
        if not isinstance(scan.get("candidates"), int) or scan["candidates"] < len(items):
            fail("scan.candidates 必须是整数，且不少于收录条数")
    return d


def normalize_special(d):
    """校验一份专题。格式说明见 specials.md。"""
    for f in ("slug", "date", "title", "org", "cat", "createdAt", "summary", "highlights", "sources"):
        if d.get(f) in (None, "", []):
            fail(f"专题缺少字段 {f}")
    if not SLUG_RE.match(d["slug"]):
        fail("slug 只能用小写字母、数字和连字符，例如 openai-devday-2026")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d["date"]):
        fail("date 格式应为 YYYY-MM-DD（北京时间，发布会开始那天）")
    if d["cat"] not in CATS:
        fail(f"cat 只能是 {sorted(CATS)}")
    try:
        datetime.fromisoformat(d["createdAt"])
    except ValueError:
        fail("createdAt 不是 ISO 8601 时间")
    if len(d["title"]) > 24:
        fail("title 请控制在 24 字以内")
    if len(d["summary"]) > 90:
        fail("summary 请控制在 90 字以内")
    hs = d["highlights"]
    if not isinstance(hs, list) or len(hs) < 2:
        fail("highlights 至少 2 条")
    for i, h in enumerate(hs):
        for f in ("title", "body", "score"):
            if h.get(f) in (None, ""):
                fail(f"highlights[{i}] 缺少 {f}")
        if not isinstance(h["score"], int) or not 1 <= h["score"] <= 10:
            fail(f"highlights[{i}].score 必须是 1–10 的整数")
    hs.sort(key=lambda h: -h["score"])
    for k in ("forYou", "availability"):
        if k in d and not (isinstance(d[k], list) and all(isinstance(x, str) for x in d[k])):
            fail(f"{k} 必须是字符串数组")
    for s_ in d["sources"]:
        if not str(s_.get("url", "")).startswith(("http://", "https://")):
            fail("sources 里有无效链接")
    return d


def load_specials():
    if not SPECIALS.exists():
        return []
    out = [json.loads(p.read_text(encoding="utf-8")) for p in SPECIALS.glob("*.json")]
    out.sort(key=lambda x: (x["date"], x["createdAt"]))
    return out


def load_all():
    out = [json.loads(p.read_text(encoding="utf-8")) for p in ISSUES.glob("*.json")]
    out.sort(key=lambda x: x["key"], reverse=True)
    return out


def rebuild():
    issues = load_all()
    specials = load_specials()
    sp_by_date = {}
    for sp in specials:
        sp_by_date.setdefault(sp["date"], []).append(sp)
    # 网页先读一份很小的日期目录，翻到哪天再加载那一天的文件，所有历史都能翻到
    days_dir = ROOT / "data" / "days"
    days_dir.mkdir(parents=True, exist_ok=True)
    by_date = {}
    for x in issues:
        by_date.setdefault(x["date"], []).append(x)
    index = []
    for date in sorted(set(by_date) | set(sp_by_date)):
        day = sorted(by_date.get(date, []), key=lambda x: x["key"])
        sps = sp_by_date.get(date, [])
        (days_dir / f"{date}.json").write_text(
            json.dumps({"date": date, "issues": day, "specials": sps}, ensure_ascii=False, indent=1), encoding="utf-8")
        main = next((x for x in day if x["edition"] == "morning"), day[0] if day else None)
        stamps = [x["createdAt"] for x in day] + [sp["createdAt"] for sp in sps]
        index.append({"date": date,
                      "headline": main["headline"] if main else sps[0]["title"],
                      "updatedAt": max(stamps),
                      "count": sum(len(x["items"]) for x in day),
                      "specials": [{"slug": sp["slug"], "title": sp["title"]} for sp in sps]})
    (ROOT / "data" / "index.json").write_text(
        json.dumps({"generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "dates": index}, ensure_ascii=False, indent=1), encoding="utf-8")
    old = ROOT / "data" / "issues.json"
    if old.exists():
        old.unlink()

    latest = {"date": None, "headline": "", "updatedAt": None, "count": 0, "lead": None, "items": []}
    last_sp = specials[-1] if specials else None
    if last_sp and (not issues or last_sp["date"] >= issues[0]["date"]):
        # 最新一天有专题：小组件头条显示专题，下面列当天其余要闻
        day = last_sp["date"]
        todays = [x for x in issues if x["date"] == day]
        items = sorted([it for x in todays for it in x["items"]], key=lambda it: (TIERS[it["tier"]], -it["score"]))
        latest = {
            "date": day,
            "headline": last_sp["title"],
            "updatedAt": max([last_sp["createdAt"]] + [x["createdAt"] for x in todays]),
            "count": len(items) + len(last_sp["highlights"]),
            "lead": {"cat": last_sp["cat"], "title": last_sp["title"], "summary": last_sp["summary"][:48] + ("…" if len(last_sp["summary"]) > 48 else ""),
                     "special": last_sp["slug"]},
            "items": ([{"cat": last_sp["cat"], "title": h["title"], "tier": "must"} for h in last_sp["highlights"][:2]] +
                      [{"cat": it["cat"], "title": it["title"], "tier": it["tier"]} for it in items])[:5],
        }
    elif issues:
        # 一天一页：当天的早间和晚间合在一起
        day = issues[0]["date"]
        todays = [x for x in issues if x["date"] == day]
        main = next((x for x in todays if x["edition"] == "morning"), todays[-1])
        items = [it for x in todays for it in x["items"]]
        items.sort(key=lambda it: (TIERS[it["tier"]], -it["score"]))
        lead = next((it for it in items if it["tier"] == "lead"), items[0])
        first = re.split(r"(?<=[。！？])", lead["body"])[0].strip()
        latest = {
            "date": day,
            "headline": main["headline"],
            "updatedAt": max(x["createdAt"] for x in todays),
            "count": len(items),
            "lead": {"cat": lead["cat"], "title": lead["title"],
                     "summary": lead.get("summary") or (first if len(first) <= 50 else first[:48] + "…")},
            "items": [{"cat": it["cat"], "title": it["title"], "tier": it["tier"]}
                      for it in items if it is not lead][:5],
        }
    (ROOT / "data" / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已重建：{len(issues)} 期、{len(specials)} 份专题，最新 {latest['date']}")


def main(argv):
    if not argv:
        fail(__doc__)
    if argv[0] == "--rebuild":
        return rebuild()
    if argv[0] == "--exists":
        sys.exit(0 if (ISSUES / f"{argv[1]}.json").exists() else 1)
    if argv[0] == "--specials":
        for sp in load_specials():
            print(sp["slug"], sp["date"], sp["title"])
        return
    if argv[0] == "--special-exists":
        sys.exit(0 if (SPECIALS / f"{argv[1]}.json").exists() else 1)
    if argv[0] == "--special":
        d = normalize_special(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
        SPECIALS.mkdir(parents=True, exist_ok=True)
        dest = SPECIALS / f'{d["slug"]}.json'
        if dest.exists() and "--force" not in argv:
            fail(f'专题 {d["slug"]} 已存在（要覆盖请加 --force）')
        dest.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已写入 {dest.relative_to(ROOT)}")
        return rebuild()
    if argv[0] == "--recent":
        n = int(argv[1]) if len(argv) > 1 else 3
        print(json.dumps(load_all()[:n], ensure_ascii=False, indent=1))
        return
    d = normalize(json.loads(Path(argv[0]).read_text(encoding="utf-8")))
    dest = ISSUES / f'{d["key"]}.json'
    if dest.exists() and "--force" not in argv:
        fail(f'{d["key"]} 已存在（要覆盖请加 --force）')
    dest.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写入 {dest.relative_to(ROOT)}")
    rebuild()


if __name__ == "__main__":
    main(sys.argv[1:])
