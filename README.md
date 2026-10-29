# xhs-wa-contact-hunter

一个 DSH Agent Skill：**在小红书（或同类内容社区）的评论区里挖掘主动留下联系方式的人，然后在 WhatsApp Web 上逐个建联、发送差异化开场白。**

不是爬虫，不是群发工具。它是一套「人机协作 + 有风控边界」的操作流程，配三个可独立运行的小脚本。

## 为什么需要这套东西

在小红书找「求互养号 / 求搭子 / 求合作」的人，看起来很简单：搜关键词、翻评论、加号码。实际做起来有四个坎：

1. **平台会过滤新评论里的手机号。** 越新的评论越可能只剩一句「加我」，明文号码反而藏在 24 小时以上的老评论里；
2. **搜索用「最新」排序会毁掉相关性。** 当日匹配内容太少时，平台直接填充推荐流，返回一堆完全不相关的笔记；
3. **评论区图片里贴的二维码有两种格式**，一种能在网页端还原出手机号，另一种只是 Messenger 专用令牌，拿不到号码；
4. **一晚上加太多陌生人会被风控。** 这是这套流程真正的失败模式。

这个 Skill 把上面四条都写成了明确规则，Agent 照着做就不会重复踩坑。

## 目录结构

```
xhs-wa-contact-hunter/
├── SKILL.md                          # 入口：核心认知 + 六步主流程 + 五条硬约束
├── references/
│   ├── xhs-harvest.md                # 检索、筛选面板、时间戳读法、评论分层规律
│   ├── qr-decode.md                  # 二维码下载、解码、两种 payload 的区别与还原步骤
│   ├── whatsapp-web-ops.md           # WhatsApp Web 建联操作序列、话术结构、回复应对
│   └── risk-control.md               # 数量上限、账号前置条件、行为节奏、触发风控后处理
├── scripts/
│   ├── decode_qr.py                  # 多策略二维码解码（原图/灰度/Otsu/放大/锐化/裁剪）
│   ├── extract_contacts.py           # 从文本或 CSV 抽电话、wa.me、微信并规范化去重
│   └── leads.py                      # 线索台账：追加、去重、状态流转、回复率统计
└── assets/
    └── message-templates.md          # 四种切入点的话术骨架与变体规则
```

## 安装

作为 DSH Skill 使用，直接放进本机 skills 目录：

```bash
git clone https://github.com/<you>/xhs-wa-contact-hunter.git \
  ~/.dsh/skills/xhs-wa-contact-hunter
```

Windows：

```powershell
git clone https://github.com/<you>/xhs-wa-contact-hunter.git `
  "$env:USERPROFILE\.dsh\skills\xhs-wa-contact-hunter"
```

DSH 会热加载，无需重启。之后 Agent 在匹配场景下会自动调用，你也可以显式说「用 xhs-wa-contact-hunter 这个技能」。

## 依赖

```bash
pip install opencv-python
```

只有二维码解码需要第三方库，其余均为 Python 3.9+ 标准库。

## 脚本用法

```bash
# 解码评论区二维码（支持一次多张，也支持按目录批量）
python scripts/decode_qr.py ~/Downloads/xxx_来自小红书网页版.jpg

# 从评论记录里抽联系方式（一行一条，字段用 | 分隔：昵称|时间|地区|正文）
python scripts/extract_contacts.py comments.txt --out leads_raw.csv

# 导入台账
python scripts/leads.py --file leads.csv import leads_raw.csv

# 更新状态 / 看统计
python scripts/leads.py --file leads.csv status --number +8613800000000 --to sent
python scripts/leads.py --file leads.csv stats
```

`leads.csv` 的字段：

```
号码, 昵称, 来源帖, 评论时间, 地区, 渠道, 状态, 发送时间, 最后更新, 备注
```

状态流转：`new → verified → sent → replied → agreed`，另有 `refused / no_whatsapp / dead`。

## 两条最重要的规则

**一、发送前必须验证账号存在。** 在 WhatsApp 新聊天面板输入号码，只有出现条目才说明注册了 WhatsApp；完全没条目就是没注册，不要盲发。

**二、单账号单晚新建陌生会话不超过 5 个。** 达到上限就停手，先把已有对话做深。这条线的依据是平台对「短时间主动新建多个陌生会话」的判定逻辑。

## 适用范围与边界

这套骨架适用于任何「社区留联系方式 → 即时通讯建联」的场景：达人招募、跨境卖家找搭子、本地服务获客，换关键词和话术即可。

**请只处理公开发布、且对方主动求联系的线索。** 评论区里被动提及的第三方号码不要用。每条线索保留来源帖 URL 与评论时间，这是「对方主动留联系方式」的唯一凭据。

## License

MIT
