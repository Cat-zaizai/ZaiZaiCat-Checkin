# Trae CN 每日自动签到

为 Trae CN 账号自动领取每日签到积分，支持多账号。接口参考 cockpit-tools / trae-mate / TRAE-Automatic-sign-in 相关实现。

## 快速使用（推荐：网页会话模式，支持多账号）

1. **安装依赖**

```bash
pip install requests pycryptodome
```

2. **获取账号会话**：浏览器登录 https://www.trae.cn → F12 → 应用(Application) → Cookies → 复制 `sessionid` 的值（约 60 天有效）。**只需这一个 cookie**，`sid_tt`/`uid_tt`/`passport_*`/`X-Cloudide-Session` 等均不需要。

3. **写入配置**：在 `config/token.json` 的 `trae` 节点添加账号（`token.json` 已在 .gitignore，不会提交）：

```json
{
  "trae": {
    "accounts": [
      {
        "account_name": "主号",
        "sessionid": "粘贴 sessionid 的值"
      }
    ]
  }
}
```

> 只需 `sessionid` 一个字段（值填浏览器 Cookie 里的 `sessionid`）即可，**不需要再填旧式的 `session`（X-Cloudide-Session）**。脚本每次运行先调 `/cloudide/api/v3/trae/Login` 自动刷新 `X-Cloudide-Session`（与浏览器打开 trae.cn 的续期链路一致），再换 JWT 签到，因此 `session`/`sid_tt`/`uid_tt` 等都不需要配置，约 60 天不用手工更新。`account_name` 用于通知里认出账号（通知会显示为 `名称(#UserID后6位)`，服务端不提供昵称，故以配置名为主、UserID 尾号兜底，便于区分同名条目）；`user_id`/`access_token`/`expires_at`/`device_id` 为可选增强字段（导入去重、桌面令牌回退），没有也不影响签到。

4. **运行**

```bash
python script/trae/main.py            # 执行签到
python script/trae/main.py --dry-run  # 先预览：只查状态不签到
```

每天定时跑一次即可（Windows 任务计划 或 青龙 cron `30 8 * * *`）。

## 备用：桌面令牌模式（单账号）

如果你没有网页 session，也可以用官方客户端登录态自动导入：

```bash
python script/trae/import_accounts.py             # 自动导入本机 Trae/cockpit 账号
python script/trae/import_accounts.py --list      # 先预览
```

导入后会在 `trae.accounts` 里填好 `access_token`。注意此模式**受设备限制**：一个客户端设备每天通常只能有一个账号签到成功；多账号若提示设备错误，请改用上面的网页会话模式。

## 文件说明

| 文件 | 作用 |
|------|------|
| `main.py` | 签到主入口：多账号编排、判重、结果推送 |
| `api.py` | 接口封装（网页会话 / 桌面令牌） |
| `import_accounts.py` | 账号导入（官方客户端 / cockpit-tools） |
| `web_checkin.py` | 单账号快速验证工具：`python web_checkin.py --session "<值>"` |

## 常见问题

- **日志提示"已用长效 Cookie 刷新 session"**：正常，脚本每次运行自动续期，无需手工更新
- **需要配多少个 cookie？**：只需 `sessionid` 一个（约 60 天有效）。`sid_tt`/`uid_tt`/`passport_*`/`X-Cloudide-Session` 等均已实测可去掉，不填也不影响刷新与签到
- **还要填旧式的 `session` 吗？**：不用。配了 `sessionid` 后脚本自动刷新并填充 `X-Cloudide-Session`，`session` 字段可留空或删除
- **日志提示"sessionid 失效"**：`sessionid` 失效（约 60 天），回浏览器重新复制 `sessionid`
- **日志提示"请更新 session"**：账号只配了旧式 `session`（未配 `sessionid`）且已过期，补配 `sessionid` 即可
- **日志提示"缺少签到设备 device_id"**：该账号走的是桌面令牌模式但没有可用设备，配 `sessionid` 走网页模式即可
- **结果推送**：复用项目统一推送（`config/notification.json` 配置）

---

**免责声明**：本脚本仅供学习交流使用，使用产生的一切后果由使用者自行承担。
