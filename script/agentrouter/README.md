# Agent Router 每日签到

[Agent Router](https://ps.air-outer.com/console)（备用域名，原域名 `agentrouter.org` 境内不通）
是基于 New API 的大模型 API 网关，每日签到送 $25 额度。

## 签到原理

站点**没有独立签到入口**，额度在**登录时**发放（官方 FAQ：「签到领 $25 额度」需要退出后
重新登录才会到账）。因此脚本每天完整重走一次 GitHub OAuth 登录，登录成功即签到成功。

```
站点 /api/oauth/state          取签名 state（同时下发 session cookie）
        ↓
GitHub /login/oauth/authorize  用 GitHub 登录态换 code
        ↓
站点 /api/oauth/github         带 code + state 登录 → 额度到账
```

GitHub OAuth App 注册的回调域名是 `agentrouter.org`（境内不可达），脚本只从其跳转地址中
提取 `code`，从不访问该域名，随后统一用配置中的 `base_url`（默认 `https://ps.air-outer.com`）
发起登录请求，等价于把回调域名替换成备用域名。

签到结果由登录响应给出：服务端在登录流程中完成签发，响应 `data.checked_in` 为 `true`
即「今日已签到」（前端据此弹出「签到成功，新增额度已到账」）。所以**没有、也不需要独立
签到接口**，重登即签到。

站点未开放账号密码登录（账号为 GitHub 注册、无独立密码），GitHub OAuth 是唯一登录路径。

## 配置

在 `config/token.json` 中新增 `agentrouter` 节点：

```json
{
  "agentrouter": {
    "accounts": [
      {
        "account_name": "erma0",
        "github_cookies": "user_session=xxx; __Host-user_session_same_site=xxx; logged_in=yes",
        "base_url": "https://ps.air-outer.com"
      }
    ]
  }
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `account_name` | 否 | 备注名，仅用于日志和通知展示 |
| `github_cookies` | 二选一 | github.com 的完整 Cookie 串（推荐）或 cookie 字典 |
| `github_session` | 二选一 | 仅 `user_session` 的值，脚本自动补齐 `logged_in` 等标记 |
| `user_id` | 否 | 站点用户 ID，用于 `new-api-user` 请求头；不填则签到照常，只是查不到余额 |
| `base_url` | 否 | 站点地址，默认 `https://ps.air-outer.com` |
| `proxy` | 否 | 访问 GitHub 用的代理，如 `http://127.0.0.1:7890`；留空沿用环境变量 |
| `verify` | 否 | TLS 校验，留空自动合并系统根证书；可填证书路径，或 `false` 跳过校验 |

> `user_id` 获取：登录后 F12 → 网络（Network）→ 任一 `/api/` 请求 → 请求头里的
> `new-api-user`。站点用它识别用户，缺失时接口会返回「未提供 New-Api-User」。
> 登录响应若带回用户 ID，脚本会自动补上，无需手动填。

### 获取 GitHub 登录态

登录态只用于换取 OAuth 授权码，本站不读取任何浏览器数据，需要手动复制一次：

1. 浏览器打开 <https://github.com> 并确保已登录
2. F12 打开开发者工具 → 应用程序（Application）→ Cookie → `https://github.com`
3. 找到 `user_session`，复制其值；更稳妥的做法是从网络（Network）面板任一 github.com
   请求的 `Cookie` 请求头里整串复制

`user_session` 有效期较长（通常一年），填一次即可长期自动运行；失效时日志会提示
「GitHub 登录态无效或已过期」，重新复制即可。

> 首次运行若该 GitHub 账号尚未授权过此应用，脚本会自动提交授权同意表单，无需手动点击。

## 运行

```bash
python script/agentrouter/main.py            # 执行签到
python script/agentrouter/main.py --dry-run   # 仅校验配置
```

定时任务建议每天一次，cron 示例：

```
20 9 * * * cd /path/to/ZaiZaiCat-Checkin && python script/agentrouter/main.py
```

## 常见问题

**证书验证失败（`unable to get local issuer certificate`）**

用了 Watt Toolkit / SteamTools 之类的 GitHub 加速器时，github.com 的流量走本地 TLS
中间人，根证书只装在 Windows 系统证书库、不在 Python 的 certifi 里。脚本已自动合并
`certifi + 系统 ROOT 证书` 生成 CA bundle，正常情况下无需处理；若仍报错，可把 `verify`
配成对应根证书的路径，或临时设为 `false`（不推荐）。

**提示 GitHub 登录态无效或已过期**

浏览器重新登录 github.com，按上文步骤重新复制 Cookie 到 `github_cookies`。

## 说明

- 站点把签到挂在登录流程里，登录成功即视为签到成功，脚本会同时输出账号当前余额
- 站点对非白名单路由统一返回「无权进行此操作，权限不足」，实测 `/api/user/sign_in`、
  `/checkin`、`/check_in`、`/daily_checkin` 等均不可用，即**只能通过重新登录领取额度**
- 签到结果按站点原版逻辑判断：登录响应 `data.checked_in` 为 `true` 时输出
  「签到成功，新增额度已到账」（与前端 toast 一致）
- `checked_in` 表示「**今日已签到**」状态（实测同一天重复登录它始终为 `true`，并非
  「本次新签到」）。额度实际每天只发放一次，站点日志里每天只新增一条
  「每日签到成功，增加额度 ＄25.000000 额度」记录，重复登录不会重复到账
- 多账号依次处理，账号之间间隔 5 秒
