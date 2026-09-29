#!/usr/bin/env python3
"""每日AI资讯 数据脚本。

用法：
  python3 scripts/add_issue.py path/to/issue.json          # 校验并写入一期，然后重建索引
  python3 scripts/add_issue.py path/to/issue.json --force  # 覆盖同名一期
  python3 scripts/add_issue.py --exists 2026-09-30-1morning  # 已存在则退出码 0，否则 1
  python3 scripts/add_issue.py --recent 3                  # 打印最近 N 期（定时任务去重用）
  python3 scripts/add_issue.py --rebuild                   # 只重建 data/issues.json 和 data/latest.json

每条新闻必须有：
  cat    model | policy | product | biz | china | research
  title  标题（30 字以内）
  body   1–3 句说明
  score  重要度 1–10（打分标准见 README）
  tier   lead（头条，每期恰好 1 条）| must（必看，0–3 条）| brief（其余）
写入时按 头条 → 必看 → 其余、同档内按 score 从高到低 自动排序。

写入的文件：
  data/issues/<key>.json   单期原始数据
  data/issues.json         网页读取：最近 120 期，新的在前
  data/latest.json         小组件读取：最新一期的摘要
"""
import json, re, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISSUES = ROOT / "data" / "issues"
CATS = {"model", "policy", "product", "biz", "china", "research"}
TIERS = {"lead": 0, "must": 1, "brief": 2}
EDITIONS = {"weekly": "0", "morning": "1", "evening": "2"}
KEY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[012](weekly|morning|evening)$")
MAX_INDEX = 120


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
    if len(leads) != 1:
        fail(f"头条（lead）必须恰好 1 条，现在是 {len(leads)} 条")
    if len(musts) > 3:
        fail(f"必看（must）最多 3 条，现在是 {len(musts)} 条")
    items.sort(key=lambda it: (TIERS[it["tier"]], -it["score"]))
    if "watch" in d and not isinstance(d["watch"], list):
        fail("watch 必须是数组")
    return d


def load_all():
    out = [json.loads(p.read_text(encoding="utf-8")) for p in ISSUES.glob("*.json")]
    out.sort(key=lambda x: x["key"], reverse=True)
    return out


def rebuild():
    issues = load_all()
    (ROOT / "data" / "issues.json").write_text(
        json.dumps({"generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "issues": issues[:MAX_INDEX]}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    latest = {"date": None, "edition": None, "headline": "", "updatedAt": None, "count": 0, "items": []}
    if issues:
        # 小组件显示当天的主刊（早刊，没有就取当天最新一期）；晚间增刊的头条和必看并进来
        day = issues[0]["date"]
        todays = [x for x in issues if x["date"] == day]
        main = next((x for x in todays if x["edition"] == "morning"), todays[0])
        extra = [x for x in todays if x["edition"] == "evening" and x is not main]
        top = [it for x in [main] + extra for it in x["items"] if it["tier"] in ("lead", "must")]
        top.sort(key=lambda it: (TIERS[it["tier"]], -it["score"]))
        latest = {
            "date": day,
            "edition": main["edition"],
            "headline": main["headline"],
            "updatedAt": max(x["createdAt"] for x in todays),
            "hasEvening": bool(extra),
            "count": sum(len(x["items"]) for x in [main] + extra),
            "items": [{"cat": it["cat"], "title": it["title"], "tier": it["tier"]} for it in top[:6]],
        }
    (ROOT / "data" / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已重建：{len(issues)} 期，最新 {latest['date']} {latest['edition']}")


def main(argv):
    if not argv:
        fail(__doc__)
    if argv[0] == "--rebuild":
        return rebuild()
    if argv[0] == "--exists":
        sys.exit(0 if (ISSUES / f"{argv[1]}.json").exists() else 1)
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
