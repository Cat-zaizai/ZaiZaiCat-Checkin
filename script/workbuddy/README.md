# WorkBuddy 自动签到脚本

WorkBuddy（腾讯 CodeBuddy）每日签到脚本，支持多账号、令牌自动续期、账号批量导入。

签到接口实现参考 [cockpit-tools](https://github.com/jlcodes99/cockpit-tools) 项目中 WorkBuddy 自动签到模块的实现，与官方客户端行为保持一致。

## ✨ 功能特性

- 🔐 **多账号支持** - 依次处理配置中的所有账号，账号间随机延迟 5-10 秒
- 📥 **账号导入** - 一键导入官方 WorkBuddy 客户端当前登录账号，无需手动抓包；也支持从 cockpit-tools 批量导入
- 🔁 **令牌自动续期** - `access_token` 过期时用 `refresh_token` 自动换新并写回配置
- 🎯 **智能判重** - 先查签到状态，今日已签到则跳过，不重复请求
- ⏱️ **随机错峰** - 启动后在时间窗口内随机延迟，避开请求高峰
- 📊 **结果推送** - 复用项目统一推送模块，输出积分与连签天数

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | 主入口，多账号签到编排与结果推送 |
| `api.py` | 接口封装：签到状态查询、每日签到、令牌刷新 |
| `import_accounts.py` | 账号导入工具：官方客户端 / cockpit-tools / JSON 文件 |

## 📦 安装依赖

```bash
pip install requests pycryptodome
```

## ⚙️ 配置说明

账号配置写在项目根目录的 `config/token.json` 的 `workbuddy` 节点下：

```json
{
  "workbuddy": {
    "accounts": [
      {
        "account_name": "主号",
        "access_token": "你的访问令牌",
        "refresh_token": "你的刷新令牌",
        "uid": "你的用户ID",
        "enterprise_id": "",
        "domain": ""
      }
    ]
  }
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `account_name` | 否 | 账号备注名，用于日志和推送显示 |
| `access_token` | **是** | 访问令牌，对应请求头 `Authorization: Bearer` |
| `refresh_token` | 否 | 刷新令牌，缺失时令牌过期只能手动重新导入 |
| `uid` | 否 | 用户 ID，对应请求头 `X-User-Id` |
| `enterprise_id` | 否 | 企业 ID，个人账号留空 |
| `domain` | 否 | 域名，一般留空 |

> **强烈建议填写 `refresh_token`**，否则令牌过期后签到会一直失败，需要人工介入。

## 📥 导入账号

### 方式一：从官方 WorkBuddy 客户端导入（推荐）

本机登录过 [WorkBuddy / CodeBuddy](https://www.codebuddy.cn) 桌面客户端的话，直接运行：

```bash
python import_accounts.py
```

脚本会自动探测官方客户端凭据库（`%APPDATA%/WorkBuddy/User/globalStorage/state.vscdb`），解密并导入**当前登录账号**，无需抓包。逻辑与 [cockpit-tools](https://github.com/jlcodes99/cockpit-tools) 的本机导入功能对齐（Windows 使用 DPAPI + AES-GCM 解密，macOS 使用 Keychain + AES-CBC）。

### 方式二：从 cockpit-tools 导入

如果本机装了 [cockpit-tools](https://github.com/jlcodes99/cockpit-tools) 并管理了多个 WorkBuddy 账号，同样直接运行 `python import_accounts.py` 即可——脚本会同时探测 cockpit-tools 数据目录（含 `C:/Users/用户名/.antigravity_cockpit`），批量导入全部账号。

> **加密账号自动解密**：cockpit-tools 新版将账号以 AES-256-GCM 加密存储，密钥在本机 `secure-account-storage.key`。导入工具会自动找到该密钥并解密，无需任何额外操作。明文与加密两种格式均已兼容。

先预览不写入：

```bash
python import_accounts.py --list
```

### 方式三：指定路径导入

自动探测失败时（例如客户端装在非默认位置），手动指定目录：

```bash
python import_accounts.py --path "C:/Users/你的用户名/AppData/Roaming/cockpit-tools"
```

也支持直接指定单个账号 JSON 文件，或包含账号数组的 JSON 文件：

```bash
python import_accounts.py --path "D:/backup/my_accounts.json"
```

### 导入行为说明

- 按 `uid`（无则用 `email`）去重，**重复导入不会产生重复账号**（官方客户端与 cockpit-tools 来源之间同样自动合并）
- 已存在的账号只更新令牌等认证信息，**保留你自定义的 `account_name`**
- cockpit-tools 的索引文件 `workbuddy_accounts.json` 只有摘要没有令牌，会自动跳过

### 方式四：手动填写

抓包获取令牌后，按上文配置格式手动填入 `config/token.json`。

## 🔄 令牌有效期与自动续期

根据实际令牌解析（JWT），CodeBuddy 签发规则如下：

| 令牌 | 有效期 | 轮换方式 |
|------|--------|---------|
| `access_token` | 60 天 | 过期后用 `refresh_token` 换新 |
| `refresh_token` | 90 天 | 刷新时随 `access_token` 一起换新，从刷新时刻重新计 90 天 |

脚本在签到遇到令牌过期时会自动刷新并回写配置。**只要脚本每 90 天内至少成功运行一次，令牌即可无限续期**；连续 90 天未运行才需要重新导入账号。

### 与 cockpit-tools 并行使用

[cockpit-tools](https://github.com/jlcodes99/cockpit-tools) 的自动签到会在执行时刷新令牌（refresh token 轮换），这会使 `config/token.json` 里的旧令牌立即失效。脚本**不会自动从本机拉取令牌**，若两边同时使用，cockpit 侧刷新令牌后需重新运行 `import_accounts.py` 更新，或建议二选一，避免重复签到。

## 🚀 使用方法

```bash
python main.py
```

执行流程：

```
随机延迟 0~10 分钟（错峰，可用 WORKBUDDY_JITTER_MAX 环境变量调整）
  ↓
加载账号配置
  ↓
循环处理每个账号
  ├─ 查询签到状态
  ├─ 今日已签到 → 跳过
  ├─ 活动未开启 → 跳过
  ├─ 未签到 → 执行签到
  └─ 令牌过期 → 自动刷新后重试，并将新令牌写回配置
  ↓
输出统计信息并推送通知
```

## ⏰ 配置定时任务

### Windows 任务计划程序

1. 打开「任务计划程序」→ 创建基本任务
2. 触发器：每天，建议设在 `07:00`~`09:00` 之间
3. 操作：启动程序
   - 程序：`python.exe` 的完整路径
   - 参数：`main.py` 的完整路径（如 `C:\qiandao\script\workbuddy\main.py`）

> 脚本会自动定位项目根目录并读取配置，无需设置「起始于」。如需在锁屏/未登录时也执行，可把任务的「安全选项」改为「不管用户是否登录都要运行」并保存密码。

### 青龙面板

脚本头部已包含青龙任务声明，默认每天 `08:30` 执行：

```
cron: 30 8 * * *
```

## 🔌 接口说明

| 用途 | 方法与路径 |
|------|-----------|
| 签到状态 | `POST https://www.codebuddy.cn/v2/billing/meter/checkin-activity-status` |
| 状态回退 | `POST https://www.codebuddy.cn/v2/billing/meter/checkin-status` |
| 每日签到 | `POST https://www.codebuddy.cn/v2/billing/meter/daily-checkin` |
| 刷新令牌 | `POST https://www.codebuddy.cn/v2/plugin/auth/token/refresh` |

响应约定：仅 `code == 0` 视为成功，业务数据在 `data` 字段中，字段名兼容下划线与驼峰两种写法。

## ⚠️ 注意事项

1. **令牌安全** - `access_token` 等同于账号密码，切勿泄露或提交到公开仓库
2. **签到时间** - 脚本已内置启动随机延迟避开整点，账号间另有 5-10 秒随机间隔，无需额外配置
3. **令牌过期** - 若日志提示「令牌已过期，请重新导入账号」，重新运行 `import_accounts.py` 即可
4. **多账号** - 账号间已内置 5-10 秒随机间隔，无需额外配置
5. **个别账号被服务端拒绝** - 少数账号（如令牌类型为 `Offline`/`console` 的特殊账号）即便令牌未过期，也会被签到接口网关直接返回 401。这属于账号侧凭据问题，脚本无法绕过；可在 cockpit-tools 中重新登录该账号后重新导入，或将其从配置中移除。

---

**免责声明**: 本脚本仅供学习交流使用，使用产生的一切后果由使用者自行承担。
