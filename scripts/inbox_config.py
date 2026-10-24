"""收件箱的信源清单和打标规则。

watchlist.md 决定「关注什么」，这个文件决定「去哪儿抓、怎么贴标签」。
加一个源 = 在 SOURCES 里加一行；删一个源 = 删一行（或把 enabled 设成 False）。

字段说明（SOURCES 里每一项）：
  id        唯一英文名，用在条目 id 和 source-status 里
  name      给人看的名字
  type      rss | gnews | page_links | release_notes | hn | hf_papers | launch_library
            | spacex_updates | ai_news_radar | follow_builders
            | changelog_update | changelog_api | changelog_codex   （产品更新日志，三种页面格式）
  url       地址（gnews 用 q 代替）
  tier      来源层级，沿用 sources.md 的五层：1 官方一手，3 主流媒体，4 AI 与教育，5 查漏
  role      primary = 条目链接就是原文，可以当出处；lead = 只是线索（聚合、中转、个人账号），出处要回到原文
  region    intl | cn（国内消息只在「质的突破」时收，教育/留学/语培三项例外，见 watchlist.md）
  watch     这个源默认归到关注清单里的哪些对象
  layer     没有命中任何对象时的默认层：2 雷达领域，3 日程，0 清单外
  watch_requires  "ai" / "study"：只有标题或摘要里出现对应关键词，才贴上默认的 watch
  default_topics  这个源的题材完全对口时，所有条目直接贴上这些雷达领域标签（如 ["自动驾驶"]）
  stale_days  抓取成功但最新一条超过这么多天就在状态里标 stale，默认 STALE_DAYS
  keep_only_tagged  True：没贴上任何 watch/topic 的条目直接丢掉（用于信息量大的综合源）
  rumor_prone  True：爆料类来源，按传闻规则处理
  limit     每次最多取多少条（取最新的）
  kind      "changelog"：产品更新日志，条目会带 kind 标记，inbox_view 单独列成「功能更新候选」，供「功能更新」板块挑选
  label / link   （changelog_* 专用）条目标题前缀 / 条目指向的网页（url 是拿来抓的 Markdown 版，链接要给人看的页面）
  take      （changelog_* 专用）只看页面最前面多少条（页面很长，窗口只有 48 小时）
"""
import re

WINDOW_HOURS = 48
STALE_DAYS = 30        # 抓取成功但最新一条超过这么多天，状态里标 stale（单个源可用 stale_days 覆盖）

# ---- 谷歌新闻过滤（2026-10-24 信源复盘后加）----
# 谷歌新闻占收件箱八成以上，其中大量是股价、财经转载。用户不看融资、人事和股价（watchlist.md「不看的」）。
# 1) 整个发布方都是股票/投资内容的，直接丢；
# 2) 标题带股价字眼的（stock、price target、NASDAQ: 等）丢，除非发布方是正经通讯社/大媒体（它们的「stock」多半是在说公司大事）。
GN_DROP_ORIGINS = {
    "the motley fool", "marketbeat", "biggo finance", "seeking alpha", "24/7 wall st.", "orcarouter",
    "tech-insider.org", "https://tech-insider.org/", "simply wall st", "simply wall street", "zacks investment research",
    "stocktwits", "gurufocus", "tipranks", "investorplace", "barchart.com", "insider monkey", "finbold",
    "moomoo", "tradingkey", "kalkine media", "kalkine.ca", "stocks down under", "marketscreener.com",
    "indexbox", "economies.com", "fxleaders", "thestreet",
}
GN_KEEP_ORIGINS = {
    "reuters", "bloomberg.com", "bloomberg", "cnbc", "the wall street journal", "financial times", "the verge",
    "techcrunch", "ars technica", "wired", "the information", "axios", "fortune", "the new york times", "bbc",
    "the guardian", "the washington post", "associated press", "ap news", "the economist",
}
GN_STOCK_RE = re.compile(
    r"\b(stock|stocks|share price|price target|buy rating|dividend|etfs?|should you buy|buy now|market cap)\b"
    r"|\b(nasdaq|nyse)\s?:", re.I)
USER_AGENT = ("Mozilla/5.0 (compatible; SignalInbox/1.0; "
              "+https://github.com/2593040259zhangzhenning-blip/daily-ai-news)")


