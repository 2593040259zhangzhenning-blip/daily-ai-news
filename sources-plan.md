# 信源改造计划（2026-10-16 定）

> 给接手这项工作的 Claude 看的。用户在 2026-10-16 的对话里定下了方向，实施在新对话里进行。
> 先读本文件和 `watchlist.md`（关注清单，已定稿），再读 CLAUDE.md、sources.md、README.md。

## 为什么改

- 现在每期只靠模型临时用搜索引擎找新闻，每期候选只有 24–52 条。搜索引擎收录有延迟，常搜到转载站（Investing.com 转载路透、FourWeekMBA 等）。
- 实证漏报（10/15–10/16）：OpenAI 官网《教学生通过提问来学习》（教育类，加权项，10/15 北京时间 21:00 发布，晚间 21:18 和次日早间都没收）、OpenAI GPT-Rosalind 进学术实验室、蚂蚁 Ling-3.1-flash 开源、昆仑 Matrix-Game 4.0。
- 用户原话的意思：前期工作都花在前端展示上，信源没做完善。

## 范围扩大（详见 watchlist.md）

Signal 不再只是 AI 简报。关注清单分三层（盯死的对象 / 雷达领域 / 日程），外加圈外位和每周建议关注。
新增：苹果、SpaceX（只关心这家公司，不是航天品类）、英伟达、Meta/Muse 系列、留学与签证政策、英语教学与语言培训行业；雷达领域：人形机器人、芯片、自动驾驶、脑机接口。
原则：主要看国外；国内只在「质的突破」时收；教育、留学、语言培训三项国内照常看。
不看：融资、人事变动、股价涨跌（除非直接影响用户在用的产品）。
「关注」不是「喜欢」：清单由用户决定，不按点击行为自动调整。

页面层面（分类、配色、「AI 简报」这个定位）等信源跑起来、看到实际内容比例后再和用户讨论，这次不动。

## 架构：把「找新闻」和「判断新闻」拆开

1. **收件箱**：在本仓库加 GitHub Actions 定时抓取（每小时一次，公开仓库免费），按 watchlist.md 读各源，合并成 `data/inbox/` 下最近 48 小时的候选（标题、链接、时间、来源、所属层），并记录每个源的成功/失败和条数（`source-status`）。GitHub Actions 能访问任何网站，不受 Claude 运行环境的网络白名单限制。
2. **定时任务先读收件箱**，再用搜索核实、补背景、查漏（付费墙媒体、公司官方 X 账号）。
3. **共识打分**（第二步）：同一事件合并，按「几家独立来源在报 + 最高来源层级」打分，不用模型。中转站只投票、只提供线索，出处永远是原始链接。
4. **圈外位**（第二步）：清单外的事门槛极高，全科技圈都在报才收，每天最多 1 条，标「圈外」。
5. **每周复盘 + 建议关注**（第二步）：列出共识度高但 Signal 没收的事件，以及建议加入清单的对象（圈外位出现过的、Techmeme/HN 等编辑都挑过的、已关注对象的邻居），每条附「为什么你可能会在意」。

## 分两步做（用户 2026-10-16 选定）

- **第一步**：抓取脚本 + Actions 工作流 + 收件箱 + 关注清单接入早晚两个定时任务（同时改 `tasks/` 里的备份和 sources.md）。跑一周看效果。
- **第二步**：共识打分、圈外位、每周复盘和建议关注。用第一周的真实数据调门槛。

## 已核实的来源（2026-10-16）

- 官方订阅源：OpenAI `openai.com/news/rss.xml`；DeepMind `deepmind.google/blog/rss.xml`；Google AI `blog.google/innovation-and-ai/technology/ai/rss/`；Google Research `research.google/blog/rss/`；Hugging Face `huggingface.co/blog/feed.xml`；Mistral `mistral.ai/news/rss`；英伟达 `blogs.nvidia.com/feed/`。
- 没有订阅源（要做页面变动监测）：Anthropic 新闻页、Claude 发布说明、Meta AI 博客、xAI、ChatGPT 发布说明、SpaceX 官网更新页、英伟达新闻中心。Microsoft AI 博客订阅源已失效（2022 年后无更新）；VentureBeat AI 订阅源 2026-08-27 后无更新。
- 苹果：Newsroom `apple.com/newsroom/rss-feed.rss`；开发者新闻 `developer.apple.com/news/rss/news.rss`；开发者版本发布 `developer.apple.com/news/releases/rss/releases.rss`；MacRumors `feeds.macrumors.com/MacRumors-All`；9to5Mac `9to5mac.com/feed/`。
- SpaceX：Launch Library 2（The Space Devs），匿名接口免费，约每小时 15 次请求。
- 媒体：TechCrunch AI、The Verge AI、Ars Technica AI、Wired AI、MIT Tech Review AI、The Decoder 均有订阅源；量子位 `qbitai.com/feed` 有效；Google News 搜索订阅源可按关键词取最近一天。
- 社区/研究：Hacker News Algolia 接口（`hn.algolia.com/api/v1/search_by_date`，无需钥匙）；arXiv `rss.arxiv.org/rss/cs.AI` 等；Hugging Face 每日论文接口。
- 中转站：
  - **AI News Radar**（LearnPrompt，MIT 协议，每 30 分钟更新，24 小时约 300 条）。数据在 GitHub 上，分支是 `master`：`raw.githubusercontent.com/LearnPrompt/ai-news-radar/master/data/latest-24h.json`（Claude 运行环境能直接读 raw.githubusercontent.com；它的 GitHub Pages 站点禁止抓取）。字段含 site_name、source、title、url、published_at、source_tier 等。
  - **AI HOT**：中文、带评分，覆盖国内公司公众号。旧接口 `aihot.virxact.com/api/public/items` **2026-10-31 下线**，接入时用新版。按新规则只用来发现国内「质的突破」。
  - **Follow Builders**：`raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json`，用官方 X 接口抓的 AI 圈人物推文，每天一次。只当线索（个人账号）。
- Artificial Analysis 免费接口：每天 100 次，条款限内部使用、不能再分发；Signal 是公开网页，暂不接，新模型卡维持现在的读法。

## 不做的

自建 RSSHub、自己抓公众号、付费 X 接口、把任何中转站当出处、财经股市、娱乐（英雄联盟另有单独提醒）、工具变更提醒（用户 10-16 明确不要）、「AI 在国内能不能用」专项（用户 10-16 明确不要）。
