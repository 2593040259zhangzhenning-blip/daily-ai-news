# Signal · 晚间

- 运行时间：每天北京时间 21:18（`CRON_TZ=Asia/Shanghai 18 21 * * *`）
- 模型：Opus
- 审批：自动批准；完成后推送通知到手机
- 存档日期：2026-10-01

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
   - 检索范围是上一次更新（早间或晚间）之后到现在，通常约 24 小时以上。
   - JSON 里 key 用 "D-1morning"，edition 用 "morning"；可加 "watch"（1–3 条接下来值得关注的事）。
   - 一般收 5–10 条，3 分及以下不收：最高分 1 条是头条（tier "lead"），加一句 40 字以内的 summary；其余 7 分及以上最多 3 条是必看（"must"）；其他是 "brief"。传闻不能做头条。不适用第 7 步的晚间门槛。
   - 提交信息写「早间（补）：<headline>」。
   - 最后的回复：写了专题就第一行「专题：<专题 title>」；然后一行「今日头条：<头条标题>（早上没跑成，已补上）」；接着每条必看一行；最后一行「打开 Signal 看全文」。
   - 补做早间后本次就结束，不再另写晚间内容。
4. 读 README.md（重要度打分标准）、sources.md（信源清单和规则）和 specials.md（发布会专题），严格照着做。运行 python3 scripts/add_issue.py --recent 3 和 python3 scripts/add_issue.py --specials，重点看 D 当天的早间内容 D-1morning 和已有专题，记下已经报道过的事件。
5. 按 sources.md 的五层逐层检索 D 当天早上 7 点以来的 AI 动态（中国白天、欧洲时段、美国凌晨公布的都算）。五层都要查，第二层用 site:x.com 加账号名搜索，第四层（AI 与教育）必查。每条事实都要有检索到的来源支撑。一边查一边记下实际检查过的来源名称和看过的候选条数。
6. 发布会专题：如果检索中发现某场已经结束的发布活动公布了 3 项及以上值得报道的内容，而且还没有它的专题，就按 specials.md 另写一份专题（写成 /tmp/special.json，运行 python3 scripts/add_issue.py --special /tmp/special.json，报错就改到成功）。这场活动的各项发布不再写进下面的晚间条目。已有专题的活动，只有实质新进展才作为普通条目写。
7. 门槛要高：只收早间没有、而且确实重要的新事件，或早间事件的实质新进展。一般的小更新、评论文章、重复报道都不算。按 README 的四项标准打 1–10 分，「自己在用的 AI 工具」和「AI 与教育」加权；5 分以下不收。
   - 如果没有达到门槛的普通条目：不要写 /tmp/issue.json；如果第 6 步写了专题，直接跳到第 10 步提交；如果什么都没写，只回复一行「今晚无重要增补」，结束。
   - 如果有 1–5 条：继续。
8. 晚间内容没有头条：7 分及以上的最多 3 条标为必看（tier "must"），其余标 "brief"，不能用 "lead"。只在个人 X 账号或论坛出现、没有得到确认的消息，标题前加「传闻：」，分数不超过 5。把数据写成 JSON 文件 /tmp/issue.json：
{
  "key": "D-2evening",
  "date": "D",
  "edition": "evening",
  "createdAt": 当前时间的 ISO 8601 字符串（带 +08:00）,
  "headline": 一句话概括今晚新增的内容（20 字以内）,
  "items": [ { "cat": 类别, "title": 标题（30 字以内）, "body": 1–3 句说明, "score": 1–10 的整数, "tier": "must" 或 "brief", "sources": [ {"name": 媒体或机构名, "url": 链接} ] } ],
  "scan": { "checked": [ 实际检查过的来源名称，按 sources.md 的写法 ], "candidates": 看过的候选条数 }
}
cat 只能取：model、policy、product、biz、china、research。
版权要求：title 和 body 必须用自己的话写，不照抄原文句子；直接引语最多一句，且少于 15 个字。
9. 运行 python3 scripts/add_issue.py /tmp/issue.json。如果报错，按提示改 JSON 后再运行，直到成功。
10. git add -A，用 git -c user.name=Claude -c user.email=noreply@anthropic.com commit 提交，提交信息写「晚间：<headline>」（只有专题时写「专题：<专题 title>」），然后 git push。如果推送被拒绝，先 git pull --rebase 再推。确认推送成功。
11. 最后的回复就是推送给用户的内容：如果写了专题，第一行「专题：<专题 title>」；有普通条目就接一行「晚间新增 N 条」和每条一行、一句话；最后一行「打开 Signal 看全文」。不要多余说明。
   如果第 10 步最终推送失败：第一行改为「晚间内容没能发布到网站：<报错原文的一句话>」，接着照样列出内容，让用户至少在通知里看到内容。
```
