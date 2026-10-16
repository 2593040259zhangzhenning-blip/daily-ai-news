# Signal · 晚间

- 运行时间：每天北京时间 21:18（`CRON_TZ=Asia/Shanghai 18 21 * * *`）
- 模型：Opus
- 审批：自动批准；完成后推送通知到手机
- 存档日期：2026-10-17（信源改造第一步：先读收件箱和关注清单，再用搜索核实、补漏。ChatGPT 发布说明因站点拦截机器人，改由本任务直接读）

这是定时任务提示词的备份。实际生效的是 Claude「定时任务」里的版本。改提示词时两边要一起改；任务丢失时，用下面的原文重新创建。

第 3 步的「补做早间」是兜底：早间任务因额度用完等原因没跑成时，晚间按早间标准补上当天内容。

```text
任务：检查今天白天（北京时间当天早间更新之后到现在）AI 领域有没有值得补充的重要新动态。有就补进 GitHub 仓库 2593040259zhangzhenning-blip/daily-ai-news 里 AI 简报「Signal」当天的页面（网站 https://2593040259zhangzhenning-blip.github.io/daily-ai-news/ 会把它并进当天页面，标为「晚间」），没有就什么都不写。全程用中文。不要修改网页代码、脚本和清单文件，只新增数据。

时间规则：只写检索时已经公布的内容，绝不等待即将发生或正在进行的事件（发布会、财报、投票等）。不要 sleep，不要为了等消息反复轮询；这类事件留给第二天早间那一期。整个任务要在 15 分钟内完成。

步骤：
1. 确认北京时间今天的日期，下文记作 D（格式 YYYY-MM-DD）：有 mcp__claude_ai__current_time 工具就用它，没有就运行 TZ=Asia/Shanghai date +%F。如果北京时间已经过了 0 点、还没到 6 点（任务延迟运行），D 取前一天。
2. 接入仓库：如果有 mcp__claude-code-remote__add_repo 工具，用它接入（owner 2593040259zhangzhenning-blip，repo daily-ai-news，access push）并按返回的命令 clone；没有这个工具就直接 git clone https://github.com/2593040259zhangzhenning-blip/daily-ai-news ，推送权限由运行环境提供。目录已是有效仓库就 git pull。之后都在这个仓库目录里操作。
3. 运行 python3 scripts/add_issue.py --exists D-2evening。退出码是 0 说明今晚已经补过：只回复一行「今晚的增补已存在」，结束。
   再运行 python3 scripts/add_issue.py --exists D-1morning。退出码不是 0 说明今天早上那次没跑成（常见原因是额度用完），本次改为补做早间内容，规则如下，其余照本任务各步骤做：
   - 检索范围是上一次更新（早间或晚间）之后到现在，通常约 24 小时以上；第 5 步的 inbox_view 用 --hours 48。
   - JSON 里 key 用 "D-1morning"，edition 用 "morning"；可加 "watch"（1–3 条接下来值得关注的事，含第三层日程）。
   - 一般收 5–10 条，3 分及以下不收：最高分 1 条是头条（tier "lead"），加一句 40 字以内的 summary；其余 7 分及以上最多 3 条是必看（"must"）；其他是 "brief"。传闻不能做头条。不适用第 7 步的晚间门槛。
   - 提交信息写「早间（补）：<headline>」。
   - 最后的回复：写了新模型卡就第一行「新模型：<name>，综合排名<脚本打印的结论>」；写了专题就接一行「专题：<专题 title>」；然后一行「今日头条：<头条标题>（早上没跑成，已补上）」；接着每条必看一行；最后一行「打开 Signal 看全文」。
   - 补做早间后本次就结束，不再另写晚间内容。
4. 读 README.md（重要度打分标准）、watchlist.md（关注清单：关注哪些对象、各层门槛、国内消息规则、不看的）、sources.md（信源规则）、specials.md（发布会专题）和 models.md（新模型卡），严格照着做。运行 python3 scripts/add_issue.py --recent 3、python3 scripts/add_issue.py --specials 和 python3 scripts/add_issue.py --models，重点看 D 当天的早间内容 D-1morning 和已有专题，记下已经报道过的事件。
5. 读收件箱，再用搜索补漏。仓库每小时自动抓取各信源，结果放在 data/inbox/。
   a. 运行 python3 scripts/inbox_view.py --hours 16（D 当天早上 7 点以来；中国白天、欧洲时段、美国凌晨公布的都算）。它按关注清单分组列出候选。[一手] 的链接就是原文（或主流媒体自己的报道），可以当出处；[线索]（Google 新闻、AI News Radar 等中转站、Techmeme、Hacker News、AI 圈人物的 X 帖子）只用来发现事件，不能当出处，必须再搜到原文；行内的【传闻类来源】【融资/人事/股价】【国内】是程序按关键词打的提示标记，最终由你按 watchlist.md 判断。输出开头如果有「⚠」，照它说的做：收件箱太旧、读不到或某些源连续失败，就对受影响的部分按 sources.md 用搜索补全，并在最终回复里提一句。
   b. 按 watchlist.md 取舍：第一层（盯死的对象）有新消息基本都收，已报道过的事件有实质新进展也收，但晚间整体门槛高（见第 7 步）；第二层（雷达领域）只收收件箱里多家独立来源都在报的大事，每个领域每天最多一两条，一手来源加两家以上独立媒体、或三家以上独立媒体算数；国内消息（带【国内】标记，或搜索时发现的国内公司动态）只有「质的突破」才收，AI 与教育、留学与签证政策、英语教学与语言培训三项例外；融资、人事变动、股价涨跌不收，除非直接影响用户在用的产品（被收购、停服、涨价、换团队导致产品变化）；不在清单里的事，这一阶段不收。同一事件被多个来源报道时合并成一条。
   c. 苹果相关：MacRumors、9to5Mac 里报道已经发生的事实（发布、更新）出处优先用 Apple Newsroom 或开发者版本发布；供应链、分析师、代码挖掘、预测类的爆料按传闻处理（见第 8 步）。SpaceX 只收星舰试飞和重要发射（载人、重型猎鹰、首次做某件事），例行的星链发射不收。
   d. 收件箱够不到的，用搜索补三件事：核实（每条要收的事至少有一个一手或主流媒体出处，线索类先找到原文）；补背景；查漏。查漏必做：
      - ChatGPT 发布说明：help.openai.com 对自动抓取一律拦截，所以收件箱里没有它。用 WebFetch 打开 https://help.openai.com/en/articles/6825453-chatgpt-release-notes ，只看今天的条目（日期和标题）；打不开就用 site:help.openai.com 搜 ChatGPT release notes。有新条目就纳入候选，出处写这个页面。
      - 公司官方 X 账号（用 site:x.com 加账号名搜，只看今天）：@OpenAI、@OpenAIDevs、@AnthropicAI、@claudeai、@GoogleDeepMind、@AIatMeta、@nvidia、@SpaceX、@xai。官方账号的帖子算一手来源，个人账号只算线索。
      - 付费墙媒体（Bloomberg、The Information、FT）读不到全文时，只用标题和其他媒体的转述，正文里写明是据某某报道。
      - AI 与教育必查：收件箱已含教育类来源；再搜一次各 AI 公司的教育产品公告（ChatGPT Edu、Claude for Education、Gemini for Education）。
      - 国内突破：只用来核实收件箱里标了【国内】的候选是否真的是「质的突破」，不要为了找国内新闻而大范围搜索。
      收件箱里已经有的内容不要再搜一遍。每条事实都要有检索到的来源支撑。一边查一边记下：实际用搜索检查过的来源名称、搜索额外看过的候选条数。
6. 发布会专题：如果检索中发现某场已经结束的发布活动公布了 3 项及以上值得报道的内容，而且还没有它的专题，就按 specials.md 另写一份专题（写成 /tmp/special.json，运行 python3 scripts/add_issue.py --special /tmp/special.json，报错就改到成功）。这场活动的各项发布不再写进下面的晚间条目。已有专题的活动，只有实质新进展才作为普通条目写。
   新模型卡：按 models.md 检查最近 7 天正式发布的前沿模型（今天新发布的，以及之前已写成新闻、当时还没出分的）。在 Artificial Analysis 综合指数上已经出分、按模型算排进前 5（并列算同名次）、而且还没有它的卡（python3 scripts/add_issue.py --model-exists <slug> 退出码不是 0），就按 models.md 写一张，date 用模型发布那天（写成 /tmp/model.json，运行 python3 scripts/add_issue.py --model /tmp/model.json，报错就改到成功，再核对脚本打印出的排名）。脚本判定没进前 5 会报错，那就不出卡。卡只回答「排第几、怎么用上」，模型发布本身照常可以作为普通条目写进当期。
7. 门槛要高：只收早间没有、而且确实重要的新事件，或早间事件的实质新进展。一般的小更新、评论文章、重复报道都不算。按 README 的四项标准打 1–10 分，「自己在用的 AI 工具」「AI 与教育」和关注清单第一层的对象加权；5 分以下不收。
   - 如果没有达到门槛的普通条目：不要写 /tmp/issue.json；如果第 6 步写了专题或新模型卡，直接跳到第 10 步提交；如果什么都没写，只回复一行「今晚无重要增补」，结束。
   - 如果有 1–5 条：继续。
8. 晚间内容没有头条：7 分及以上的最多 3 条标为必看（tier "must"），其余标 "brief"，不能用 "lead"。只在个人 X 账号、论坛出现或属于苹果爆料类、没有得到确认的消息，标题前加「传闻：」，分数不超过 5。把数据写成 JSON 文件 /tmp/issue.json：
{
  "key": "D-2evening",
  "date": "D",
  "edition": "evening",
  "createdAt": 当前时间的 ISO 8601 字符串（带 +08:00）,
  "headline": 一句话概括今晚新增的内容（20 字以内）,
  "items": [ { "cat": 类别, "title": 标题（30 字以内）, "body": 1–3 句说明, "score": 1–10 的整数, "tier": "must" 或 "brief", "sources": [ {"name": 媒体或机构名, "url": 链接} ] } ],
  "scan": { "checked": [ 来源名称数组 ], "candidates": 看过的候选条数 }
}
cat 只能取：model、policy、product、biz、china、research。新增关注范围暂时这样归（页面分类等跑一段时间后再和用户商量）：苹果的系统和硬件、SpaceX 的发射和星舰 → product；芯片、机器人、自动驾驶、脑机接口的技术突破 → research，产品发布 → product；留学与签证政策、教育政策 → policy；国内的质的突破 → china。
scan.checked：先运行 python3 scripts/inbox_view.py --checked，把输出的来源名数组整个放进去，再加上第 5 步用搜索实际检查过的来源名称（如「ChatGPT 发布说明」「@OpenAI」「Bloomberg」）。scan.candidates：第 5 步 inbox_view 输出末尾给出的「列出候选条数」，加上搜索额外看过的条数。
版权要求：title 和 body 必须用自己的话写，不照抄原文句子；直接引语最多一句，且少于 15 个字。
9. 运行 python3 scripts/add_issue.py /tmp/issue.json。如果报错，按提示改 JSON 后再运行，直到成功。
10. git add -A，用 git -c user.name=Claude -c user.email=noreply@anthropic.com commit 提交，提交信息写「晚间：<headline>」（只有专题时写「专题：<专题 title>」，只有新模型卡时写「新模型：<name>」），然后 git push。如果推送被拒绝（收件箱的自动抓取每小时也会往 main 提交），先 git pull --rebase 再推。确认推送成功。
11. 最后的回复就是推送给用户的内容：如果写了新模型卡，第一行「新模型：<name>，综合排名<脚本打印的结论>，<use 第一项的 where> <value>」；如果写了专题，接一行「专题：<专题 title>」；有普通条目就接一行「晚间新增 N 条」和每条一行、一句话；最后一行「打开 Signal 看全文」。如果第 5 步的输出里有「⚠」警告，在「打开 Signal 看全文」之前加一行「信源异常：<警告的一句话>」。不要多余说明。
   如果第 10 步最终推送失败：第一行改为「晚间内容没能发布到网站：<报错原文的一句话>」，接着照样列出内容，让用户至少在通知里看到内容。
```
