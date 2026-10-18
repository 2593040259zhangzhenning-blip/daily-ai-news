# 信源清单

关注什么、各层门槛、国内消息和不看的规则，以 `watchlist.md` 为准；这份文件只管**去哪里找**和**哪些能当出处**。
每一期（2026-10-17 起每天只有早间一期）的流程：先读收件箱，再用搜索核实、补背景、查漏；实际检查过的来源记进当期的 `scan` 字段，网页底部会公开显示。
这份清单可以随时改：收件箱的源改 `scripts/inbox_config.py`（加一项 = 加一个源），搜索补漏的部分改这份文件，下一期就按新的来。

## 一、收件箱（自动抓取，每小时一次）

GitHub Actions（`.github/workflows/inbox.yml`）每小时读下面这些源，合并成最近 48 小时的候选，放在 `data/inbox/`：
`items.json` 是候选，`source-status.json` 记每个源这次成功没成功、抓到几条。定时任务用 `python3 scripts/inbox_view.py` 读，不要直接读 JSON。

| 层 | 来源 | 读法 | 能否当出处 |
|---|---|---|---|
| 1 官方一手 | OpenAI 官网、Google DeepMind、Google AI、Google Research、英伟达博客、英伟达新闻中心、Apple Newsroom、Apple 开发者新闻和版本发布、Hugging Face 博客、Mistral、多邻国博客 | 订阅源 | 能 |
| 1 官方一手 | Anthropic 新闻页、Meta AI 博客、xAI 新闻页、雅思官方、教育部（工作动态） | 页面变动监测：每小时看有没有新链接，发布日期取自链接或文章页 | 能 |
| 1 官方一手 | Claude 发布说明（support.claude.com，是 Claude 应用的更新，不含 Claude Code） | 解析页面里按日期排的条目 | 能 |
| 1 官方一手 | Claude Code 更新日志（code.claude.com，逐版本）、Claude Code 每周摘要（即邮件 "This week in Claude Code" 的网页版，2026-10-18 时最新一期只到 9 月 11 日那周，只当补充） | 抓页面的 Markdown 版（网址后加 .md），解析 `<Update>` 条目 | 能 |
| 1 官方一手 | ChatGPT 与 Codex 更新日志（learn.chatgpt.com，原 developers.openai.com/codex/changelog 会跳转过去；Codex CLI 0.xxx 这类 GitHub 发版镜像不收）、OpenAI API 更新日志（developers.openai.com） | 前者解析页面，后者抓 Markdown 版 | 能 |
| 1 官方一手 | SpaceX 官网更新（内容接口）、英国签证与移民局（GOV.UK，只留和学生有关的） | 接口 / 订阅源 | 能 |
| 3 主流媒体 | TechCrunch AI、The Verge AI、Ars Technica AI、Wired AI、MIT Technology Review AI、The Decoder、量子位 | 订阅源 | 能（写明媒体名） |
| 3 主流媒体 | MacRumors、9to5Mac | 订阅源 | 报道已发生的事实时能；爆料类按传闻处理 |
| 3 日程 | SpaceX 发射日程（Launch Library） | 公开接口 | 只用于日程，是否发射成功再找官方确认 |
| 4 AI 与教育 / 留学 | EdSurge、Inside Higher Ed（只留 AI 相关）、ICEF Monitor、The PIE News、中国教育报（只留 AI 相关） | 订阅源 / 页面 | 能 |
| 5 查漏线索 | Techmeme、Hacker News 首页（≥100 分）、Hugging Face 每日论文（前 12）、AI News Radar（中转站）、Follow Builders（AI 圈人物的 X 帖子）、Google 新闻关键词搜索（20 组） | 订阅源 / 接口 | **不能**，只用来发现事件 |

AI HOT（aihot.news）不接：它的使用规则不允许公开镜像，而收件箱随本仓库公开；也不收 AI News Radar 里来自 AI HOT 的条目。

