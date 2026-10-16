#!/usr/bin/env python3
"""Signal 收件箱抓取脚本：按关注清单读各个信源，合并成最近 48 小时的候选。

只用 Python 标准库。GitHub Actions 每小时跑一次（.github/workflows/inbox.yml）。

输出（都在 data/inbox/）：
  items.json         最近 48 小时的候选条目，一条一行，按时间从新到旧
  source-status.json 每个源这次抓取成功没有、抓到几条、连续失败几次
  state.json         页面变动监测的记忆（已经见过哪些链接）

用法：
  python3 scripts/fetch_inbox.py                  # 抓取全部源并写文件
  python3 scripts/fetch_inbox.py --only openai,hn # 只抓指定的源（调试用）
  python3 scripts/fetch_inbox.py --dry-run        # 只打印结果，不写文件
  python3 scripts/fetch_inbox.py --list           # 列出全部源

条目字段：
  id, title, url, publishedAt（拿不到发布时间就是 null）, firstSeen, source, sourceName,
  tier（来源层级 1–5，见 sources.md）, role（primary 链接即原文 / lead 只是线索）,
  region（intl / cn）, layer（1 盯死的对象 2 雷达领域 3 日程 0 清单外）,
  watch（命中的关注对象）, topics（命中的雷达领域）, flags（rumor 传闻类 / money_people 融资人事股价 / domestic 国内）,
  snippet（≤160 字摘要）, origin（聚合源里的原始媒体名）, eventAt（日程类条目的事件时间）, meta（点赞数等）,
  dateOnly（来源只给了日期没给时刻，publishedAt 按当天结束算）
"""
import argparse
import concurrent.futures as cf
import hashlib
import html as htmlmod
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inbox_config as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox"
UTC = timezone.utc
BJ = timezone(timedelta(hours=8))


# ---------------------------------------------------------------- 时间 ----
def now_utc():
    return datetime.now(UTC).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def parse_dt(s):
    if not s:
        return None
    s = str(s).strip()
    try:
        dt = parsedate_to_datetime(s)
        if dt is not None:
            return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)
    except (TypeError, ValueError, IndexError):
        pass
    t = re.sub(r"(\.\d{6})\d+", r"\1", s.replace("Z", "+00:00"))
    for cand in (t, t.replace(" ", "T", 1)):
        try:
            dt = datetime.fromisoformat(cand)
            return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)
        except ValueError:
            continue
    return None


MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DATE_PATTERNS = [
    (re.compile(r"\b([A-Z][a-z]{2,8})\.? (\d{1,2}), (\d{4})\b"), "mdy"),
    (re.compile(r"\b(\d{1,2}) ([A-Z][a-z]{2,8})\.? (\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b"), "dd/mm/yyyy"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso"),
    (re.compile(r"/t(\d{4})(\d{2})(\d{2})_\d+"), "iso"),
]


def find_date(text):
    """从一段文字里找日期，返回 (date, 匹配起止位置)；找不到返回 (None, None)。"""
    for rx, kind in DATE_PATTERNS:
        m = rx.search(text or "")
        if not m:
            continue
        try:
            if kind == "mdy":
                mon = MONTHS.get(m.group(1)[:3].lower())
                d = date(int(m.group(3)), mon, int(m.group(2))) if mon else None
            elif kind == "dmy":
                mon = MONTHS.get(m.group(2)[:3].lower())
                d = date(int(m.group(3)), mon, int(m.group(1))) if mon else None
            elif kind == "dd/mm/yyyy":
                d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            else:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except (ValueError, TypeError):
            d = None
        if d:
            return d, m.span()
    return None, None


def day_end(d, now):
    """只有日期没有时刻的发布时间：按当天结束算，但不晚于现在。"""
    dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC)
    return min(dt, now)


# ---------------------------------------------------------------- 网络 ----
class FetchError(Exception):
    def __init__(self, msg, status=None):
        super().__init__(msg)
        self.status = status


_HOST_LOCK = threading.Lock()
_HOST_LOCKS = {}
_HOST_LAST = {}


