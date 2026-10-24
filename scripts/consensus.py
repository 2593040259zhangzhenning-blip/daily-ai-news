"""共识打分：把收件箱里报同一件事的条目合并成「事件」，按几家独立来源在报来打分。

不用模型，纯规则，每次读收件箱现算（inbox_view.py 和 fetch_inbox.py 都调用）。
中转站、聚合站只投票、只提供线索，出处永远是原始链接（role=primary 的条目才是原文）。

做法：
1. 把标题拆成词（英文单词；中文连续汉字拆成相邻两字），去掉常见虚词；
2. 每个词按「在窗口里出现在多少条标题里」加权（越稀有越有区分度，「AI」「OpenAI」这种满天飞的几乎不算）；
3. 两条标题的加权相似度够高、发布时间又在 72 小时之内，就算同一件事；用并查集合并；
4. 一个事件的「来源数」= 其中不同发布方的数量（股价财经转载站合算一家，同一家媒体只算一次）。
"""
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

UTC = timezone.utc

STOP = set("""a an and are as at be been but by for from has have had he her his how in into is it its more most new not now of on
or our out over says say said she so than that the their them they this to up us was we were what when where which who why will with
would you your after before about also amid per via vs can could may might just first one two get gets got all any other some
inc corp ltd co llc plc news report reports reported latest today week day year years""".split())
HAN = re.compile(r"[一-鿿]+")
WORD = re.compile(r"[A-Za-z][A-Za-z0-9.\-+']*|\d+(?:\.\d+)?")
# 同一条新闻稿被转载站原样转发的发布方：合算一家
RELAYS = {"yahoo finance", "yahoo", "yahoo tech", "tradingview", "aol.com", "investing.com", "marketscreener.com",
          "benzinga", "msn", "newsbreak", "biggo finance", "moomoo", "the globe and mail"}
# 编辑票：这些聚合站本身不是出处，但「编辑挑了它」是共识的一个信号，按一家算
EDITOR_SOURCES = {"techmeme", "hn", "ai-news-radar", "follow-builders", "hf-papers", "gn-top-tech", "gn-top-science"}
LINK_ORIGIN_RE = re.compile(r"^https?://")


def _tokens(title):
    t = title or ""
    out = set()
    for w in WORD.findall(t):
        w = w.lower().strip(".-+'")
        w = re.sub(r"'s$", "", w)
        if len(w) >= 3 and w not in STOP:
            out.add(w[:-1] if w.endswith("s") and len(w) > 4 and not w.endswith("ss") else w)
        elif w.isdigit() or re.fullmatch(r"\d+\.\d+", w):
            out.add(w)
    for run in HAN.findall(t):
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    return out


# 同一家媒体在不同来源里的不同叫法，统一后只算一家
ALIASES = {
    "openai 官网": "openai", "英伟达博客": "nvidia", "nvidia blog": "nvidia", "英伟达新闻中心": "nvidia",
    "nvidia newsroom": "nvidia", "apple newsroom": "apple", "the verge ai": "the verge", "the verge 交通": "the verge",
    "techcrunch ai": "techcrunch", "techcrunch 交通": "techcrunch", "techcrunch 机器人": "techcrunch",
    "ars technica ai": "ars technica", "wired ai": "wired", "mit technology review ai": "mit technology review",
    "mit tr ai": "mit technology review", "量子位": "qbitai", "anthropic 新闻页": "anthropic",
    "ieee spectrum 机器人": "ieee spectrum", "ieee spectrum 半导体": "ieee spectrum", "ieee spectrum 生物医学": "ieee spectrum",
    "google deepmind 博客": "google", "google ai 栏目": "google", "google research 博客": "google",
    "9to5mac": "9to5mac", "macrumors": "macrumors",
}


def _outlet(it):
    org = (it.get("origin") or "").strip().lower()
    org = re.sub(r"^https?://|/$", "", org)
    if it["source"] in EDITOR_SOURCES:
        # 编辑票按聚合站算一家；它链到的原发布方如果能识别，另外算一票
        return "编辑:" + it["source"]
    name = org or it.get("sourceName", it["source"]).split("：")[0]
    name = name.lower()
    name = ALIASES.get(name, name)
    return "转载站" if name in RELAYS else name


