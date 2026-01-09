# ZaiZaiCat-Checkin 🐱

自用每日签到脚本,青龙签到脚本

> **⚠️ 免责声明**  
> 本项目中的大量代码由 AI 辅助编写生成，代码规范和格式可能存在不足之处，敬请见谅。  
> 本项目仅供学习交流使用，请勿用于商业用途。使用本项目所造成的一切后果由使用者自行承担。


## ✨ 功能特性

- 🚀 **多平台支持** - 集成多个平台的自动签到和任务执行功能
- 👥 **多账号管理** - 每个平台支持配置多个账号，自动循环执行
- 📱 **通知推送** - 集成 多平台 推送，实时获取执行结果
- 🔄 **智能延迟** - 模拟人工操作，避免被检测
- 📝 **详细日志** - 完整的执行日志记录，方便问题排查
- 🎯 **任务管理** - 自动获取并完成各平台的日常任务
- ⚙️ **灵活配置** - 统一的配置文件管理，易于维护

## ✅ 脚本可用性状态

以下是各平台脚本的当前可用性状态：

| 平台           | 脚本路径 | 状态 | 说明                  |
|--------------|---------|------|---------------------|
| 🚚 顺丰速运      | `script/sf/main.py` | ✅ 可用 | 支持签到和积分任务           |
| 📱 恩山论坛      | `script/enshan/sign_in.py` | ✅ 可用 | 支持每日签到              |
| 🔐 看雪论坛      | `script/kanxue/sign_in.py` | ✅ 可用 | 支持每日签到              |
| 📺 上海杨浦      | `script/shyp/main.py` | ✅ 可用 | 支持任务列表和积分任务         |
| 🏢 华润通-万象星   | `script/huaruntong/999/main.py` | ✅ 可用 | 支持答题签到              |
| 💳 华润通-微信版   | `script/huaruntong/huaruntong_wx/main.py` | ✅ 可用 | 支持签到送积分             |
| 🛒 华润通-Ole'  | `script/huaruntong/ole/main.py` | ❌ 不可用 | 需要动态获取微信code换取token |
| 🎯 华润通-文体未来荟 | `script/huaruntong/wentiweilaihui/main.py` | ✅ 可用 | 支持签到和积分查询           |
| 👟 鸿星尔克      | `script/erke/main.py` | ✅ 可用 | 支持签到和积分明细查询         |
| 📝 WPS Office  | `script/wps/main.py` | ✅ 可用 | 支持自动签到和抽奖           |
| 💰 什么值得买      | `script/smzdm/sign_daily_task/main.py` | ✅ 可用 | 支持每日签到和众测任务         |

### 状态说明

- ✅ **可用**: 脚本完整且功能正常，可以直接使用
- ⚠️ **部分可用**: 脚本基本可用，但可能存在某些功能限制
- 🚧 **开发中**: 脚本正在开发或测试阶段
- ❌ **不可用**: 脚本存在问题或已废弃

### 使用建议

1. **推荐使用**: 所有标记为"✅ 可用"的脚本都已经过测试，可以放心使用
2. **配置要求**: 使用前请确保在 `config/token.json` 中正确配置了相应平台的账号信息
3. **Cookie 有效期**: 建议定期更新 Cookie 等认证信息，以保证脚本正常运行
4. **测试建议**: 使用青龙命令拉取脚本可能会出现混乱的问题,建议直接clone整个项目到青龙的 scripts 目录下


## 🔧 环境要求

- **Python**: 3.7+ (推荐 3.9+)
- **依赖库**:
  - `requests` - HTTP 请求库
  - `pycryptodome` - 加密库（WPS 签到需要）
  - `logging` - 日志记录
  - 其他标准库

## 📦 安装部署

### 1. 青龙面板部署（推荐）

**青龙部署教程**

1. 将整个项目上传到青龙面板的 `scripts` 目录
2. 在青龙面板中添加定时任务
3. 配置环境变量（用于推送通知）

#### 青龙命令行拉库

```bash
# ql repo <repo_url> <whitelist> <blacklist> <dependence> <branch> <extensions>
ql repo https://github.com/Cat-zaizai/ZaiZaiCat-Checkin.git "main.py|sign_in.py" "" ".py|.js|.json" "" "ts js py json"
```

#### 青龙面板订阅

`订阅管理 -> 创建订阅`，表单填写示例：
- 名称：ZaiZaiCat-Checkin
- 链接：https://github.com/Cat-zaizai/ZaiZaiCat-Checkin.git
- 分支：`main`
- 定时：`0 0 1 * * *`
- 白名单：`main|sign_in`
- 黑名单：`(留空)`
- 依赖文件：`.py|.js|.json`
- 文件后缀：`ts js py json`