def _polite_wait(host):
    gap = 1.5 if host.endswith("google.com") else 0.3
    with _HOST_LOCK:
        lock = _HOST_LOCKS.setdefault(host, threading.Lock())
    with lock:
        wait = _HOST_LAST.get(host, 0) + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _HOST_LAST[host] = time.time()


def http_get(url, accept="*/*", timeout=30, retries=1):
    """返回 (状态码, 字节, Content-Type, 最终地址)。失败抛 FetchError。"""
    host = urllib.parse.urlparse(url).hostname or ""
    for attempt in range(retries + 1):
        try:
            _polite_wait(host)
            req = urllib.request.Request(url, headers={
                "User-Agent": C.USER_AGENT, "Accept": accept,
                "Accept-Language": "en-US,en;q=0.8,zh-CN;q=0.6"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), r.headers.get("Content-Type", ""), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(4)
                continue
            raise FetchError("HTTP %d" % e.code, e.code)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < retries:
                time.sleep(3)
                continue
            reason = getattr(e, "reason", e)
            kind = "超时" if "timed out" in str(reason).lower() else "连接失败"
            raise FetchError("%s：%s" % (kind, str(reason)[:120]))
    raise FetchError("未知错误")


def decode_html(data, ctype=""):
    m = re.search(r"charset=([\w\-]+)", ctype or "", re.I)
    if not m:
        m = re.search(rb"<meta[^>]+charset=[\"']?([\w\-]+)", data[:4096], re.I)
        enc = m.group(1).decode("ascii", "ignore") if m else "utf-8"
    else:
        enc = m.group(1)
    try:
        return data.decode(enc, errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- 文本 ----
def strip_html(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(htmlmod.unescape(s).split())


def clip(s, n):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def norm_url(u, keep_fragment=False):
    try:
        p = urllib.parse.urlsplit(u.strip())
    except ValueError:
        return u.strip()
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
         if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid", "ref", "cmpid", "source")]
    path = p.path.rstrip("/") if p.path not in ("", "/") else p.path
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urllib.parse.urlencode(q),
                                    p.fragment if keep_fragment else ""))


def item_id(source, key):
    return hashlib.sha1(("%s|%s" % (source, key)).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- RSS ----
def _ln(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el):
    return "".join(el.itertext()).strip() if el is not None else ""


def parse_feed(data):
    """RSS 2.0 / Atom / RDF 都能读。返回条目列表。"""
    try:
        root = ET.fromstring(data.lstrip())
    except ET.ParseError:
        # 有的订阅源里混着 HTML 实体（&nbsp; 之类），XML 解析器不认识：转成字符再试一次
        txt = data.decode("utf-8", errors="replace")
        txt = re.sub(r"&([A-Za-z][A-Za-z0-9]*);",
                     lambda m: m.group(0) if m.group(1) in ("amp", "lt", "gt", "quot", "apos")
                     else htmlmod.escape(htmlmod.unescape(m.group(0)), quote=False), txt)
        txt = re.sub(r"^<\?xml[^>]*\?>", "", txt.lstrip())
        try:
            root = ET.fromstring(txt)
        except ET.ParseError as e:
            raise FetchError("订阅源解析失败：%s" % str(e)[:100])
    out = []
    for el in root.iter():
        if _ln(el.tag) not in ("item", "entry"):
            continue
        d = {"title": "", "url": "", "published": None, "snippet": "", "origin": "", "guid": ""}
        links = []
        for c in el:
            n = _ln(c.tag)
            if n == "title":
                d["title"] = _text(c)
            elif n == "link":
                if c.get("href"):
                    links.append((c.get("rel") or "alternate", c.get("href")))
                elif (c.text or "").strip():
                    links.append(("alternate", c.text.strip()))
            elif n in ("pubDate", "published", "date", "issued") and not d["published"]:
                d["published"] = parse_dt(_text(c))
            elif n in ("updated", "modified") and not d["published"]:
                d["updated"] = parse_dt(_text(c))
            elif n in ("description", "summary") and not d["snippet"]:
                d["snippet"] = strip_html(_text(c))
            elif n in ("encoded", "content") and not d["snippet"]:
                d["snippet"] = strip_html(_text(c))
            elif n == "source":
                d["origin"] = _text(c)
            elif n in ("guid", "id"):
                d["guid"] = _text(c)
        if not d["published"]:
            d["published"] = d.pop("updated", None)
        d.pop("updated", None)
        alt = [h for rel, h in links if rel == "alternate"] or [h for _, h in links]
        d["url"] = alt[0] if alt else (d["guid"] if d["guid"].startswith("http") else "")
        if d["title"] and d["url"]:
            out.append(d)
    return out


# ---------------------------------------------------------------- 页面 ----
class _Anchors(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.href, self.buf, self.out = base, None, [], []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.buf = []

    def handle_data(self, data):
        if self.href is not None:
            self.buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            h = self.href.strip()
            if h and not h.startswith(("javascript:", "mailto:", "#")):
                self.out.append((urllib.parse.urljoin(self.base, h), " ".join(" ".join(self.buf).split())))
            self.href = None


CATEGORY_WORDS = (r"Announcements?|Policy|Product|Products|Science|Research|Societal Impacts|Economic Research|Interpretability|"
                  r"Alignment|Customer stories|Education|Global Insight|Global News|Teachers Insight|Learner Insight|"
                  r"Featured|FEATURED|Learn More|\d+ min")
WEAK_TITLES = {"", "featured", "learn more", "read more", "more", "next", "blog", "news"}


def title_from_anchor(text):
    """锚文字里常混着分类、日期、摘要：尽量抠出标题。"""
    text = re.sub(r"\s*(?:Read|Learn) More\s*$", "", text.strip(), flags=re.I)
    d, span = find_date(text)
    if not d:
        return text.strip()
    before = text[: span[0]].strip()
    after = text[span[1]:].strip()
    before = re.sub(r"^(?:(?:%s)\s*)+" % CATEGORY_WORDS, "", before).strip()
    before = re.sub(r"\s*(?:%s)\s*$" % CATEGORY_WORDS, "", before).strip()
    if before:
        return before
    return re.sub(r"^(?:(?:%s)\s*)+" % CATEGORY_WORDS, "", after).strip()


def page_meta(html_text):
    """从文章页里取标题和发布时间（og:title、article:published_time、JSON-LD、<time>）。"""
    def meta(*names):
        for n in names:
            m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']*)["\']' % re.escape(n), html_text, re.I)
            if not m:
                m = re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']%s["\']' % re.escape(n), html_text, re.I)
            if m:
                return htmlmod.unescape(m.group(1)).strip()
        return ""
    title = meta("og:title", "twitter:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.I | re.S)
        title = strip_html(m.group(1)) if m else ""
    title = re.sub(r"\s*[|·–-]\s*(Anthropic|Meta AI|Meta|xAI|IELTS|NVIDIA|Apple)[^|]*$", "", title).strip()
    pub = parse_dt(meta("article:published_time", "og:article:published_time", "publish_date", "date", "pubdate"))
    if not pub:
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html_text)
        pub = parse_dt(m.group(1)) if m else None
    if not pub:
        m = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', html_text, re.I)
        pub = parse_dt(m.group(1)) if m else None
    return {"title": title, "published": pub, "description": meta("og:description", "description")}


def parse_release_notes(html_text):
    """发布说明页：日期做标题（h2/h3/h4），每条以整段加粗的段落或小标题开头。"""
    m = re.search(r"(?is)<article.*?</article>", html_text)
    body = m.group(0) if m else html_text
    tokens = []
    for mm in re.finditer(r"(?is)<h([1-5])[^>]*>(.*?)</h\1>|<p[^>]*>(.*?)</p>|<li[^>]*>(.*?)</li>", body):
        if mm.group(2) is not None:
            tokens.append(("h", strip_html(mm.group(2))))
        else:
            raw = mm.group(3) if mm.group(3) is not None else mm.group(4)
            only_bold = re.fullmatch(r"\s*<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>\s*", raw or "", re.S | re.I)
            txt = strip_html(raw)
            if not txt:
                continue
            tokens.append(("b" if only_bold else "p", txt))
    entries, cur_date, cur = [], None, None
    for kind, txt in tokens:
        d, span = find_date(txt)
        if kind == "h" and d and len(txt) <= 30:
            cur_date, cur = d, None
            continue
        if cur_date is None:
            continue
        if kind in ("b", "h"):
            if kind == "h" and re.fullmatch(r"[A-Z][a-z]+ \d{4}", txt):
                continue
            cur = {"date": cur_date, "title": txt, "snippet": ""}
            entries.append(cur)
        elif kind == "p":
            if cur is None:
                cur = {"date": cur_date, "title": clip(txt, 80), "snippet": ""}
                entries.append(cur)
            elif not cur["snippet"]:
                cur["snippet"] = txt
    return entries


# ---------------------------------------------------------------- 各类型抓取 ----
def fetch_rss(src, ctx):
    status, data, ctype, final = http_get(src["url"], accept="application/rss+xml, application/atom+xml, application/xml, text/xml, */*")
    entries = parse_feed(data)
    return dict(entries=entries, fetched=len(entries), http=status)


def fetch_gnews(src, ctx):
    loc = C.GNEWS_LOCALES[src.get("region", "intl")]
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(dict(q=src["q"], **loc))
    status, data, ctype, final = http_get(url, accept="application/rss+xml, application/xml, text/xml, */*")
    entries = parse_feed(data)
    for e in entries:
        if e["origin"]:
            e["title"] = re.sub(r"\s+[-–—]\s+" + re.escape(e["origin"]) + r"\s*$", "", e["title"])
        e["snippet"] = ""      # Google 新闻的摘要只是标题的重复
    entries = [e for e in entries if len(e["title"].strip(" -–—")) >= 6 and e["title"].strip() != e["origin"]]
    return dict(entries=entries, fetched=len(entries), http=status)


def fetch_page_links(src, ctx):
    status, data, ctype, final = http_get(src["url"], accept="text/html,*/*")
    text = decode_html(data, ctype)
    p = _Anchors(final)
    p.feed(text)
    link_re = re.compile(src["link_re"])
    seen, links = set(), []
    for href, atext in p.out:
        href = href.split("#")[0]
        if not link_re.match(href) or href in seen:
            if href in seen:
                # 同一链接出现多次时，保留文字更长的那个（有的锚点只有图片）
                for i, (h, t) in enumerate(links):
                    if h == href and len(atext) > len(t):
                        links[i] = (h, atext)
            continue
        seen.add(href)
        links.append((href, atext))
    state = ctx["state"].get("pages", {}).get(src["id"], {})
    known = state.get("seen", {})
    baselined = bool(state.get("baselined"))
    now = ctx["now"]
    entries, enrich_budget = [], src.get("enrich_first_run", 6) if not baselined else 6
    new_seen = dict(known)
    for href, atext in links:
        is_new = href not in known
        title = title_from_anchor(atext)
        d, _ = find_date(atext)
        if not d:
            d, _ = find_date(href)
        pub = day_end(d, now) if d else None
        if is_new:
            weak = title.lower() in WEAK_TITLES or len(title) < 6
            if src.get("enrich") and (weak or pub is None) and enrich_budget > 0:
                enrich_budget -= 1
                try:
                    _, pd, pc, _ = http_get(href, accept="text/html,*/*", timeout=25, retries=0)
                    meta = page_meta(decode_html(pd, pc))
                    if meta["title"] and len(meta["title"]) >= 6:
                        title = meta["title"]
                    if meta["published"]:
                        pub = meta["published"]
                except FetchError:
                    pass
            if not title or title.lower() in WEAK_TITLES:
                title = href.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
            new_seen[href] = iso(now)
            # 第一次见到这个页面：只收能确认在窗口内的，其余只记下「见过」
            if not baselined and not (pub and pub >= now - timedelta(hours=C.WINDOW_HOURS)):
                continue
            entries.append(dict(title=title, url=href, published=pub, snippet="", origin="", guid=href,
                                dateOnly=bool(d) and pub == day_end(d, now)))
    if len(new_seen) > 400:
        new_seen = dict(list(new_seen.items())[-400:])
    return dict(entries=entries, fetched=len(links), http=status,
                state_update={"pages": {src["id"]: {"seen": new_seen, "baselined": True}}})


def fetch_release_notes(src, ctx):
    status, data, ctype, final = http_get(src["url"], accept="text/html,*/*")
    entries = []
    parsed = parse_release_notes(decode_html(data, ctype))
    for e in parsed[:20]:
        entries.append(dict(title=e["title"], url=src["url"], published=day_end(e["date"], ctx["now"]),
                            snippet=e["snippet"], origin="", guid="%s|%s" % (e["date"], e["title"]), dateOnly=True))
    return dict(entries=entries, fetched=len(parsed), http=status)


def fetch_hn(src, ctx):
    status, data, _, _ = http_get(src["url"], accept="application/json")
    hits = json.loads(data).get("hits", [])
    entries = []
    for h in hits:
        pts = h.get("points") or 0
        if pts < src.get("min_points", 0) or not h.get("title"):
            continue
        link = h.get("url") or "https://news.ycombinator.com/item?id=%s" % h.get("objectID")
        entries.append(dict(title=h["title"], url=link, published=parse_dt(h.get("created_at")), snippet="", origin="Hacker News",
                            guid=str(h.get("objectID")), meta={"points": pts, "comments": h.get("num_comments") or 0,
                                                              "discussion": "https://news.ycombinator.com/item?id=%s" % h.get("objectID")}))
    return dict(entries=entries, fetched=len(hits), http=status)


def fetch_hf_papers(src, ctx):
    status, data, _, _ = http_get(src["url"], accept="application/json")
    rows = json.loads(data)
    rows.sort(key=lambda r: (r.get("paper") or {}).get("upvotes") or 0, reverse=True)
    entries = []
    for r in rows:
        p = r.get("paper") or {}
        if not p.get("id"):
            continue
        entries.append(dict(title=r.get("title") or p.get("title"), url="https://huggingface.co/papers/%s" % p["id"],
                            published=parse_dt(r.get("publishedAt") or p.get("publishedAt")),
                            snippet=clip(strip_html(r.get("summary") or p.get("summary") or ""), 160), origin="Hugging Face",
                            guid=p["id"], meta={"upvotes": p.get("upvotes") or 0}))
    return dict(entries=entries, fetched=len(rows), http=status)


def fetch_launch_library(src, ctx):
    base = src["url"].rstrip("/")
    entries, http, total = [], None, 0
    for kind, extra in (("upcoming", "limit=12"), ("previous", "limit=8")):
        url = "%s/%s/?lsp__name=SpaceX&mode=list&%s" % (base, kind, extra)
        status, data, _, _ = http_get(url, accept="application/json")
        http = status
        rows = json.loads(data).get("results", [])
        total += len(rows)
        for r in rows:
            net = parse_dt(r.get("net"))
            st = (r.get("status") or {}).get("name") or ""
            name = r.get("name") or ""
            bj = net.astimezone(BJ).strftime("%m-%d %H:%M") if net else "时间待定"
            entries.append(dict(title="SpaceX 发射：%s（%s）" % (name, st), url=r.get("url") or url,
                                published=parse_dt(r.get("last_updated")) or net, snippet="计划 %s（北京时间）" % bj,
                                origin="Launch Library", guid=r.get("id") or name, eventAt=net,
                                meta={"status": st}))
    return dict(entries=entries, fetched=total, http=http)


def fetch_spacex_updates(src, ctx):
    status, data, _, _ = http_get(src["url"], accept="application/json")
    rows = json.loads(data)
    rows = rows.get("data", rows) if isinstance(rows, dict) else rows
    rows = sorted(rows, key=lambda r: r.get("date") or "", reverse=True)
    entries = []
    for r in rows[:12]:
        d, _ = find_date(r.get("date") or "")
        if not d or not r.get("title"):
            continue
        entries.append(dict(title=" ".join(r["title"].split()),
                            url="https://www.spacex.com/updates#%s" % r.get("updateId"), published=day_end(d, ctx["now"]),
                            snippet="", origin="", guid=str(r.get("updateId")), dateOnly=True))
    return dict(entries=entries, fetched=len(rows), http=status)


def fetch_ai_news_radar(src, ctx):
    status, data, _, _ = http_get(src["url"], accept="application/json", timeout=60)
    rows = json.loads(data).get("items", [])
    entries = []
    for r in rows:
        tier = C.RADAR_KEEP_TIERS.get(r.get("source_tier"))
        if not tier or r.get("site_name") in C.RADAR_DROP_SITES or not r.get("ai_is_related", True):
            continue
        title = r.get("title_original") or r.get("title")
        if not title or not r.get("url"):
            continue
        entries.append(dict(title=title, url=r["url"], published=parse_dt(r.get("published_at")), snippet="",
                            origin=r.get("source") or "", guid=r.get("id") or r["url"], tier=tier,
                            region="cn" if re.search(r"[一-鿿]", title) else "intl"))
    return dict(entries=entries, fetched=len(rows), http=status)


def fetch_follow_builders(src, ctx):
    status, data, _, _ = http_get(src["url"], accept="application/json")
    doc = json.loads(data)
    entries = []
    for person in doc.get("x", []):
        handle = person.get("handle") or ""
        for t in person.get("tweets", []):
            txt = re.sub(r"https?://\S+", "", t.get("text") or "")
            txt = " ".join(txt.split())
            if len(txt) < 40 or not t.get("url"):
                continue
            entries.append(dict(title="@%s：%s" % (handle, clip(txt, 110)), url=t["url"], published=parse_dt(t.get("createdAt")),
                                snippet="", origin="X @%s" % handle, guid=str(t.get("id")),
                                meta={"likes": t.get("likes") or 0}))
    return dict(entries=entries, fetched=len(entries), http=status)


FETCHERS = {
    "rss": fetch_rss, "gnews": fetch_gnews, "page_links": fetch_page_links, "release_notes": fetch_release_notes,
    "hn": fetch_hn, "hf_papers": fetch_hf_papers, "launch_library": fetch_launch_library,
    "spacex_updates": fetch_spacex_updates, "ai_news_radar": fetch_ai_news_radar, "follow_builders": fetch_follow_builders,
}


def fetch_source(src, ctx):
    t0 = time.time()
    res = dict(entries=[], fetched=0, http=None, error=None, ms=0)
    try:
        r = FETCHERS[src["type"]](src, ctx)
        res.update(r)
    except FetchError as e:
        res["error"], res["http"] = str(e), e.status
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError) as e:
        res["error"] = "数据解析失败：%s %s" % (type(e).__name__, str(e)[:100])
    except Exception as e:  # 单个源出错不能拖垮整次抓取
        res["error"] = "意外错误：%s %s" % (type(e).__name__, str(e)[:100])
    res["ms"] = int((time.time() - t0) * 1000)
    return res