def _pt(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _time(it):
    return _pt(it.get("eventAt")) or _pt(it.get("publishedAt")) or _pt(it.get("firstSeen"))


def cluster(items, threshold=0.55, max_gap_hours=72):
    """返回事件列表（按来源数从多到少）。items 是 items.json 里的条目。"""
    docs = [(it, _tokens(it["title"])) for it in items if it.get("kind") != "changelog"]
    n = len(docs)
    df = Counter()
    for _, tk in docs:
        df.update(tk)
    idf = {w: math.log((n + 1) / (c + 0.5)) for w, c in df.items()}
    # 太常见的词（出现在 4% 以上的标题里）几乎没有区分度，直接不参与匹配
    common = {w for w, c in df.items() if c > max(30, n * 0.04)}
    toks = [{w for w in tk if w not in common} for _, tk in docs]
    norm = [math.sqrt(sum(idf[w] ** 2 for w in tk)) or 1.0 for tk in toks]
    inv = defaultdict(list)
    for i, tk in enumerate(toks):
        for w in tk:
            inv[w].append(i)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    times = [_time(it) for it, _ in docs]
    for i, tk in enumerate(toks):
        if len(tk) < 3:
            continue
        cand = Counter()
        for w in tk:
            if len(inv[w]) > 400:
                continue
            for j in inv[w]:
                if j < i:
                    cand[j] += idf[w] ** 2
        for j, dot in cand.items():
            if find(i) == find(j):
                continue
            sim = dot / (norm[i] * norm[j])
            if sim < threshold:
                continue
            if times[i] and times[j] and abs((times[i] - times[j]).total_seconds()) > max_gap_hours * 3600:
                continue
            parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    events = []
    for idxs in groups.values():
        its = [docs[i][0] for i in idxs]
        outlets = {}
        for it in its:
            outlets.setdefault(_outlet(it), it)
        n_out = len(outlets)
        editors = sum(1 for o in outlets if o.startswith("编辑:"))
        real = n_out - editors
        primary = [it for it in its if it.get("role") == "primary" and "rumor" not in it.get("flags", [])]
        official = [it for it in primary if it.get("tier") == 1]
        # 代表标题：优先一手、层级高、标题长度适中的
        best = sorted(its, key=lambda it: (it.get("role") != "primary", it.get("tier", 9), abs(len(it["title"]) - 70)))[0]
        watch = sorted({w for it in its for w in it.get("watch", [])})
        topics = sorted({t for it in its for t in it.get("topics", [])})
        ts = [t for t in (_time(it) for it in its) if t]
        events.append(dict(
            title=best["title"], url=best["url"] if best.get("role") == "primary" else None,
            outlets=n_out, real_outlets=real, editors=editors,
            official=bool(official), primary_n=len(primary), items=len(its),
            watch=watch, topics=topics,
            layer=min((it.get("layer", 0) or 9) for it in its) if any(it.get("layer") for it in its) else 0,
            flags=sorted({f for it in its for f in it.get("flags", [])}),
            first=min(ts) if ts else None, last=max(ts) if ts else None,
            outlet_names=sorted(o for o in outlets if not o.startswith("编辑:")),
            editor_names=sorted(o[3:] for o in outlets if o.startswith("编辑:")),
            primary_links=[(it["sourceName"], it["url"]) for it in (official or primary)[:3]],
            ids=[it["id"] for it in its],
        ))
    events.sort(key=lambda e: (e["real_outlets"] + e["editors"] * 0.5 + (2 if e["official"] else 0)), reverse=True)
    return events


def level(e):
    """共识档：高 / 中 / 低。真实发布方数 + 编辑票 + 官方是否发了。"""
    score = e["real_outlets"] + 0.5 * e["editors"] + (2 if e["official"] else 0)
    if score >= 9:
        return "高"
    if score >= 5:
        return "中"
    return "低"


def score(e):
    return e["real_outlets"] + 0.5 * e["editors"] + (2 if e["official"] else 0)


def is_outside(e, min_score=5):
    """圈外候选：没命中关注清单和雷达领域，不是融资/人事/股价，不是国内消息，共识够高。"""
    return (not e["watch"] and not e["topics"] and score(e) >= min_score
            and not ({"money_people", "domestic"} & set(e["flags"])))


# ---------------------------------------------------------------- 事件日志 ----
LOG_DAYS = 21


def _iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def update_log(log, events, items_by_id, now):
    """把这次算出的事件并进滚动日志（data/inbox/events-log.json，保留 21 天），每周复盘靠它。
    只记共识中档以上的事件和圈外候选；按条目 id 重合来认「还是同一件事」（收件箱只留 48 小时，事件会逐步长大）。"""
    entries = log.get("events", [])
    by_id = {}
    for k, en in enumerate(entries):
        for i in en["ids"]:
            by_id[i] = k
    for e in events:
        lv = level(e)
        outside = is_outside(e)
        if lv == "低" and not outside:
            continue
        urls = [items_by_id[i]["url"] for i in e["ids"]
                if i in items_by_id and not items_by_id[i]["source"].startswith("gn-")][:12]
        hit = next((by_id[i] for i in e["ids"] if i in by_id), None)
        rec = dict(
            title=e["title"], first=_iso(e["first"]), last=_iso(e["last"]),
            maxScore=round(score(e), 1), maxOutlets=e["real_outlets"], official=e["official"],
            watch=e["watch"], topics=e["topics"], flags=e["flags"], outside=outside,
            outlets=e["outlet_names"][:14], editors=e["editor_names"], urls=urls,
            primaryLinks=e["primary_links"], ids=e["ids"][:60])
        if hit is None:
            entries.append(rec)
            for i in rec["ids"]:
                by_id[i] = len(entries) - 1
            continue
        old = entries[hit]
        rec["first"] = min(filter(None, [old.get("first"), rec["first"]]), default=None)
        rec["title"] = old["title"] if old.get("maxScore", 0) >= rec["maxScore"] else rec["title"]
        rec["maxScore"] = max(old.get("maxScore", 0), rec["maxScore"])
        rec["maxOutlets"] = max(old.get("maxOutlets", 0), rec["maxOutlets"])
        rec["official"] = old.get("official") or rec["official"]
        rec["outside"] = old.get("outside") or rec["outside"]
        rec["outlets"] = sorted(set(old.get("outlets", [])) | set(rec["outlets"]))[:14]
        rec["editors"] = sorted(set(old.get("editors", [])) | set(rec["editors"]))
        rec["urls"] = (old.get("urls", []) + [u for u in rec["urls"] if u not in old.get("urls", [])])[:16]
        rec["ids"] = list(dict.fromkeys(old.get("ids", []) + rec["ids"]))[-60:]
        entries[hit] = rec
        for i in rec["ids"]:
            by_id[i] = hit
    lo = _iso(datetime.fromtimestamp(now.timestamp() - LOG_DAYS * 86400, UTC))
    entries = [en for en in entries if (en.get("last") or en.get("first") or "") >= lo]
    return dict(updatedAt=_iso(now), days=LOG_DAYS, events=entries)
