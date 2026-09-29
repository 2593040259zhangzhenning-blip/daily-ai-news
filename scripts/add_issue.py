#!/usr/bin/env python3
"""AI 每日情报 数据脚本。

用法：
  python3 scripts/add_issue.py path/to/issue.json   # 校验并写入一期，然后重建索引
  python3 scripts/add_issue.py --exists 2026-09-30-1morning   # 已存在则退出码 0，否则 1
  python3 scripts/add_issue.py --recent 3           # 打印最近 N 期（给定时任务去重用）
  python3 scripts/add_issue.py --rebuild            # 只重建 data/issues.json 和 data/latest.json

写入的文件：
  data/issues/<key>.json   单期原始数据
  data/issues.json         网页读取：最近 120 期，新的在前
  data/latest.json         小组件读取：最新一天的摘要
"""
import json, re, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISSUES = ROOT / "data" / "issues"
CATS = {"model", "policy", "product", "biz", "china", "research"}
EDITIONS = {"weekly": "0", "morning": "1", "evening": "2"}
KEY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[012](weekly|morning|evening)$")
MAX_INDEX = 120


def fail(msg):
    print(f"错误：{msg}", file=sys.stderr)
    sys.exit(2)


def validate(d):
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
    if not isinstance(d["items"], list) or not d["items"]:
        fail("items 必须是非空数组")
    for i, it in enumerate(d["items"]):
        for f in ("cat", "title", "body"):
            if not it.get(f):
                fail(f"items[{i}] 缺少 {f}")
        if it["cat"] not in CATS:
            fail(f'items[{i}].cat 只能是 {sorted(CATS)}，实际是 {it["cat"]}')
        for s in it.get("sources", []):
            if not str(s.get("url", "")).startswith(("http://", "https://")):
                fail(f"items[{i}] 有无效来源链接")
    if "watch" in d and not isinstance(d["watch"], list):
        fail("watch 必须是数组")


def load_all():
    out = []
    for p in ISSUES.glob("*.json"):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    out.sort(key=lambda x: x["key"], reverse=True)
    return out


def rebuild():
    issues = load_all()
    (ROOT / "data" / "issues.json").write_text(
        json.dumps({"generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "issues": issues[:MAX_INDEX]}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    latest = {"date": None, "headline": "", "edition": None, "updatedAt": None,
              "count": 0, "editions": [], "items": []}
    if issues:
        day = issues[0]["date"]
        todays = [x for x in issues if x["date"] == day]  # 新的一期在前
        newest = todays[0]
        items = [it for x in todays for it in x["items"]]
        must = [it for it in items if it.get("must")]
        rest = [it for it in items if not it.get("must")]
        latest = {
            "date": day,
            "headline": newest["headline"],
            "edition": newest["edition"],
            "updatedAt": newest["createdAt"],
            "count": len(items),
            "editions": [x["edition"] for x in todays],
            "items": [{"cat": it["cat"], "title": it["title"], "must": bool(it.get("must"))}
                      for it in (must + rest)[:8]],
        }
    (ROOT / "data" / "latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=1), encoding="utf-8")
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
    src = Path(argv[0])
    d = json.loads(src.read_text(encoding="utf-8"))
    validate(d)
    dest = ISSUES / f'{d["key"]}.json'
    if dest.exists() and "--force" not in argv:
        fail(f'{d["key"]} 已存在（要覆盖请加 --force）')
    dest.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写入 {dest.relative_to(ROOT)}")
    rebuild()


if __name__ == "__main__":
    main(sys.argv[1:])