上表中的更新日志类来源（Claude 发布说明、Claude Code 更新日志和每周摘要、ChatGPT 与 Codex 更新日志、OpenAI API 更新日志）的条目带 `kind: "changelog"`，`inbox_view.py` 把它们单独列成「功能更新候选」一节，不混进按对象分的组里。怎么挑见 `watchlist.md` 的「功能更新」。
GitHub Actions 的机房 IP 能不能读到这几个页面，要看上线后 `source-status.json` 的结果；读不到的由早间任务用 WebFetch 直接读（ChatGPT 发布说明就是这样处理的）。

收件箱里每条候选都带三个提示标记，是程序按关键词打的，**只供参考，取舍由定时任务按 `watchlist.md` 判断**：【传闻类来源】【融资/人事/股价】【国内】。
时间前面的 `~` 表示来源没给发布时间，用的是收件箱第一次发现它的时间。

## 二、搜索补漏（收件箱够不到的）

收件箱里已经有的不要再搜一遍。检索方式：优先用 `site:域名` 加关键词查最近 24 小时；能直接打开的官方页面就直接打开。

| 要查什么 | 怎么查 | 为什么收件箱没有 |
|---|---|---|
| ChatGPT 发布说明（也是功能更新的来源） | 用 WebFetch 打开 help.openai.com/en/articles/6825453-chatgpt-release-notes，只看最近几天的条目；打不开就搜 `site:help.openai.com ChatGPT release notes` | OpenAI 帮助中心对自动抓取一律返回 Cloudflare 人机验证，GitHub 上抓不到 |
| 公司官方 X 账号 | `site:x.com 账号名`：@OpenAI、@OpenAIDevs、@AnthropicAI、@claudeai、@GoogleDeepMind、@AIatMeta、@nvidia、@SpaceX、@xai | X 不允许自动读取，也没有接付费接口 |
| 付费墙媒体 | Reuters、Bloomberg、Financial Times、The Information：读不到全文时只用标题和其他媒体的转述，正文里写明是据某某报道 | 读不到正文 |
| AI 公司的教育产品公告 | ChatGPT Edu、Claude for Education、Gemini for Education 等 | 没有统一的订阅源 |
| 国内公司动态（只为核实「质的突破」） | DeepSeek、通义 / Qwen（qwenlm.github.io）、月之暗面 Kimi、智谱（z.ai）、字节豆包；中文媒体：机器之心、36氪、晚点 LatePost、财新 | 国内消息按 `watchlist.md` 的规则只在突破时收，不日常抓 |
| 日程 | 苹果发布会和 WWDC、英伟达 GTC、OpenAI DevDay、Google I/O 等 | 官方公告或媒体预告，有确定日期的写进 `watch` |

新模型的排名查 Artificial Analysis（见 `models.md`），不在这里。

## 规则

1. 每条新闻至少要有一个官方一手或主流媒体来源（收件箱里标 `[一手]` 的，或搜索找到的原文），也就是上面第 1、3、4 层。
2. 只在个人 X 账号或论坛出现、没有得到确认的消息，以及苹果的爆料类消息（供应链、分析师、代码挖掘、预测）：标题前加「传闻：」，分数不超过 5，不能做头条。
3. 不能单独作为出处：收件箱里标 `[线索]` 的全部（Google 新闻的跳转链接、AI News Radar 等中转站、Techmeme、Hacker News、Follow Builders、Hugging Face 每日论文），以及 Wikipedia、SEO 汇总站、AI 工具目录站、没有署名的聚合号。中转站只提供线索，发现事件后必须回到原文找确认，`sources` 里写原文链接。
4. 当期的 `scan` 字段：
   - `checked`：先运行 `python3 scripts/inbox_view.py --checked`，把输出的来源名数组整个放进去（收件箱本次成功读取的源），再加上这一期用搜索实际检查过的来源名称。某个源抓取失败，它就不会出现在名单里，不要手动补上。
   - `candidates`：`inbox_view.py` 输出末尾给出的「列出候选条数」，加上搜索额外看过的条数。
5. 收件箱某个源连续失败，`inbox_view.py` 开头会用「⚠」提示。受影响的部分要用搜索补全，并在最终回复里提一句。
