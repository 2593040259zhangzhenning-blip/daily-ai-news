# Signal · 专题

- 运行时间：不定时，手动触发，触发时附上活动名（例如「活动：OpenAI DevDay 2026」）
- 模型：Opus
- 审批：自动批准；完成后推送通知到手机
- 存档日期：2026-10-01

这是定时任务提示词的备份。实际生效的是 Claude「定时任务」里的版本。改提示词时两边要一起改；任务丢失时，用下面的原文重新创建。

早间和晚间任务也会在发现已结束的发布会时自动写专题；这个任务用于单独为某场活动补写。

```text
任务：为 AI 简报「Signal」写一份发布会专题。要写哪场活动，在本次运行附带的说明里（例如「活动：OpenAI DevDay 2026」）；如果没有附带说明，只回复一行「没有指定活动」，结束。专题写进 GitHub 仓库 2593040259zhangzhenning-blip/daily-ai-news（网站 https://2593040259zhangzhenning-blip.github.io/daily-ai-news/ 会自动发布），再给用户推送一段简短摘要。全程用中文。不要修改网页代码、脚本和清单文件，只新增专题数据。

时间规则：只写活动上已经正式公布的内容。活动主题演讲还没结束的话，不要等待、不要 sleep，只回复一行「活动还没结束，稍后再跑」，结束。整个任务要在 15 分钟内完成。

步骤：
1. 用 mcp__claude_ai__current_time 确认北京时间（没有就运行 TZ=Asia/Shanghai date）。
2. 接入仓库：如果有 mcp__claude-code-remote__add_repo 工具，用它接入（owner 2593040259zhangzhenning-blip，repo daily-ai-news，access push）并按返回的命令 clone；没有这个工具就直接 git clone https://github.com/2593040259zhangzhenning-blip/daily-ai-news ，推送权限由运行环境提供。目录已是有效仓库就 git pull。之后都在这个仓库目录里操作。
3. 读 specials.md（专题的判断标准、检索方法、JSON 格式和写作要求）、README.md（打分标准和读者关注点）、sources.md（信源规则），严格照着做。
4. 给活动定一个 slug（小写字母、数字、连字符，例如 openai-devday-2026），运行 python3 scripts/add_issue.py --special-exists <slug>。已存在就只回复一行「这场活动的专题已存在」，结束。
5. 按 specials.md 检索并整理，写成 /tmp/special.json，然后运行 python3 scripts/add_issue.py --special /tmp/special.json。报错就按提示修改后重试，直到成功。
6. 运行 python3 scripts/add_issue.py --recent 2，看当天的早间和晚间内容里有没有这场活动的零散条目。有的话不用改它们，在最后的回复里说明一句即可。
7. git add -A，用 git -c user.name=Claude -c user.email=noreply@anthropic.com commit 提交，提交信息写「专题：<title>」，然后 git push。推送被拒绝就先 git pull --rebase 再推。确认推送成功。
8. 最后的回复就是推送给用户的内容：第一行「专题：<title>」；第二行是 summary；接着列出分数最高的 3 项，每项一行、一句话；最后一行「打开 Signal 看完整总结」。不要多余说明。
   如果推送最终失败：第一行改为「专题没能发布到网站：<报错原文的一句话>」，其余照样写。
```
