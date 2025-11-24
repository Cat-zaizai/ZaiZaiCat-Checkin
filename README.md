# ZaiZaiCat-Checkin 🐱

一个支持多平台、多账号的自动签到和任务执行工具集，专为青龙面板（Qinglong Panel）设计。

> **⚠️ 免责声明**  
> 本项目中的大量代码由 AI 辅助编写生成，代码规范和格式可能存在不足之处，敬请见谅。  
> 本项目仅供学习交流使用，请勿用于商业用途。使用本项目所造成的一切后果由使用者自行承担。

## 📋 目录

- [功能特性](#功能特性)
- [支持平台](#支持平台)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [安装部署](#安装部署)
- [配置说明](#配置说明)
- [使用方法](#使用方法)
- [通知推送](#通知推送)
- [常见问题](#常见问题)
- [更新日志](#更新日志)
- [开源协议](#开源协议)

## ✨ 功能特性

- 🚀 **多平台支持** - 集成多个平台的自动签到和任务执行功能
- 👥 **多账号管理** - 每个平台支持配置多个账号，自动循环执行
- 📱 **通知推送** - 集成 Bark 推送，实时获取执行结果
- 🔄 **智能延迟** - 模拟人工操作，避免被检测
- 📝 **详细日志** - 完整的执行日志记录，方便问题排查
- 🎯 **任务管理** - 自动获取并完成各平台的日常任务
- ⚙️ **灵活配置** - 统一的配置文件管理，易于维护

## 🎪 支持平台

### 1. 顺丰速运（SF Express）
- ✅ 每日签到
- ✅ 积分任务自动完成
- ✅ 任务列表管理
- ✅ 积分查询

**脚本路径**: `script/sf/main.py`

### 2. 恩山论坛（Enshan）
- ✅ 每日签到
- ✅ 签到状态查询
- ✅ 积分信息统计

**脚本路径**: `script/enshan/sign_in.py`

### 3. 看雪论坛（Kanxue）
- ✅ 每日签到
- ✅ 用户信息查询
- ✅ 签到记录管理

**脚本路径**: `script/kanxue/sign_in.py`

### 4. 上海杨浦（SHYP）
- ✅ 任务列表获取
- ✅ 积分任务完成
- ✅ 签到信息查询
- ✅ 商品自动抢购（可选）

**脚本路径**: `script/shyp/main.py`

### 5. 华润通（Huaruntong）
支持多个子平台：
- **万象星（999）**: 签到、积分查询
- **微信小程序版**: 签到送积分
- **Ole'精品超市**: 签到任务
- **文体未来荟**: 签到任务

**脚本路径**: `script/huaruntong/*/main.py`


## ✅ 脚本可用性状态

以下是各平台脚本的当前可用性状态：

| 平台           | 脚本路径 | 状态 | 说明 |
|--------------|---------|------|------|
| 🚚 顺丰速运      | `script/sf/main.py` | ✅ 可用 | 支持签到和积分任务 |
| 📱 恩山论坛      | `script/enshan/sign_in.py` | ✅ 可用 | 支持每日签到 |
| 🔐 看雪论坛      | `script/kanxue/sign_in.py` | ✅ 可用 | 支持每日签到 |
| 📺 上海杨浦      | `script/shyp/main.py` | ✅ 可用 | 支持任务列表和积分任务 |
| 🏢 华润通-万象星   | `script/huaruntong/999/main.py` | ✅ 可用 | 支持答题签到 |
| 💳 华润通-微信版   | `script/huaruntong/huaruntong_wx/main.py` | ✅ 可用 | 支持签到送积分 |
| 🛒 华润通-Ole'  | `script/huaruntong/ole/main.py` | ✅ 可用 | 支持签到任务 |
| 🎯 华润通-文体未来荟 | `script/huaruntong/wentiweilaihui/main.py` | ✅ 可用 | 支持签到和积分查询 |
### 状态说明

- ✅ **可用**: 脚本完整且功能正常，可以直接使用
- ⚠️ **部分可用**: 脚本基本可用，但可能存在某些功能限制
- 🚧 **开发中**: 脚本正在开发或测试阶段
- ❌ **不可用**: 脚本存在问题或已废弃

### 使用建议

1. **推荐使用**: 所有标记为"✅ 可用"的脚本都已经过测试，可以放心使用
2. **配置要求**: 使用前请确保在 `config/token.json` 中正确配置了相应平台的账号信息
3. **Cookie 有效期**: 建议定期更新 Cookie 等认证信息，以保证脚本正常运行
4. **测试建议**: 首次使用新脚本时，建议先在本地测试一次，确认功能正常后再部署到青龙面板

## 📁 项目结构

```
ZaiZaiCat-Checkin/
├── config/                      # 配置文件目录
│   └── token.json              # 统一的账号配置文件
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
│   └── huaruntong/             # 华润通
│       ├── 999/               # 万象星
│       ├── huaruntong_wx/     # 微信小程序
│       ├── ole/               # Ole'精品超市
│       └── wentiweilaihui/    # 文体未来荟
├── notification.py             # 通知推送模块
├── LICENSE                     # MIT 开源协议
└── README.md                   # 项目说明文档
```

## 🔧 环境要求

- **Python**: 3.7+ (推荐 3.9+)
- **依赖库**:
  - `requests` - HTTP 请求库
  - `logging` - 日志记录
  - 其他标准库

## 📦 安装部署

### 1. 克隆项目

```bash
git clone https://github.com/Cat-zaizai/ZaiZaiCat-Checkin.git
cd ZaiZaiCat-Checkin
```

### 2. 安装依赖

```bash
pip install requests
```

### 3. 配置账号信息

编辑 `config/token.json` 文件，按照平台添加账号信息。

### 4. 青龙面板部署（推荐）

1. 将整个项目上传到青龙面板的 `scripts` 目录
2. 在青龙面板中添加定时任务
3. 配置环境变量（用于推送通知）

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

# 什么值得买 - 每天 07:00
0 7 * * * python3 /ql/scripts/ZaiZaiCat-Checkin/smzdm/sign_daily_task/main.py
```

## ⚙️ 配置说明

### 配置文件结构

`config/token.json` 采用 JSON 格式，按平台分类存储账号信息。

#### 示例配置

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
  },
  "kanxue": {
    "kanxue": {
      "accounts": [
        {
          "account_name": "默认账号",
          "cookie": "你的Cookie",
          "csrf_token": "CSRF Token",
          "user_agent": "User-Agent"
        }
      ]
    }
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

## 🚀 使用方法

### 本地运行

```bash
# 运行顺丰速运签到
python3 script/sf/main.py

# 运行恩山论坛签到
python3 script/enshan/sign_in.py

# 运行看雪论坛签到
python3 script/kanxue/sign_in.py

# 运行上海云杨浦任务
python3 script/shyp/main.py

# 运行什么值得买任务
python3 smzdm/sign_daily_task/main.py
```

### 青龙面板运行

在青龙面板中配置定时任务后，脚本会按照设定的时间自动执行。

### 查看日志

- 脚本执行日志会同时输出到控制台和日志文件
- 日志文件位置：各脚本目录下的 `.log` 文件
- 青龙面板日志：在任务管理中查看执行日志

## 📱 通知推送

本项目集成了 Bark 推送功能，可以将执行结果实时推送到你的 iOS 设备。

### 配置 Bark 推送

在青龙面板的 `config.sh` 或环境变量中添加：

```bash
# 必需参数
export BARK_PUSH="你的Bark设备Key或完整URL"

# 可选参数
export BARK_ICON="https://example.com/icon.png"  # 推送图标
export BARK_SOUND="birdsong"                      # 推送声音
export BARK_GROUP="签到通知"                       # 推送分组
export BARK_LEVEL="active"                        # 推送级别
export BARK_URL="https://example.com"             # 点击跳转URL
```

### Bark 推送级别

- `active`: 默认级别，立即亮屏显示通知
- `timeSensitive`: 时效性通知，专注模式下也会显示
- `passive`: 被动通知，不会立即显示

### 推送示例

```python
from notification import send_notification, NotificationLevel, NotificationSound

# 基础推送
send_notification("签到成功", "今日签到已完成")

# 自定义推送
send_notification(
    "重要通知",
    "这是一条重要消息",
    level=NotificationLevel.TIME_SENSITIVE,
    sound=NotificationSound.ALARM
)
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

### 2025-11-24
- ✨ 新增顺丰速运签到脚本
- ✨ 新增恩山论坛签到脚本
- ✨ 新增看雪论坛签到脚本
- ✨ 新增上海杨浦任务脚本
- ✨ 新增华润通多个子平台支持
- ✨ ✨ 999 签到功能完善
- ✨ ✨ 华润通微信小程序签到功能完善
- ✨ ✨ Ole' 精品超市签到功能完善
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
- 感谢 AI 辅助编写代码
- 感谢青龙面板提供的自动化平台

## 📧 联系方式

如有问题或建议，欢迎通过以下方式联系：

- GitHub Issues: [提交问题](https://github.com/Cat-zaizai/ZaiZaiCat-Checkin/issues)
- Email: 项目作者邮箱（如有）

---

**⭐ 如果这个项目对你有帮助，欢迎给个 Star！**

*最后更新: 2025-11-24*

