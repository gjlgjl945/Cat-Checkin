# ZaiZaiCat-Checkin 🐱

每日多平台自动签到脚本，已改造为 GitHub Actions 友好版本。

仅保留以下 5 个签到任务：

| 平台           | 入口脚本                              | 说明                  |
|--------------|-----------------------------------|---------------------|
| 🚚 顺丰速运      | `script/sf/main.py`               | 签到 + 积分任务         |
| 🔐 看雪论坛      | `script/kanxue/sign_in.py`        | 每日签到                |
| 👟 鸿星尔克      | `script/erke/main.py`             | 签到 + 积分明细查询        |
| 📝 WPS Office  | `script/wps/main.py`              | 任务中心 + 天天领福利       |
| 💰 什么值得买     | `script/smzdm/sign_daily_task/main.py` | 每日签到 + 众测/互动任务     |

> **⚠️ 免责声明**
> 本项目中的大量代码由 AI 辅助编写生成，代码规范和格式可能存在不足之处，敬请见谅。
> 本项目仅供学习交流使用，请勿用于商业用途。使用本项目所造成的一切后果由使用者自行承担。

## 🚀 快速开始（GitHub Actions 部署）

### 1. Fork 仓库
点击右上角 **Fork**，把仓库 fork 到自己的 GitHub 账户下。

### 2. 准备 `config/token.json`

每个平台的字段含义见 [`config/token.json.example`](config/token.json.example)。下面是填写模板：

```json
{
  "sf":     { "accounts": [{ "account_name": "...", "sign": "...", "channel": "weixin", "device_id": "...", "user_agent": "..." }] },
  "kanxue": { "accounts": [{ "account_name": "...", "cookie": "...", "csrf_token": "...", "user_agent": "..." }] },
  "erke":   { "accounts": [{ "account_name": "...", "member_id": "...", "enterprise_id": "...", "unionid": "...", "openid": "...", "wx_openid": "...", "user_agent": "..." }] },
  "wps":    { "accounts": [{ "account_name": "...", "user_id": 123, "cookies": "...", "user_agent": "..." }] },
  "smzdm":  { "accounts": [{ "name": "...", "cookie": "...", "user_agent": "...", "setting": "..." }] }
}
```

> **字段获取方式**
> - 顺丰：`sign` 在顺丰速运 APP/小程序请求 `shareLogin` 接口时的请求参数中可拿到。
> - 看雪：登录后浏览器 DevTools → Network 任选一个请求，复制完整 Cookie 和页面里的 `csrf_token`。
> - 鸿星尔克：登录小程序后抓包获取 `member_id / enterprise_id / unionid / openid / wx_openid`。
> - WPS：登录 WPS 官网或客户端后抓取完整 Cookie（注意 user_id 字段是数字）。
> - 什么值得买：抓包获取 `cookie` 和请求体中的加密 `setting` 字段。

填好之后，用 base64 编码整个 JSON 文件，方便作为 Secret 填入：

- macOS / Linux：`base64 -w0 config/token.json`
- Windows PowerShell：
  ```powershell
  [Convert]::ToBase64String([System.IO.File]::ReadAllBytes("config/token.json"))
  ```

把输出整段复制下来。

### 3. 配置 GitHub Secrets
进入你 fork 的仓库页面：**Settings → Secrets and variables → Actions → New repository secret**。

| Secret 名称       | 必填 | 内容                                                                  |
|------------------|------|---------------------------------------------------------------------|
| `TOKEN_JSON`     | 是   | 第 2 步生成的 base64 字符串                                                 |
| `NOTIFICATION_JSON` | 否   | 同上方式生成 `config/notification.json` 的 base64 编码；不需要推送通知就跳过            |

可选的推送通道（对应 `notification.json`）支持 Bark、Server 酱、PushPlus、Telegram、飞书、钉钉、企业微信、Gotify、Ntfy、PushDeer 等十余种，详见 [`config/template_notification.json`](config/template_notification.json)。

### 4. 启用 Workflow
进入 **Actions** 标签页，点击 **"I understand my workflows, go ahead and enable them"** 启用工作流。

- 定时触发：每天北京时间 08:00（UTC 00:00）自动执行
- 手动触发：**Actions → 多平台每日签到 → Run workflow**

### 5. 查看执行结果
- **Actions** 标签页里查看每次运行的日志
- 失败时，工作流会把 `config/` 目录和日志打包成 `checkin-logs` 工件，可在运行详情页底部下载

## 🔧 本地运行（可选）

需要 Python 3.11+ 与 Node.js 18+（顺丰脚本需要执行 JavaScript）。

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 准备配置
cp config/token.json.example config/token.json
# 用编辑器填好真实账号信息

# 3. 运行（可指定单个平台）
python script/sf/main.py
python script/kanxue/sign_in.py
python script/erke/main.py
python script/wps/main.py
python script/smzdm/sign_daily_task/main.py
```

## 📁 项目结构

```
ZaiZaiCat-Checkin/
├── .github/workflows/checkin.yml   # GitHub Actions 工作流
├── config/
│   ├── template_notification.json  # 推送配置模板（含全部字段说明）
│   ├── template_token.json         # 账号配置模板（与代码字段对齐）
│   ├── token.json.example          # 同上的副本，提交到仓库供用户参考
│   └── token.json                  # ⚠️ 真实配置，已被 .gitignore 排除
├── script/
│   ├── sf/main.py                  # 顺丰速运
│   ├── kanxue/sign_in.py           # 看雪论坛
│   ├── erke/main.py                # 鸿星尔克
│   ├── wps/main.py                 # WPS Office
│   └── smzdm/sign_daily_task/main.py  # 什么值得买
├── notification.py                 # 推送模块（Bark、Server 酱、PushPlus 等）
├── requirements.txt
└── README.md
```

## ❓ 常见问题

**Q：怎么知道字段值是否抓对了？**
A：先在本地跑 `python script/<平台>/main.py`，看是否能完成签到并触发推送。能在本地跑通，到 GitHub Actions 通常也能跑通。

**Q：GitHub Actions 跑失败但本地正常？**
A：通常是因为 Secret 中的 base64 编码复制时不完整（少/多了换行）。重新在本地生成一次确认长度不为 0。

**Q：怎么修改执行时间？**
A：编辑 `.github/workflows/checkin.yml` 中的 `cron` 表达式。GitHub Actions 使用 UTC 时区；北京时间 = UTC + 8。例如北京时间 20:00 = UTC 12:00 → `cron: "0 12 * * *"`。

**Q：为什么不在仓库里直接放 token.json？**
A：会把包含 Cookie / 账号敏感信息的文件提交到公开仓库，会有泄露风险。工作流在执行时通过 Secret 解码生成该文件，运行结束后随 Runner 一起销毁。

## 📄 开源协议
本项目采用 [MIT License](LICENSE) 开源协议。

---

**⭐ 如果这个项目对你有帮助，欢迎给个 Star！**