# ---------------------------------------------------------------- 打标 ----
def tag_item(src, title, snippet, region=None):
    both = "%s %s" % (title, snippet)
    ai = bool(C.AI_RE.search(both))
    watch = list(src.get("watch") or [])
    req = src.get("watch_requires")
    if (req == "ai" and not ai) or (req == "study" and not C.STUDY_RE.search(both)):
        watch = []
    for name, rx in C.WATCH_RULES:
        if rx.search(title) and name not in watch:
            watch.append(name)
    if C.EDU_RE.search(both) and ai and "AI与教育" not in watch:
        watch.append("AI与教育")
    if C.STUDY_ABROAD_RE.search(both) and "留学与签证政策" not in watch:
        watch.append("留学与签证政策")
    if C.LANG_RE.search(title) and "英语教学与语言培训行业" not in watch:
        watch.append("英语教学与语言培训行业")
    topics = [n for n, rx in C.TOPIC_RULES if rx.search(title)]
    if src.get("layer") == 3:
        layer = 3
    elif any(w in C.LAYER1 for w in watch):
        layer = 1
    elif topics:
        layer = 2
    else:
        layer = src.get("layer", 0) if src.get("layer") == 2 else 0
    flags = []
    if src.get("rumor_prone"):
        flags.append("rumor")
    if C.MONEY_PEOPLE_RE.search(title):
        flags.append("money_people")
    region = region or src.get("region", "intl")
    if region == "cn" and not (set(watch) & C.EDU_EXEMPT):
        flags.append("domestic")
    return watch, topics, layer, flags