#### 通用环境变量与配置

- 入口：`脚本管理 -> ZaiZaiCat-Checkin -> config`
- 创建`token.json`文件：项目所需账号配置文件,可参考 `config/token_example.json` 示例进行编辑
- `notification.json`：统一推送配置文件

#### 依赖下载安装
- 入口：`依赖管理 -> Python3 -> 创建依赖`
- 内容： PyExecJS pycryptodome

> 说明：青龙拉库脚本默认定时规则为 `1 1 1 1 1`（不自动执行），如需运行请自行调整成对应任务所需的 cron 表达式。

> 提示：如果拉取项目超时，可尝试使用 GitHub 镜像/加速服务，或切换网络后重试。



### 2. 其他部署方式

**其他部署教程**

1. 克隆项目
   ```bash
   git clone https://github.com/Cat-zaizai/ZaiZaiCat-Checkin.git
   cd ZaiZaiCat-Checkin
   ```
2. 安装依赖
   ```bash
   # 基础依赖
   pip install requests

   # WPS 签到需要的加密库
   pip install pycryptodome
   
   # 顺丰脚本所需的依赖
   pip install PyExecJS
   ```
3. 配置账号信息：创建 `config/token.json`文件,参考[template_token.json](config/template_token.json) 为各平台添加账号配置。

4. 添加定时任务

**定时任务示例**:
```bash
# 顺丰速运 - 每天 08:00
0 8 * * * python3 /ql/scripts/ZaiZaiCat-Checkin/script/sf/main.py

# 恩山论坛 - 每天 09:00
0 9 * * * python3 /ql/scripts/ZaiZaiCat-Checkin/script/enshan/sign_in.py

# 看雪论坛 - 每天 09:30
30 9 * * * python3 /ql/scripts/ZaiZaiCat-Checkin/script/kanxue/sign_in.py

# 上海杨浦 - 每天 10:00
0 10 * * * python3 /ql/scripts/ZaiZaiCat-Checkin/script/shyp/main.py

# 鸿星尔克 - 每天 08:30
30 8 * * * python3 /ql/scripts/ZaiZaiCat-Checkin/script/erke/main.py

# WPS Office - 每天 07:30
30 7 * * * python3 /ql/scripts/ZaiZaiCat-Checkin/script/wps/main.py

# 什么值得买 - 每天 07:00
0 7 * * * python3 /ql/scripts/ZaiZaiCat-Checkin/script/smzdm/sign_daily_task/main.py
```

### 3. 配置账号信息

编辑 `config/token.json` 文件，按照平台添加账号信息。

## ⚙️ 配置说明

### 配置文件结构

`config/token.json` 采用 JSON 格式，按平台分类存储账号信息。

#### 示例配置
此处需要运行什么脚本,则去相关脚本文件夹中的md文档查看对应的配置说明。
```json
{
  "sf": {
    "accounts": [
      {
        "account_name": "账号1",
        "cookies": "你的Cookie",
        "user_id": "用户ID",
        "user_agent": "User-Agent",
        "channel": "weixin",
        "device_id": "设备ID"
      }
    ]
  },
  "enshan": {
    "accounts": [
      {
        "account_name": "默认账号",
        "cookies": "你的Cookie",
        "formhash": "表单hash",
        "user_agent": "User-Agent"
      }
    ]
  }
}
```

### 获取配置信息

#### 1. Cookie 获取方法

1. 使用浏览器打开对应平台网站
2. 登录你的账号
3. 按 `F12` 打开开发者工具
4. 切换到 `Network` 标签
5. 刷新页面或进行操作
6. 找到请求，查看 `Request Headers` 中的 `Cookie`
7. 复制完整的 Cookie 字符串

#### 2. Token 获取方法

- 部分平台（如华润通、上海杨浦）使用 Token 认证
- 使用抓包工具（如 Charles、Fiddler）获取
- 或从浏览器开发者工具中的请求头查找 `Authorization` 字段

#### 3. 其他参数

- `user_agent`: 从请求头中的 `User-Agent` 字段复制
- `device_id`: 从请求参数或请求头中获取
- `formhash`/`csrf_token`: 从页面源码或请求中提取


## 📱 通知推送