def W(expr):
    """英文词边界：不用 \\b，因为 \\b 在「AI时代」这种中英相连的地方不起作用。"""
    return r"(?<![A-Za-z0-9])(?:" + expr + r")(?![A-Za-z0-9])"


# ---- 关键词规则 ----------------------------------------------------------
AI_RE = re.compile(
    W(r"AI|A\.I\.|artificial intelligence|(?i:generative)|(?i:genai)|LLMs?|(?i:chatbots?)|ChatGPT|GPT-?\d[\w.\-]*|Claude|Gemini|Copilot|(?i:machine learning)")
    + r"|人工智能|大模型|AIGC|智能体|生成式|大语言模型")

STUDY_RE = re.compile(
    r"(?i)student|study|studying|graduate route|university|universities|college|IELTS|TOEFL|English language|"
    r"post-study|education|学生|留学|学签|雅思|托福")

# 关注清单第一层：盯死的对象
WATCH_RULES = [
    ("Anthropic/Claude", re.compile(r"(?i)" + W(r"Anthropic|Claude(?: Code| Cowork)?|Mythos|Dario Amodei"))),
    ("OpenAI/ChatGPT", re.compile(r"(?i)" + W(r"OpenAI|ChatGPT|Sora|Codex|Sam Altman|GPT-?\d[\w.\-]*"))),
    ("Google/Gemini", re.compile(r"(?i)" + W(r"Gemini|DeepMind|Gemma|NotebookLM|Google AI|Veo|Nano Banana|Google Research"))),
    ("Meta/Muse", re.compile(
        r"(?-i:" + W(r"Muse(?: Spark| Wonder| Image| Video| Spark Open)?|Meta AI|Meta Superintelligence|Meta Platforms|MSL|Llama|Meta") + r")"
        r"(?!\s*-?\s*(?i:data|analysis|verse))")),
    ("英伟达", re.compile(r"(?i)" + W(r"Nvidia|GTC|Jensen Huang|Blackwell|CUDA") + r"|英伟达|黄仁勋")),
    ("苹果", re.compile(r"(?i)" + W(r"Apple|iPhone|iPad|MacBook|Mac|iOS ?\d+[\w.]*|iPadOS|macOS|visionOS|watchOS|Siri|WWDC|Apple Intelligence|Tim Cook") + r"|苹果")),
    ("SpaceX", re.compile(r"(?i)" + W(r"SpaceX|Starship|Starlink|Falcon ?(?:9|Heavy)|Starbase") + r"|星舰")),
]

# 教育、留学、语培：靠关键词组合判断（来源本身是教育类媒体的，用 watch_requires 控制）
EDU_RE = re.compile(
    r"(?i)" + W(r"education|edtech|classrooms?|teachers?|students?|universit(?:y|ies)|schools?|tutoring|curriculum|campus|ChatGPT Edu|higher ed(?:ucation)?")
    + r"|教育|高校|学生|教师|课堂|大学|学校|校长|教学|中小学|课程|教材")
STUDY_ABROAD_RE = re.compile(
    r"(?i)study abroad|international students?|student visas?|graduate route|post-study work|IELTS|TOEFL|"
    r"QS World University Rankings|visa (?:rules|policy|changes|requirements)|studying overseas|"
    r"留学|雅思|托福|学签|留学生|签证")
LANG_RE = re.compile(
    r"(?i)" + W(r"Duolingo|New Oriental|EF Education First|(?:English|language) (?:teaching|learning|training|tutoring)|ELT|TESOL") +
    r"|多邻国|新东方|英语培训|英语教学|语言培训|雅思口语")

# 第二层：雷达领域
TOPIC_RULES = [
    ("人形机器人", re.compile(r"(?i)" + W(r"humanoids?|Optimus|Figure AI|Unitree|Boston Dynamics|Agility Robotics|Apptronik|1X NEO|UBTech|Agibot|AgiBot|Sanctuary AI|Neura Robotics|Figure 0\d") + r"|人形机器人|宇树")),
    ("芯片", re.compile(r"(?i)" + W(r"chips?|semiconductors?|GPUs?|TPUs?|HBM\d*|foundry|TSMC|ASML|wafers?|Cerebras|Groq|AMD|Intel|Qualcomm|Broadcom") + r"|芯片|半导体|光刻")),
    ("自动驾驶", re.compile(r"(?i)" + W(r"robotaxis?|self-driving|autonomous (?:driving|vehicles?|cars?)|Waymo|FSD|Full Self-Driving|Zoox|Pony\.ai|WeRide|Apollo Go") + r"|自动驾驶|无人驾驶|萝卜快跑")),
    ("脑机接口", re.compile(r"(?i)brain-computer interface|brain computer interface|" + W(r"BCI|Neuralink|Synchron|Paradromics|Precision Neuroscience") + r"|脑机接口")),
    ("AI全行业", re.compile(r"(?i)" + W(r"xAI|Grok|Mistral|Perplexity|Cohere|Midjourney|Stability AI|Hugging Face|Safe Superintelligence|Thinking Machines|Microsoft AI|Amazon Nova|Runway") )),
]