def build_item(src, e, now, prev):
    pub = e.get("published")
    if pub and (pub.hour, pub.minute, pub.second) == (0, 0, 0) and not e.get("eventAt"):
        e = dict(e, published=day_end(pub.date(), now), dateOnly=True)      # 只有日期的发布时间，按当天结束算
    url = norm_url(e["url"], keep_fragment=src["type"] == "spacex_updates")
    title = " ".join(e["title"].split())
    key = e.get("guid") if src["type"] in ("launch_library", "release_notes", "hn", "hf_papers") else url
    iid = item_id(src["id"], key or url)
    snippet = clip(e.get("snippet", ""), 160)
    watch, topics, layer, flags = tag_item(src, title, snippet, e.get("region"))
    if src.get("keep_only_tagged") and not (watch or topics):
        return None
    old = prev.get(iid, {})
    it = dict(id=iid, title=clip(title, 200), url=url, publishedAt=iso(e.get("published")),
              firstSeen=old.get("firstSeen") or iso(now), source=src["id"], sourceName=src["name"],
              tier=e.get("tier") or src["tier"], role=src["role"], region=e.get("region") or src.get("region", "intl"),
              layer=layer, watch=watch, topics=topics, flags=flags)
    if e.get("dateOnly"):
        it["dateOnly"] = True
    if snippet:
        it["snippet"] = snippet
    if e.get("origin"):
        it["origin"] = e["origin"]
    if e.get("eventAt"):
        it["eventAt"] = iso(e["eventAt"])
    if e.get("meta"):
        it["meta"] = e["meta"]
    return it


