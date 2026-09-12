# Trae CN 每日自动签到

为 Trae CN 账号自动领取每日签到积分，支持多账号。接口参考 cockpit-tools / trae-mate / TRAE-Automatic-sign-in 相关实现。

## 快速使用（推荐：网页会话模式，支持多账号）

1. **安装依赖**

```bash
pip install requests pycryptodome
```

2. **获取账号会话**：浏览器登录 https://www.trae.cn → F12 → 应用(Application) → Cookies → 复制 `X-Cloudide-Session` 的完整值

3. **写入配置**：在 `config/token.json` 的 `trae` 节点添加账号（`token.json` 已在 .gitignore，不会提交）：

```json
{
  "trae": {
    "accounts": [
      {
        "account_name": "主号",
        "session": "粘贴 X-Cloudide-Session 的完整值"
      }
    ]
  }
}
```

> 只有 `session` 是必需的，`account_name` 用于通知里认出账号。签到设备 ID 按账号名自动生成，无需填写。`user_id`/`access_token`/`expires_at`/`device_id` 均为可选增强字段（导入去重、桌面令牌回退），没有也不影响网页会话签到。一个账号一条 `session`，互不影响；会话约 14 天有效，过期后日志会提示"请更新 session"，回浏览器重新复制即可。

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

- **日志提示"请更新 session"**：session 过期（约 14 天），浏览器重新复制一次即可
- **日志提示"缺少签到设备 device_id"**：该账号走的是桌面令牌模式但没有可用设备，给它配 `session` 走网页模式即可
- **结果推送**：复用项目统一推送（`config/notification.json` 配置）

---

**免责声明**：本脚本仅供学习交流使用，使用产生的一切后果由使用者自行承担。