# 不看的：融资、人事、股价（除非直接影响用户在用的产品，这一步只做提示，由定时任务判断）
MONEY_PEOPLE_RE = re.compile(
    r"(?i)" + W(r"raises?|raised|funding round|Series [A-G]|valuation|IPO|stock|shares|share price|stake|appoints?|hires?|"
                r"departs?|steps? down|poach(?:es|ed)?|layoffs?|acquires?|acquisition|buyout") +
    r"|融资|估值|股价|上市|任命|离职|跳槽|裁员|收购")

LAYER1 = {"Anthropic/Claude", "OpenAI/ChatGPT", "Google/Gemini", "Meta/Muse", "英伟达", "苹果", "SpaceX",
          "AI与教育", "留学与签证政策", "英语教学与语言培训行业"}
EDU_EXEMPT = {"AI与教育", "留学与签证政策", "英语教学与语言培训行业"}   # 国内消息也照常收的三项
RADAR = {"人形机器人", "芯片", "自动驾驶", "脑机接口", "AI全行业"}

# ---- 信源清单 ------------------------------------------------------------
def _gn(sid, name, q, watch=(), layer=2, region="intl", limit=15, requires=None, keep=False, topic=None):
    d = dict(id=sid, name=name, type="gnews", q=q, tier=5, role="lead", region=region,
             watch=list(watch), layer=layer, limit=limit, watch_requires=requires, keep_only_tagged=keep)
    if topic:
        d["topic"] = topic        # 谷歌新闻「头条」栏目（TECHNOLOGY / SCIENCE），不是关键词搜索
    return d