def in_window(it, now):
    lo = now - timedelta(hours=C.WINDOW_HOURS)
    if it.get("eventAt"):
        ev = parse_dt(it["eventAt"])
        return bool(ev) and lo <= ev <= now + timedelta(days=7)
    t = parse_dt(it.get("publishedAt")) or parse_dt(it.get("firstSeen"))
    return bool(t) and t >= lo


def sort_key(it):
    return parse_dt(it.get("eventAt")) or parse_dt(it.get("publishedAt")) or parse_dt(it.get("firstSeen")) or datetime.min.replace(tzinfo=UTC)


# ---------------------------------------------------------------- 主流程 ----
def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_items(path, generated, items):
    lines = ",\n".join("  " + json.dumps(i, ensure_ascii=False, separators=(",", ":")) for i in items)
    head = '{"generatedAt":"%s","windowHours":%d,"count":%d,"items":[\n' % (generated, C.WINDOW_HOURS, len(items))
    Path(path).write_text(head + lines + "\n]}\n", encoding="utf-8")


def run(sources, out_dir, dry=False):
    now = now_utc()
    prev_doc = load_json(out_dir / "items.json", {})
    prev = {i["id"]: i for i in prev_doc.get("items", []) if "id" in i}
    state = load_json(out_dir / "state.json", {"pages": {}})
    prev_status = {s["id"]: s for s in load_json(out_dir / "source-status.json", {}).get("sources", [])}
    ctx = {"now": now, "state": state}

    results = {}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_source, s, ctx): s for s in sources}
        for f in cf.as_completed(futs):
            results[futs[f]["id"]] = f.result()

    merged = dict(prev)
    per_source_new = {}
    for src in sources:
        r = results[src["id"]]
        if r.get("state_update"):
            for k, v in r["state_update"].items():
                state.setdefault(k, {}).update(v)
        entries = sorted(r["entries"], key=lambda e: e.get("published") or now, reverse=True)
        entries = entries[: src.get("limit", 60)] if src["type"] != "page_links" else entries
        fresh = set()
        for e in entries:
            it = build_item(src, e, now, prev)
            if not it or not in_window(it, now):
                continue
            if it["id"] not in prev:
                fresh.add(it["id"])
            merged[it["id"]] = it
        n_new = len(fresh)
        per_source_new[src["id"]] = n_new

    items = [i for i in merged.values() if in_window(i, now)]
    items.sort(key=sort_key, reverse=True)

    counts = {}
    for i in items:
        counts[i["source"]] = counts.get(i["source"], 0) + 1
    statuses = []
    for src in sources:
        r = results[src["id"]]
        old = prev_status.get(src["id"], {})
        ok = r["error"] is None
        st = dict(id=src["id"], name=src["name"], type=src["type"], url=src.get("url") or src.get("q"),
                  tier=src["tier"], ok=ok, http=r.get("http"), error=r["error"], fetched=r["fetched"],
                  inWindow=counts.get(src["id"], 0), new=per_source_new.get(src["id"], 0), ms=r["ms"],
                  lastOkAt=iso(now) if ok else old.get("lastOkAt"),
                  failStreak=0 if ok else (old.get("failStreak", 0) + 1))
        if ok and r["fetched"] == 0:
            st["warn"] = "解析到 0 条，页面或订阅源结构可能变了"
        statuses.append(st)
    # 这次没跑的源（--only 调试时）保留上次的状态
    ran = {s["id"] for s in statuses}
    statuses += [s for sid, s in prev_status.items() if sid not in ran]
    ok_n = sum(1 for s in statuses if s["ok"])
    status_doc = dict(generatedAt=iso(now), summary=dict(sources=len(statuses), ok=ok_n, failed=len(statuses) - ok_n,
                                                         items=len(items)), sources=statuses)

    if not dry:
        out_dir.mkdir(parents=True, exist_ok=True)
        write_items(out_dir / "items.json", iso(now), items)
        (out_dir / "source-status.json").write_text(json.dumps(status_doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (out_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return items, status_doc


def print_report(items, status_doc, only_ran=None):
    print("\n%-22s %-4s %-6s %-6s %-5s %-6s %s" % ("源", "结果", "抓到", "窗口内", "新增", "耗时ms", "说明"))
    for s in status_doc["sources"]:
        if only_ran and s["id"] not in only_ran:
            continue
        mark = "OK" if s["ok"] and not s.get("warn") else ("WARN" if s["ok"] else "FAIL")
        note = s.get("error") or s.get("warn") or ""
        print("%-22s %-4s %-6s %-6s %-5s %-6s %s" % (s["id"], mark, s["fetched"], s["inWindow"], s["new"], s["ms"], note))
    sm = status_doc["summary"]
    print("\n共 %d 个源：成功 %d，失败 %d；收件箱现有 %d 条（最近 %d 小时）" % (sm["sources"], sm["ok"], sm["failed"], sm["items"], C.WINDOW_HOURS))


def main():
    ap = argparse.ArgumentParser(description="抓取 Signal 收件箱")
    ap.add_argument("--only", help="只抓这些源，逗号分隔")
    ap.add_argument("--dry-run", action="store_true", help="只打印结果，不写文件")
    ap.add_argument("--list", action="store_true", help="列出全部源")
    ap.add_argument("--out", default=str(INBOX), help="输出目录（默认 data/inbox）")
    args = ap.parse_args()
    sources = [s for s in C.SOURCES if s.get("enabled", True)]
    if args.list:
        for s in sources:
            print("%-22s %-14s %s" % (s["id"], s["type"], s.get("url") or s.get("q")))
        return 0
    only = None
    if args.only:
        only = {x.strip() for x in args.only.split(",") if x.strip()}
        unknown = only - {s["id"] for s in sources}
        if unknown:
            print("不认识的源：%s" % ", ".join(sorted(unknown)), file=sys.stderr)
            return 2
        sources = [s for s in sources if s["id"] in only]
    items, status_doc = run(sources, Path(args.out), dry=args.dry_run)
    print_report(items, status_doc, only_ran=only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
