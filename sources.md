# 信源清单

每一期（早间和晚间）都要按下面五层逐层检索，并把实际检查过的来源记进当期的 `scan` 字段，网页底部会公开显示。
这份清单可以随时改：加一行、删一行，下一期就按新的来。

检索方式：优先用 `site:域名` 加关键词在搜索引擎里查最近 24 小时的内容；能直接打开的官方页面就直接打开。

## 第一层 · 官方一手

公司自己发布的消息，可信度最高。

| 公司 | 查哪里 |
|---|---|
| OpenAI | openai.com/news，OpenAI 开发者文档的更新日志 |
| Anthropic | anthropic.com/news，Claude 发布说明（support.claude.com） |
| Google / DeepMind | blog.google（AI 栏目），deepmind.google |
| Meta | ai.meta.com/blog |
| 微软 | blogs.microsoft.com（AI 相关） |
| 英伟达 | nvidianews.nvidia.com |
| xAI | x.ai/news |
| DeepSeek | deepseek.com 与其 API 文档的新闻页 |
| 阿里通义 / Qwen | qwenlm.github.io，阿里云官网公告 |
| 月之暗面 Kimi | moonshot.cn 官方公告 |
| 智谱 | zhipuai.cn / z.ai 官方公告 |
| 字节豆包 | 火山引擎官网公告 |

## 第二层 · X 官方账号

AI 圈很多消息最先出现在 X 上。X 网站本身不允许自动读取，所以用 `site:x.com 账号名` 在搜索引擎里查。
公司官方账号的帖子算一手来源；个人账号只用来发现线索，必须找到第一层或第三层的确认才能写。

- 公司：@OpenAI、@OpenAIDevs、@AnthropicAI、@claudeai、@GoogleDeepMind、@AIatMeta、@deepseek_ai、@Alibaba_Qwen、@Kimi_Moonshot
- 人物（只作线索）：@sama、@demishassabis、@karpathy

## 第三层 · 主流媒体

- 英文：Reuters、Bloomberg、Financial Times、The Information、The Verge、TechCrunch、CNBC、Axios
- 中文：机器之心、量子位、36氪、晚点 LatePost、财新

付费墙网站（Bloomberg、The Information、FT）读不到全文时，只用标题和其他媒体的转述，并在正文里写明是据某某报道。

## 第四层 · AI 与教育

读者重点关注，每期必查。

- EdSurge、Inside Higher Ed、Times Higher Education
- 中国教育部（moe.gov.cn）、中国教育报
- 各 AI 公司的教育产品公告（ChatGPT Edu、Claude for Education、Gemini for Education 等）

## 第五层 · 查漏

只用来发现前四层漏掉的新闻，不能当出处。发现线索后必须回到前四层找确认。

- Techmeme、Hacker News 首页
- news.smol.ai（汇总 X、Reddit、Discord 的 AI 讨论；2026 年 9 月检查时最近一期停在 9/9，更新不稳定）

## 规则

1. 每条新闻至少要有一个第一层到第四层的来源。
2. 只在个人 X 账号或论坛出现、没有得到确认的消息：标题前加「传闻：」，分数不超过 5，不能做头条。
3. 不能单独作为出处：Wikipedia、SEO 汇总站、AI 工具目录站、没有署名的聚合号。
4. 当期的 `scan` 字段记录：实际检查过的来源名称（`checked`，按上面的写法）、看过的候选新闻条数（`candidates`）。