本项目已扩展为支持多平台统一推送（而不仅限于 Bark），通过一个集中配置文件或环境变量进行管理。
参考项目: [dailycheckin](https://github.com/Sitoi/dailycheckin)

支持的推送平台（示例，具体以 `notification.py` 中实现为准）：
- Bark
- Server酱 (SCKEY / SENDKEY)
- Server酱 Turbo
- CoolPush
- Qmsg酱
- Telegram
- 飞书 (Feishu)
- 钉钉 (DingTalk)
- 企业微信群机器人
- 企业微信应用消息
- PushPlus
- Gotify
- Ntfy
- PushDeer

配置方式（优先级）
1. `config/notification.json` 中的对应字段（推荐用于本地与容器持久化配置）
2. 环境变量（适用于青龙面板或临时覆盖）

配置文件位置
- 文件路径：`config/notification.json`（已新增）

如何使用
- 编辑 `config/notification.json` 添加或修改推送服务的配置（推荐）
- 或在部署环境中通过环境变量设置对应字段（示例见下）
- 在脚本中通过 `from notification import send_notification` 调用统一发送接口：

示例：
```python
from notification import send_notification
send_notification("签到结果", "账号 A: 成功\n账号 B: 失败")
```

示例配置（`config/notification.json`）
```json
{
  "bark": {
    "push": "https://api.day.app/your_bark_key_or_url",
    "icon": "",
    "sound": "birdsong",
    "group": "ZaiZaiCat-Checkin",
    "level": "active",
    "url": ""
  },
  "server": {
    "sckey": "",
    "sendkey": ""
  },
  "pushplus": {
    "token": "",
    "topic": ""
  },
  "pushdeer": {
    "pushkey": "",
    "url": "https://api2.pushdeer.com/message/push",
    "type": "text"
  },
  "gotify": {
    "url": "",
    "token": "",
    "priority": "3"
  },
  "ntfy": {
    "url": "https://ntfy.sh",
    "topic": "",
    "priority": "3"
  }
}
```

常用环境变量（根据不同服务的字段名称）示例
- BARK_PUSH
- SCKEY / SENDKEY
- PUSHPLUS_TOKEN
- PUSHDEER_PUSHKEY (或 PUSHDEER_PUSHKEY)
- GOTIFY_URL / GOTIFY_TOKEN
- NTFY_TOPIC / NTFY_URL
- QMSG_KEY
- TG_BOT_TOKEN / TG_USER_ID
- FSKEY
- DINGTALK_ACCESS_TOKEN / DINGTALK_SECRET
- QYWX_KEY / QYWX_CORPID / QYWX_AGENTID / QYWX_CORPSECRET / QYWX_TOUSER

说明与注意事项
- 推荐把敏感字段（如 pushkey、token、sckey）放在环境变量或不提交到仓库的配置文件中。
- `notification.py` 的配置读取优先级为：配置文件 > 环境变量 > 默认值。
- PushDeer 支持两种使用方式：
  - 官方在线版：无需自架，使用 `https://api2.pushdeer.com/message/push` 并在 PushDeer 客户端创建 Key；保持 `pushdeer.url` 为默认即可。
  - 自架服务端：将 `pushdeer.url` 指向你的服务地址（例如 `https://your-server.example/push`）。
- 不同推送服务的消息格式与支持的特性（图片、Markdown 等）不同，`notification.py` 中会根据各平台的要求做适配。

示例：通过 PushDeer 发送 Markdown 类型消息时，在 `config/notification.json` 中把 `pushdeer.type` 设置为 `markdown`，并在调用 `send_notification` 时把内容设置为 Markdown 格式。

兼容性与扩展
- 本文档描述的是当前版本支持的平台。如需添加新的推送渠道，可在 `notification.py` 中添加相应的加载、启用检测和发送函数，并在 `config/notification.json` 中加入配置。


## 📁 项目结构

```
ZaiZaiCat-Checkin/
├── config/                      # 配置文件目录
│   └── token.json              # 统一的账号配置文件
│   └── notification.json              # 统一的推送配置文件
├── script/                      # 脚本目录
│   ├── enshan/                 # 恩山论坛
│   │   ├── api.py             # API 接口封装
│   │   └── sign_in.py         # 签到脚本
│   ├── kanxue/                 # 看雪论坛
│   │   ├── api.py
│   │   └── sign_in.py
│   ├── sf/                     # 顺丰速运
│   │   ├── api.py
│   │   └── main.py
│   ├── shyp/                   # 上海杨浦
│   │   ├── api.py
│   │   ├── main.py
│   │   └── auto_buy.py        # 自动抢购脚本
│   ├── huaruntong/             # 华润通
│       ├── 999/               # 万象星
│       ├── huaruntong_wx/     # 微信小程序
│       ├── ole/               # Ole'精品超市
│       └── wentiweilaihui/    # 文体未来荟
│   ├── erke/                   # 鸿星尔克
│       ├── api.py
│       └── main.py
│   └── wps/                    # WPS Office
│       ├── api.py             # API接口和加密模块
│       ├── main.py            # 主程序入口
│       ├── README.md          # WPS脚本说明文档
│       ├── QUICK_START.md     # 快速配置指南
│       ├── CHANGES.md         # 修改说明
│       └── test_config.py     # 配置测试脚本
├── notification.py             # 通知推送模块
├── LICENSE                     # MIT 开源协议
└── README.md                   # 项目说明文档
```

## ❓ 常见问题

### 1. Cookie 失效怎么办？

Cookie 有有效期限制，失效后需要重新获取并更新配置文件。建议定期检查更新。

### 2. 签到失败如何排查？

1. 检查 Cookie 是否过期
2. 查看日志文件中的错误信息
3. 确认账号是否正常（未被封禁）
4. 检查网络连接是否正常

### 3. 如何添加新账号？

在 `config/token.json` 对应平台的 `accounts` 数组中添加新的账号对象即可。

### 4. 如何禁用某个平台？

- 方法1: 删除 `config/token.json` 中对应平台的配置
- 方法2: 在青龙面板中禁用对应的定时任务

### 5. 推送通知没有收到？

1. 检查 `BARK_PUSH` 环境变量是否配置正确
2. 确认 Bark App 已正确安装和配置
3. 检查网络连接是否正常
4. 查看脚本日志中的推送相关信息

### 6. 脚本执行报错怎么办？

1. 查看完整的错误日志
2. 检查 Python 版本和依赖库是否安装
3. 确认配置文件格式是否正确
4. 检查文件权限是否正确

## 📝 更新日志

### 2025-12-18 
- ✨ **WPS脚本新增抽奖相关任务**:
  - 🎟️ 支持自动参与每日抽奖
  - 🎁 支持自动领取抽奖奖励
  - 📝 更新 WPS 脚本说明文档，加入抽奖功能使用说明

### 2025-12-08 v2.0
- ✨ **新增什么值得买(SMZDM)任务模块**: 完整的自动化任务执行系统
  - 📅 **每日签到**: 自动完成每日签到，获取积分奖励
  - 🎯 **众测任务**: 自动执行众测相关任务
    - 浏览文章任务自动完成
    - 互动任务自动处理
    - 智能任务奖励领取
  - 🎯 **互动任务**: 全面的用户互动任务支持
    - 自动浏览指定文章
    - 智能关注用户任务
    - 自动领取任务奖励
  - 👥 **多账号管理**: 支持配置多个账号并行执行
  - 📊 **详细统计**: 完整的任务执行统计和结果汇总
  - 📝 **完善日志**: 详细的执行日志记录和错误追踪

### 2025-12-08
- ✨ 支持多平台统一推送：在 `notification.py` 中新增 多平台推送 支持，并将各平台推送整合到统一接口 `send_notification`。
- 🛠 新增推送配置文件：`config/notification.json`（支持从文件或环境变量加载配置，优先级：文件 > 环境 > 默认）。
- 📝 更新 `README.md` 的“通知推送”文档，加入 使用说明、配置示例和常用环境变量说明。

### 2025-12-01
- ✨ 新增 WPS Office 自动签到脚本
- 📝 更新项目说明文档

### 2025-11-28
- ✨ 新增鸿星尔克签到脚本
- ✨ 支持鸿星尔克积分明细查询功能
- ❌ Ole'精品超市脚本设为不可用（需要动态获取微信code换取token）
- 📝 更新项目说明文档

### 2025-11-24
- ✨ 新增顺丰速运签到脚本
- ✨ 新增恩山论坛签到脚本
- ✨ 新增看雪论坛签到脚本
- ✨ 新增上海杨浦任务脚本
- ✨ 新增华润通多个子平台支持
- ✨ ✨ 999 签到功能完善
- ✨ ✨ 华润通微信小程序签到功能完善
- ✨ ✨ Ole' 精品超市签到功能（已废弃）
- ✨ ✨ 文体未来荟签到功能完善
- ✨ 创建项目 README 文档
- 📝 完善项目说明和使用指南


## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！


## ⚠️ 注意事项

1. 本项目仅供学习交流使用，请勿用于商业用途
2. 使用本项目所造成的一切后果由使用者自行承担
3. 请合理使用自动签到功能，避免对平台造成负担
4. Cookie 等敏感信息请妥善保管，不要泄露给他人
5. 定期更新 Cookie，避免失效影响使用
6. 代码由 AI 辅助生成，可能存在不规范之处

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

- 感谢所有为本项目提供帮助和支持的朋友
- 感谢青龙面板提供的自动化平台

## 📧 联系方式

如有问题或建议，欢迎通过以下方式联系：

- GitHub Issues: [提交问题](https://github.com/Cat-zaizai/ZaiZaiCat-Checkin/issues)
- Email: wusan503@gmail.com

---

**⭐ 如果这个项目对你有帮助，欢迎给个 Star！**

*最后更新: 2025-12-08*