SOURCES = [
    # ===== 第一层 · 官方一手 =====
    dict(id="openai", name="OpenAI 官网", type="rss", url="https://openai.com/news/rss.xml",
         tier=1, role="primary", region="intl", watch=["OpenAI/ChatGPT"], limit=40),
    # 已停用（2026-10-17）：help.openai.com 对所有机房 IP 返回 Cloudflare 人机验证（403），GitHub 上抓不到。
    # 改由早晚定时任务用网页读取工具直接读这个页面，见 tasks/morning.md 第 5 步。
    dict(id="chatgpt-notes", name="ChatGPT 发布说明", type="release_notes", enabled=False,
         url="https://help.openai.com/en/articles/6825453-chatgpt-release-notes",
         tier=1, role="primary", region="intl", watch=["OpenAI/ChatGPT"], kind="changelog"),
    # 2026-10-18 新增：OpenAI 的另外两份更新日志。ChatGPT 桌面端 / Codex 的页面原先在 developers.openai.com/codex/changelog，
    # 现在跳转到 learn.chatgpt.com；GitHub 发版镜像（Codex CLI 0.xxx 这类）不收，只收官方写的条目。
    dict(id="openai-chatgpt-codex-changelog", name="ChatGPT 与 Codex 更新日志（OpenAI）", type="changelog_codex",
         url="https://learn.chatgpt.com/docs/changelog", link="https://learn.chatgpt.com/docs/changelog", take=40,
         tier=1, role="primary", region="intl", watch=["OpenAI/ChatGPT"], kind="changelog", limit=30),
    dict(id="openai-api-changelog", name="OpenAI API 更新日志", type="changelog_api",
         url="https://developers.openai.com/api/docs/changelog.md", link="https://developers.openai.com/api/docs/changelog",
         take=15, tier=1, role="primary", region="intl", watch=["OpenAI/ChatGPT"], kind="changelog", limit=15),
    dict(id="anthropic-news", name="Anthropic 新闻页", type="page_links", url="https://www.anthropic.com/news",
         link_re=r"^https://www\.anthropic\.com/news/[a-z0-9\-]+$", fix_relative="https://www.anthropic.com",
         enrich=True, tier=1, role="primary", region="intl", watch=["Anthropic/Claude"]),
    dict(id="claude-notes", name="Claude 发布说明", type="release_notes",
         url="https://support.claude.com/en/articles/12138966-release-notes",
         tier=1, role="primary", region="intl", watch=["Anthropic/Claude"], kind="changelog"),
    # 2026-10-18 新增：Claude Code 更新日志（逐版本，官方文档站，内容来自 GitHub CHANGELOG.md）和每周摘要
    # （就是邮件里的 "This week in Claude Code"；摘要页 9 月中旬之后没再更新，所以只当补充）。
    # 抓的是页面的 Markdown 版（网址后加 .md），比 HTML 好解析；条目链接指向给人看的页面。
    dict(id="claude-code-changelog", name="Claude Code 更新日志", type="changelog_update",
         url="https://code.claude.com/docs/en/changelog.md", link="https://code.claude.com/docs/en/changelog",
         label="Claude Code", take=15, tier=1, role="primary", region="intl", watch=["Anthropic/Claude"],
         kind="changelog", limit=15),
    dict(id="claude-code-weekly", name="Claude Code 每周摘要", type="changelog_update",
         url="https://code.claude.com/docs/en/whats-new.md", link="https://code.claude.com/docs/en/whats-new",
         label="Claude Code 每周摘要", range_dates=True, take=4, stale_days=60, tier=1, role="primary", region="intl",
         watch=["Anthropic/Claude"], kind="changelog", limit=4),
    dict(id="deepmind", name="Google DeepMind 博客", type="rss", url="https://deepmind.google/blog/rss.xml",
         tier=1, role="primary", region="intl", watch=["Google/Gemini"], limit=30),
    dict(id="google-ai", name="Google AI 栏目", type="rss",
         url="https://blog.google/innovation-and-ai/technology/ai/rss/",
         tier=1, role="primary", region="intl", watch=["Google/Gemini"], limit=30),
    dict(id="google-research", name="Google Research 博客", type="rss", url="https://research.google/blog/rss/",
         tier=1, role="primary", region="intl", watch=["Google/Gemini"], limit=20),
    dict(id="meta-ai", name="Meta AI 博客", type="page_links", url="https://ai.meta.com/blog/",
         link_re=r"^https://ai\.meta\.com/blog/[a-z0-9\-]+/?$", enrich=True, enrich_first_run=8,
         tier=1, role="primary", region="intl", watch=["Meta/Muse"]),
    dict(id="nvidia-blog", name="英伟达博客", type="rss", url="https://blogs.nvidia.com/feed/",
         tier=1, role="primary", region="intl", watch=["英伟达"], limit=30),
    dict(id="nvidia-news", name="英伟达新闻中心", type="rss", url="https://nvidianews.nvidia.com/releases.xml",
         tier=1, role="primary", region="intl", watch=["英伟达"], limit=30),
    dict(id="xai-news", name="xAI 新闻页", type="page_links", url="https://x.ai/news",
         link_re=r"^https://x\.ai/news/[a-z0-9\-]+/?$", enrich=True, enrich_first_run=6,
         tier=1, role="primary", region="intl", watch=[], layer=2),
    dict(id="apple-newsroom", name="Apple Newsroom", type="rss", url="https://www.apple.com/newsroom/rss-feed.rss",
         tier=1, role="primary", region="intl", watch=["苹果"], limit=30),
    dict(id="apple-dev-releases", name="Apple 开发者版本发布", type="rss",
         url="https://developer.apple.com/news/releases/rss/releases.rss",
         tier=1, role="primary", region="intl", watch=["苹果"], limit=30),
    dict(id="apple-dev-news", name="Apple 开发者新闻", type="rss", url="https://developer.apple.com/news/rss/news.rss",
         tier=1, role="primary", region="intl", watch=["苹果"], limit=30),
    dict(id="macrumors", name="MacRumors", type="rss", url="https://feeds.macrumors.com/MacRumors-All",
         tier=3, role="primary", region="intl", watch=["苹果"], rumor_prone=True, limit=30),
    dict(id="9to5mac", name="9to5Mac", type="rss", url="https://9to5mac.com/feed/",
         tier=3, role="primary", region="intl", watch=["苹果"], rumor_prone=True, limit=30),
    dict(id="spacex-updates", name="SpaceX 官网更新", type="spacex_updates",
         url="https://content.spacex.com/api/spacex-website/updates",
         tier=1, role="primary", region="intl", watch=["SpaceX"]),
    dict(id="spacex-launches", name="SpaceX 发射日程（Launch Library）", type="launch_library",
         url="https://ll.thespacedevs.com/2.3.0/launches/", tier=3, role="primary", region="intl",
         watch=["SpaceX"], layer=3),
    dict(id="hf-blog", name="Hugging Face 博客", type="rss", url="https://huggingface.co/blog/feed.xml",
         tier=1, role="primary", region="intl", watch=[], layer=2, limit=20),
    dict(id="mistral", name="Mistral 新闻", type="rss", url="https://mistral.ai/news/rss",
         tier=1, role="primary", region="intl", watch=[], layer=2, limit=20),

    # ===== 教育 / 留学 / 语培（国内外都看）=====
    dict(id="edsurge", name="EdSurge", type="rss", url="https://www.edsurge.com/articles_rss",
         tier=4, role="primary", region="intl", watch=["AI与教育"], watch_requires="ai", keep_only_tagged=True, limit=40),
    dict(id="insidehighered", name="Inside Higher Ed", type="rss", url="https://www.insidehighered.com/rss.xml",
         tier=4, role="primary", region="intl", watch=["AI与教育"], watch_requires="ai", keep_only_tagged=True, limit=40),
    dict(id="ukvi", name="英国签证与移民局（GOV.UK）", type="rss",
         url="https://www.gov.uk/government/organisations/uk-visas-and-immigration.atom",
         tier=1, role="primary", region="intl", watch=["留学与签证政策"], watch_requires="study", keep_only_tagged=True, limit=40),
    dict(id="icef", name="ICEF Monitor", type="rss", url="https://monitor.icef.com/feed/",
         tier=4, role="primary", region="intl", watch=["留学与签证政策"], limit=30),
    dict(id="pie-news", name="The PIE News", type="rss", url="https://thepienews.com/feed/",
         tier=4, role="primary", region="intl", watch=["留学与签证政策"], limit=30),
    dict(id="ielts", name="雅思官方（IELTS）", type="page_links", url="https://ielts.org/news-and-insights",
         link_re=r"^https://ielts\.org/news-and-insights/[a-z0-9\-]+$",
         tier=1, role="primary", region="intl", watch=["留学与签证政策"]),
    # 2026-10-24 停用：博客全是教语法、下棋的内容营销，一周 4 条线索没有一条是新闻；多邻国真正的动向由谷歌新闻的语言学习两个查询覆盖
    dict(id="duolingo", name="多邻国博客", type="rss", url="https://blog.duolingo.com/feed/", enabled=False,
         tier=1, role="primary", region="intl", watch=["英语教学与语言培训行业"], limit=20),
    dict(id="moe", name="教育部（工作动态）", type="page_links", url="http://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/",
         link_re=r"^https?://www\.moe\.gov\.cn/.*/t\d{8}_\d+\.html$", fix_relative="http://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/",
         tier=1, role="primary", region="cn", watch=["AI与教育"], watch_requires="ai", keep_only_tagged=True),
    dict(id="jyb", name="中国教育报", type="page_links", url="http://www.jyb.cn/",
         link_re=r"^https?://www\.jyb\.cn/.*/t\d{8}_\d+\.html$", watch=["AI与教育"], watch_requires="ai",
         keep_only_tagged=True, tier=4, role="primary", region="cn"),

    # ===== 第三层 · 主流媒体 =====
    dict(id="techcrunch-ai", name="TechCrunch AI", type="rss",
         url="https://techcrunch.com/category/artificial-intelligence/feed/",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=30),
    dict(id="verge-ai", name="The Verge AI", type="rss", url="https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=30),
    dict(id="ars-ai", name="Ars Technica AI", type="rss", url="https://arstechnica.com/ai/feed/",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=30),
    dict(id="wired-ai", name="Wired AI", type="rss", url="https://www.wired.com/feed/tag/ai/latest/rss",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=30),
    dict(id="mit-tr-ai", name="MIT Technology Review AI", type="rss",
         url="https://www.technologyreview.com/topic/artificial-intelligence/feed",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=20),
    dict(id="the-decoder", name="The Decoder", type="rss", url="https://the-decoder.com/feed/",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=30),
    dict(id="qbitai", name="量子位", type="rss", url="https://www.qbitai.com/feed",
         tier=3, role="primary", region="cn", watch=[], layer=2, limit=30),

    # ===== 雷达领域专业源（2026-10-24 信源复盘后加，订阅源都已逐个验证能读、仍在更新）=====
    # 这些源题材比雷达领域宽，所以用 keep_only_tagged：标题没命中 TOPIC_RULES 的丢掉；
    # 题材完全对口的（Waymo 官方博客、IEEE 半导体）用 default_topics 直接贴标签。
    dict(id="robot-report", name="The Robot Report", type="rss", url="https://www.therobotreport.com/feed/",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=30, keep_only_tagged=True),
    dict(id="ieee-robotics", name="IEEE Spectrum 机器人", type="rss", url="https://spectrum.ieee.org/feeds/topic/robotics.rss",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=30, keep_only_tagged=True),
    dict(id="tc-robotics", name="TechCrunch 机器人", type="rss", url="https://techcrunch.com/category/robotics/feed/",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=20, keep_only_tagged=True),
    dict(id="waymo", name="Waymo 官方博客", type="rss", url="https://waymo.com/blog/rss.xml",
         tier=1, role="primary", region="intl", watch=[], layer=2, limit=15, default_topics=["自动驾驶"]),
    dict(id="electrek", name="Electrek", type="rss", url="https://electrek.co/feed/",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=50, keep_only_tagged=True),
    dict(id="tc-transport", name="TechCrunch 交通", type="rss", url="https://techcrunch.com/category/transportation/feed/",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=20, keep_only_tagged=True),
    dict(id="verge-transport", name="The Verge 交通", type="rss", url="https://www.theverge.com/rss/transportation/index.xml",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=10, keep_only_tagged=True),
    dict(id="ieee-semis", name="IEEE Spectrum 半导体", type="rss", url="https://spectrum.ieee.org/feeds/topic/semiconductors.rss",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=30, default_topics=["芯片"]),
    dict(id="eetimes", name="EE Times", type="rss", url="https://www.eetimes.com/feed/",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=20, keep_only_tagged=True),
    dict(id="ieee-biomed", name="IEEE Spectrum 生物医学", type="rss", url="https://spectrum.ieee.org/feeds/topic/biomedical.rss",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=30, keep_only_tagged=True),
    dict(id="stat-neuro", name="STAT 神经科学", type="rss", url="https://www.statnews.com/topic/neuroscience/feed/",
         tier=3, role="primary", region="intl", watch=[], layer=2, limit=20, keep_only_tagged=True),

    # ===== 第五层 · 查漏（只当线索）=====
    dict(id="techmeme", name="Techmeme", type="rss", url="https://www.techmeme.com/feed.xml",
         tier=5, role="lead", region="intl", watch=[], layer=0, limit=50),
    dict(id="hn", name="Hacker News 首页（≥100 分）", type="hn",
         url="https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=40",
         tier=5, role="lead", region="intl", watch=[], layer=0, min_points=100),
    dict(id="hf-papers", name="Hugging Face 每日论文（前 12）", type="hf_papers",
         url="https://huggingface.co/api/daily_papers", tier=5, role="lead", region="intl",
         watch=[], layer=0, limit=12),
    dict(id="ai-news-radar", name="AI News Radar（中转站）", type="ai_news_radar",
         url="https://raw.githubusercontent.com/LearnPrompt/ai-news-radar/master/data/latest-24h.json",
         tier=5, role="lead", region="intl", watch=[], layer=0, limit=200),
    dict(id="follow-builders", name="Follow Builders（AI 圈人物 X）", type="follow_builders",
         url="https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json",
         tier=5, role="lead", region="intl", watch=[], layer=0, limit=60),

    # ===== Google 新闻关键词搜索（共识判断 + 清单外线索；链接是跳转地址，只当线索）=====
    # 圈外位的来源：谷歌新闻科技、科学两个头条栏目。关键词搜索都是清单内的，清单外的大事只能靠这种「编辑挑的头条」发现；
    # 它们在共识打分里只算一张编辑票（consensus.EDITOR_SOURCES），不当出处。layer=0：没命中清单就是清单外。
    _gn("gn-top-tech", "Google 新闻头条：科技", "", layer=0, limit=40, topic="TECHNOLOGY"),
    _gn("gn-top-science", "Google 新闻头条：科学", "", layer=0, limit=30, topic="SCIENCE"),
    _gn("gn-anthropic", "Google 新闻：Anthropic / Claude", "Anthropic OR Claude when:2d", ["Anthropic/Claude"], layer=1),
    _gn("gn-openai", "Google 新闻：OpenAI / ChatGPT", "OpenAI OR ChatGPT when:2d", ["OpenAI/ChatGPT"], layer=1),
    _gn("gn-google", "Google 新闻：Gemini / DeepMind", "Gemini OR DeepMind when:2d", ["Google/Gemini"], layer=1),
    _gn("gn-meta", "Google 新闻：Meta AI / Muse", '"Meta AI" OR "Muse Spark" OR "Meta Superintelligence" when:2d', ["Meta/Muse"], layer=1),
    _gn("gn-nvidia", "Google 新闻：英伟达", "Nvidia when:2d", ["英伟达"], layer=1),
    _gn("gn-apple", "Google 新闻：苹果", 'Apple (iPhone OR iOS OR macOS OR "Apple Intelligence") when:2d', ["苹果"], layer=1),
    _gn("gn-spacex", "Google 新闻：SpaceX", "SpaceX OR Starship when:2d", ["SpaceX"], layer=1),
    _gn("gn-xai-mistral", "Google 新闻：xAI / Mistral 等海外 AI 公司", "xAI OR Grok OR Mistral OR Perplexity when:2d"),
    _gn("gn-humanoid", "Google 新闻：人形机器人", "humanoid robot when:2d"),
    _gn("gn-chips", "Google 新闻：芯片", '"AI chip" OR semiconductor OR TSMC OR HBM when:2d'),
    _gn("gn-autonomy", "Google 新闻：自动驾驶", 'robotaxi OR Waymo OR "self-driving" when:2d'),
    _gn("gn-bci", "Google 新闻：脑机接口", '"brain-computer interface" OR Neuralink when:2d'),
    _gn("gn-edu-ai", "Google 新闻：AI 与教育", '"AI" education OR "ChatGPT Edu" OR "Claude for Education" OR "Gemini for Education" when:2d',
        ["AI与教育"], layer=1, requires="ai", keep=True),
    _gn("gn-the", "Google 新闻：Times Higher Education", "site:timeshighereducation.com when:3d",
        ["AI与教育"], layer=1, requires="ai", keep=True),
    _gn("gn-abroad", "Google 新闻：留学与签证政策", '"international students" visa OR "study abroad" OR "graduate route" when:2d',
        ["留学与签证政策"], layer=1),
    _gn("gn-ielts", "Google 新闻：雅思 / QS 排名", 'IELTS OR "QS World University Rankings" when:3d', ["留学与签证政策"], layer=1),
    _gn("gn-english", "Google 新闻：语言学习与英语培训", 'Duolingo OR "language learning" OR "English language teaching" when:2d',
        ["英语教学与语言培训行业"], layer=1),
    _gn("gn-zh-edu", "Google 新闻（中文）：教育部与 AI 教育", "教育部 人工智能 教育 when:2d", ["AI与教育"], layer=1, region="cn", requires="ai", keep=True),
    _gn("gn-zh-abroad", "Google 新闻（中文）：留学与签证", "留学 签证 政策 OR 雅思 when:2d", ["留学与签证政策"], layer=1, region="cn"),
    _gn("gn-zh-english", "Google 新闻（中文）：英语培训", "新东方 OR 英语培训 OR 多邻国 when:2d", ["英语教学与语言培训行业"], layer=1, region="cn"),
]

GNEWS_LOCALES = {
    "intl": dict(hl="en-US", gl="US", ceid="US:en"),
    "cn": dict(hl="zh-CN", gl="CN", ceid="CN:zh-Hans"),
}

# AI News Radar：只取这些来源类型；AIHOT 来源的条目不收（对方条款不允许公开镜像）
RADAR_KEEP_TIERS = {"official": 1, "ai_media": 3, "advanced": 3, "ai_vertical": 3}
RADAR_DROP_SITES = {"AI HOT"}
