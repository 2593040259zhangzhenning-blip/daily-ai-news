# Signal · 早间

- 运行时间：每天北京时间 06:50（`CRON_TZ=Asia/Shanghai 50 6 * * *`）
- 模型：Opus
- 审批：自动批准；完成后推送通知到手机
- 存档日期：2026-10-01

这是定时任务提示词的备份。实际生效的是 Claude「定时任务」里的版本。改提示词时两边要一起改；任务丢失时，用下面的原文重新创建。

```text
任务：生成 AI 简报「Signal」当天的早间内容，写进 GitHub 仓库 2593040259zhangzhenning-blip/daily-ai-news（网站 https://2593040259zhangzhenning-blip.github.io/daily-ai-news/ 由 GitHub Pages 自动发布），再给用户推送一段简短摘要。全程用中文。不要修改网页代码、脚本和清单文件，只新增当天的数据。

时间规则：只写检索时已经公布的内容，绝不等待即将发生或正在进行的事件（发布会、财报、投票等）。不要 sleep，不要为了等消息反复轮询；这类事件写进 watch，留给下一期。整个任务要在 15 分钟内完成。

步骤：
1. 确认北京时间今天的日期，下文记作 D（格式 YYYY-MM-DD）：有 mcp__claude_ai__current_time 工具就用它，没有就运行 TZ=Asia/Shanghai date +%F。
2. 接入仓库：如果有 mcp__claude-code-remote__add_repo 工具，用它接入（owner 2593040259zhangzhenning-blip，repo daily-ai-news，access push）并按返回的命令 clone；没有这个工具就直接 git clone https://github.com/2593040259zhangzhenning-blip/daily-ai-news ，推送权限由运行环境提供。目录已是有效仓库就 git pull。之后都在这个仓库目录里操作。
3. 运行 python3 scripts/add_issue.py --exists D-1morning。退出码是 0 说明今天已经生成过：只回复一行「今天的早间内容已存在」，结束。
4. 读 README.md（重要度打分标准）、sources.md（信源清单和规则）和 specials.md（发布会专题），严格照着做。运行 python3 scripts/add_issue.py --recent 3 和 python3 scripts/add_issue.py --specials，记下最近已报道的事件和已有专题，避免重复。
5. 按 sources.md 的五层逐层检索过去约 24 小时（上一次早间或晚间更新之后）的 AI 动态。五层都要查，第二层（X 官方账号）用 site:x.com 加账号名搜索，第四层（AI 与教育）每期必查。每条事实都要有检索到的来源支撑，不确定的不写。一边查一边记下：实际检查过的来源名称、看过的候选新闻条数。
6. 发布会专题：如果检索中发现某场已经结束的发布活动公布了 3 项及以上值得报道的内容，而且还没有它的专题，就按 specials.md 另写一份专题（写成 /tmp/special.json，运行 python3 scripts/add_issue.py --special /tmp/special.json，报错就改到成功）。这场活动的各项发布不再写进下面的当期条目。已有专题的活动，只有实质新进展才作为普通条目写。
7. 挑选和打分：按 README 的四项标准给每条打 1–10 分，读者重点关注「自己在用的 AI 工具」和「AI 与教育」，这两类要加权。3 分及以下不收；一般收 5–10 条，新闻少的日子可以更少，宁缺毋滥。最高分的 1 条是头条（tier "lead"），并写一句 40 字以内的 summary；其余 7 分及以上的最多 3 条是必看（tier "must"）；其他是 "brief"。已经报道过的事件只有出现实质新进展才写，标题里点明「新进展」。只在个人 X 账号或论坛出现、没有得到确认的消息，标题前加「传闻：」，分数不超过 5，不能做头条。
8. 把数据写成 JSON 文件 /tmp/issue.json，结构：
{
  "key": "D-1morning",
  "date": "D",
  "edition": "morning",
  "createdAt": 当前时间的 ISO 8601 字符串（带 +08:00）,
  "headline": 一句话概括今天最大的主题（20 字以内）,
  "items": [ { "cat": 类别, "title": 标题（30 字以内）, "body": 1–3 句，讲清发生了什么、为什么重要, "score": 1–10 的整数, "tier": "lead" / "must" / "brief", "summary": 只有头条需要, "sources": [ {"name": 媒体或机构名, "url": 链接} ] } ],
  "watch": [ 1–3 条接下来值得关注的事，可省略 ],
  "scan": { "checked": [ 实际检查过的来源名称，按 sources.md 的写法 ], "candidates": 看过的候选条数 }
}
cat 只能取：model（模型发布）、policy（政策治理）、product（产品动态）、biz（融资商业）、china（中国 AI）、research（研究突破）。
版权要求：title、body、summary 必须用自己的话写，不照抄原文句子；直接引语最多一句，且少于 15 个字。
9. 运行 python3 scripts/add_issue.py /tmp/issue.json。如果报错，按提示改 JSON 后再运行，直到成功。
10. git add -A，用 git -c user.name=Claude -c user.email=noreply@anthropic.com commit 提交，提交信息写「早间：<headline>」，然后 git push。如果推送被拒绝，先 git pull --rebase 再推。确认推送成功。
11. 最后的回复就是推送给用户的内容：如果写了专题，第一行「专题：<专题 title>」；然后一行「今日头条：<头条标题>」；接着每条必看一行、一句话；最后一行「打开 Signal 看全文」。不要多余说明。
   如果第 10 步最终推送失败：第一行改为「早间内容没能发布到网站：<报错原文的一句话>」，接着照样列出头条和必看，让用户至少在通知里看到内容。
```
