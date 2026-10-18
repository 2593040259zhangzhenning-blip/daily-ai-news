# Signal · 早间

- 运行时间：每天北京时间 06:50（`CRON_TZ=Asia/Shanghai 50 6 * * *`）
- 模型：Opus
- 审批：自动批准；通知：2026-10-18 起正常完成不推送，只在没能发布时推送（见提示词里的「通知规则」）
- 存档日期：2026-10-18（通知规则改为只在失败时推送，成功时最终回复只写一行「已发布」；另加第 5 步 f「功能更新」和 updates 字段）；2026-10-17（信源改造第一步：先读收件箱和关注清单，再用搜索核实、补漏。ChatGPT 发布说明因站点拦截机器人，改由本任务直接读。同日取消晚间，本任务成为每天唯一一期；昨天没跑成时自动回看 48 小时补上）

这是定时任务提示词的备份。实际生效的是 Claude「定时任务」里的版本。改提示词时两边要一起改；任务丢失时，用下面的原文重新创建。

```text
任务：生成 AI 简报「Signal」当天的早间内容，写进 GitHub 仓库 2593040259zhangzhenning-blip/daily-ai-news（网站 https://2593040259zhangzhenning-blip.github.io/daily-ai-news/ 由 GitHub Pages 自动发布）。全程用中文。不要修改网页代码、脚本和清单文件，只新增当天的数据。这是 Signal 每天唯一的一期（2026-10-17 起已取消晚间）。

通知规则（用户 2026-10-18 要求，优先于下面所有步骤）：正常完成时不给用户发任何通知，不调用 PushNotification，最终回复只写一行，见第 11 步。只有任务没能完成时才通知：用 ToolSearch 加载 PushNotification（select:PushNotification），status 用 "proactive"，内容放在 <routine_summary> 标签里。需要通知的情形：连不上仓库或 clone / pull 失败；add_issue.py 反复报错、改不好；git push 最终失败；其他导致今天这期没能发布到网站的中断。通知内容见第 11 步末尾。今天的内容已存在（第 3 步）不算失败，不通知。

时间规则：只写检索时已经公布的内容，绝不等待即将发生或正在进行的事件（发布会、财报、投票等）。不要 sleep，不要为了等消息反复轮询；这类事件写进 watch，留给下一期。整个任务要在 15 分钟内完成。

步骤：
1. 确认北京时间今天的日期，下文记作 D（格式 YYYY-MM-DD）：有 mcp__claude_ai__current_time 工具就用它，没有就运行 TZ=Asia/Shanghai date +%F。
2. 接入仓库：如果有 mcp__claude-code-remote__add_repo 工具，用它接入（owner 2593040259zhangzhenning-blip，repo daily-ai-news，access push）并按返回的命令 clone；没有这个工具就直接 git clone https://github.com/2593040259zhangzhenning-blip/daily-ai-news ，推送权限由运行环境提供。目录已是有效仓库就 git pull。之后都在这个仓库目录里操作。
3. 运行 python3 scripts/add_issue.py --exists D-1morning。退出码是 0 说明今天已经生成过：只回复一行「今天的早间内容已存在」，结束。
   再运行 python3 scripts/add_issue.py --exists <D 的前一天>-1morning。退出码不是 0 说明昨天那期没跑成（常见原因是额度用完），本期要把昨天漏掉的一起补上：第 5 步 inbox_view 用 --hours 48（收件箱只保留 48 小时），官方 X 账号看最近两天，网页里「今日头条」那条的标题末尾不用特别标注，补上即可。
4. 读 README.md（重要度打分标准）、watchlist.md（关注清单：关注哪些对象、各层门槛、国内消息规则、不看的）、sources.md（信源规则）、specials.md（发布会专题）和 models.md（新模型卡），严格照着做。运行 python3 scripts/add_issue.py --recent 3、python3 scripts/add_issue.py --specials 和 python3 scripts/add_issue.py --models，记下最近已报道的事件和已有专题，避免重复。
5. 读收件箱，再用搜索补漏。仓库每小时自动抓取各信源，结果放在 data/inbox/。
   a. 运行 python3 scripts/inbox_view.py --hours 30（昨天没跑成时用 --hours 48，见第 3 步）。它按关注清单分组列出候选。[一手] 的链接就是原文（或主流媒体自己的报道），可以当出处；[线索]（Google 新闻、AI News Radar 等中转站、Techmeme、Hacker News、AI 圈人物的 X 帖子）只用来发现事件，不能当出处，必须再搜到原文；行内的【传闻类来源】【融资/人事/股价】【国内】是程序按关键词打的提示标记，最终由你按 watchlist.md 判断。输出开头如果有「⚠」，照它说的做：收件箱太旧、读不到或某些源连续失败，就对受影响的部分按 sources.md 用搜索补全，并记下这条警告（第 11 步要用）。输出里有一节「功能更新候选」，是各产品更新日志（Claude Code、Claude 应用、ChatGPT 与 Codex、OpenAI API）里的条目，只给第 5 步 f 用，不要把它们当普通新闻逐条写。
   b. 按 watchlist.md 取舍：第一层（盯死的对象）门槛低，有新消息基本都收，已报道过的事件有实质新进展也收；第二层（雷达领域）门槛高，只收收件箱里多家独立来源都在报的大事，每个领域每天最多一两条，一手来源加两家以上独立媒体、或三家以上独立媒体算数；国内消息（带【国内】标记，或搜索时发现的国内公司动态）只有「质的突破」才收，AI 与教育、留学与签证政策、英语教学与语言培训三项例外；融资、人事变动、股价涨跌不收，除非直接影响用户在用的产品（被收购、停服、涨价、换团队导致产品变化）；不在清单里的事，这一阶段不收。同一事件被多个来源报道时合并成一条。
   c. 苹果相关：MacRumors、9to5Mac 里报道已经发生的事实（发布、更新）出处优先用 Apple Newsroom 或开发者版本发布；供应链、分析师、代码挖掘、预测类的爆料按传闻处理（见第 7 步）。SpaceX 只收星舰试飞和重要发射（载人、重型猎鹰、首次做某件事），例行的星链发射不收。
   d. 日程（关注清单第三层）：苹果发布会和 WWDC、英伟达 GTC、星舰试飞和重要发射、OpenAI DevDay 和 Google I/O 等 AI 公司发布会，一周内有确定日期的，写进 watch（日期加事件）；已经结束且发布 3 项以上的，按第 6 步写专题。
   e. 收件箱够不到的，用搜索补三件事：核实（每条要收的事至少有一个一手或主流媒体出处，线索类先找到原文）；补背景（一两句为什么重要）；查漏。查漏必做：
      - ChatGPT 发布说明：help.openai.com 对自动抓取一律拦截，所以收件箱里没有它。用 WebFetch 打开 https://help.openai.com/en/articles/6825453-chatgpt-release-notes ，只看最近 3 天的条目（日期和标题）；打不开就用 site:help.openai.com 搜 ChatGPT release notes。有新条目就纳入候选，出处写这个页面。
      - 公司官方 X 账号（用 site:x.com 加账号名搜，只看最近一天；昨天没跑成时看最近两天）：@OpenAI、@OpenAIDevs、@AnthropicAI、@claudeai、@GoogleDeepMind、@AIatMeta、@nvidia、@SpaceX、@xai。官方账号的帖子算一手来源，个人账号只算线索。
      - 付费墙媒体（Bloomberg、The Information、FT）读不到全文时，只用标题和其他媒体的转述，正文里写明是据某某报道。
      - AI 与教育每期必查：收件箱已含 EdSurge、Inside Higher Ed、教育部、中国教育报、教育类关键词搜索；再搜一次各 AI 公司的教育产品公告（ChatGPT Edu、Claude for Education、Gemini for Education）。
      - 国内突破：只用来核实收件箱里标了【国内】的候选是否真的是「质的突破」，不要为了找国内新闻而大范围搜索。
      收件箱里已经有的内容不要再搜一遍。每条事实都要有检索到的来源支撑，不确定的不写。一边查一边记下：实际用搜索检查过的来源名称、搜索额外看过的候选条数。
   f. 功能更新（写进 updates，规则见 watchlist.md 的「功能更新」一节）：从「功能更新候选」一节，加上 e 里读到的 ChatGPT 发布说明，挑出我关注的产品（Claude 和 Claude Code、ChatGPT 和 Codex、Gemini）里用户能直接感觉到的变化：新功能、新模型能用了、用法或界面变了、价格额度可用范围变了。不收：环境变量、配置项、API 和 SDK 参数、修 bug、性能和稳定性优化、内部重构、遥测、只给企业管理员或开发者集成用的设置。更新日志条目的摘要只有开头几行，要判断时用 WebFetch 打开条目的链接看全文。每条一句 60 字以内的大白话，说清「你能感觉到什么变化」，带官方发布日期和官方来源链接（更新日志页本身就行）。已经作为头条、必看或更多动态写过的大事（比如新模型发布）不再重复写进 updates，--recent 里已经出现过的也不重复。最多 8 条；没有就不写 updates 字段，不要为了凑数写。
6. 发布会专题：如果检索中发现某场已经结束的发布活动公布了 3 项及以上值得报道的内容，而且还没有它的专题，就按 specials.md 另写一份专题（写成 /tmp/special.json，运行 python3 scripts/add_issue.py --special /tmp/special.json，报错就改到成功）。这场活动的各项发布不再写进下面的当期条目。已有专题的活动，只有实质新进展才作为普通条目写。
   新模型卡：按 models.md 检查最近 7 天正式发布的前沿模型（今天新发布的，以及之前已写成新闻、当时还没出分的）。在 Artificial Analysis 综合指数上已经出分、按模型算排进前 5（并列算同名次）、而且还没有它的卡（python3 scripts/add_issue.py --model-exists <slug> 退出码不是 0），就按 models.md 写一张，date 用模型发布那天（写成 /tmp/model.json，运行 python3 scripts/add_issue.py --model /tmp/model.json，报错就改到成功，再核对脚本打印出的排名）。脚本判定没进前 5 会报错，那就不出卡。卡只回答「排第几、怎么用上」，模型发布本身照常可以作为普通条目写进当期。还没出分的写进 watch。
7. 挑选和打分：按 README 的四项标准给每条打 1–10 分，读者重点关注「自己在用的 AI 工具」「AI 与教育」和关注清单第一层的对象，这几类要加权。3 分及以下不收；一般收 5–10 条，新闻少的日子可以更少，宁缺毋滥。最高分的 1 条是头条（tier "lead"），并写一句 40 字以内的 summary；其余 7 分及以上的最多 3 条是必看（tier "must"）；其他是 "brief"。已经报道过的事件只有出现实质新进展才写，标题里点明「新进展」。只在个人 X 账号、论坛出现或属于苹果爆料类、没有得到确认的消息，标题前加「传闻：」，分数不超过 5，不能做头条。
8. 把数据写成 JSON 文件 /tmp/issue.json，结构：
{
  "key": "D-1morning",
  "date": "D",
  "edition": "morning",
  "createdAt": 当前时间的 ISO 8601 字符串（带 +08:00）,
  "headline": 一句话概括今天最大的主题（20 字以内）,
  "items": [ { "cat": 类别, "title": 标题（30 字以内）, "body": 1–3 句，讲清发生了什么、为什么重要, "score": 1–10 的整数, "tier": "lead" / "must" / "brief", "summary": 只有头条需要, "sources": [ {"name": 媒体或机构名, "url": 链接} ] } ],
  "watch": [ 1–3 条接下来值得关注的事（含第三层日程），可省略 ],
  "updates": [ { "product": 产品名（Claude Code、Claude、ChatGPT、Codex、Gemini，14 字以内）, "text": 一句话大白话（60 字以内）, "date": "官方发布日期 YYYY-MM-DD", "sources": [ {"name": "Claude Code 更新日志", "url": 链接} ] } ]（第 5 步 f；可省略；同一产品的条目挨在一起，Claude 在前）,
  "scan": { "checked": [ 来源名称数组 ], "candidates": 看过的候选条数 }
}
cat 只能取：model（模型发布）、policy（政策治理）、product（产品动态）、biz（融资商业）、china（中国 AI）、research（研究突破）。新增关注范围暂时这样归（页面分类等跑一段时间后再和用户商量）：苹果的系统和硬件、SpaceX 的发射和星舰 → product；芯片、机器人、自动驾驶、脑机接口的技术突破 → research，产品发布 → product；留学与签证政策、教育政策 → policy；国内的质的突破 → china。
scan.checked：先运行 python3 scripts/inbox_view.py --checked，把输出的来源名数组整个放进去，再加上第 5 步用搜索实际检查过的来源名称（如「ChatGPT 发布说明」「@OpenAI」「Bloomberg」）。scan.candidates：第 5 步 inbox_view 输出末尾给出的「列出候选条数」，加上搜索额外看过的条数。
版权要求：title、body、summary 必须用自己的话写，不照抄原文句子；直接引语最多一句，且少于 15 个字。
9. 运行 python3 scripts/add_issue.py /tmp/issue.json。如果报错，按提示改 JSON 后再运行，直到成功。
10. git add -A，用 git -c user.name=Claude -c user.email=noreply@anthropic.com commit 提交，提交信息写「早间：<headline>」，然后 git push。如果推送被拒绝（收件箱的自动抓取每小时也会往 main 提交），先 git pull --rebase 再推。确认推送成功。
11. 最终回复：
   - 一切顺利（第 10 步推送成功）：只回复一行「已发布」。如果第 5 步有「⚠」警告，改为「已发布（信源异常：<警告的一句话>）」。不要列头条和必看，不要提新模型卡或专题，不要调用 PushNotification。
   - 没能发布（第 10 步最终推送失败，或通知规则里列的其他中断）：按通知规则发 PushNotification，第一行「早间内容没能发布到网站：<报错原文的一句话>」，如果已经选好了头条和必看，接着列出头条和每条必看（每条一行、一句话），让用户至少在通知里看到内容；最终回复写同样的内容。
```
