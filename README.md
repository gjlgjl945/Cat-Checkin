# Cat-Checkin 🐱

四个平台的每日自动签到，**GitHub Actions 友好**：无交互式输入、配置全部来自 Secrets / 环境变量、
按平台并行执行、单平台超时与重试可控、退出码与任务状态一一对应。

## ✅ 平台清单

| 平台 | 入口脚本 | 超时 | 说明 |
|---|---|---|---|
| 🔐 看雪论坛 | `script/kanxue/sign_in.py` | 300s | 每日签到，纯 Cookie |
| 📝 WPS Office | `script/wps/main.py` | 1500s | 任务中心 + 天天领福利双页面 |
| 💰 什么值得买 | `script/smzdm/sign_daily_task/main.py` | 1500s | 每日签到 + 众测/互动任务 |
| 🐅 Trae CN | `script/trae/main.py` | 900s | 积分模式每日签到，支持多账号 |

> 相对上游 ZaiZaiCat-Checkin，本仓库已裁剪为上述四个平台；`SYNC_REPORT.md` 记录了同步与裁剪的来龙去脉。

> **⚠️ 免责声明**
> 本项目中的大量代码由 AI 辅助编写生成，代码规范和格式可能存在不足之处，敬请见谅。
> 本项目仅供学习交流使用，请勿用于商业用途。使用本项目所造成的一切后果由使用者自行承担。

## 🚀 快速开始（GitHub Actions 部署）

### 1. Fork 仓库
点击右上角 **Fork**，把仓库 fork 到自己的 GitHub 账户下。

### 2. 准备配置（一个平台一份文件）

**每个平台一个文件，互不影响。** 文件名固定由平台 key 推导：

| 平台 | 文件名 | Secret |
|---|---|---|
| 看雪论坛 | `config/token.kanxue.json` | `TOKEN_KANXUE_JSON` |
| WPS Office | `config/token.wps.json` | `TOKEN_WPS_JSON` |
| 什么值得买 | `config/token.smzdm.json` | `TOKEN_SMZDM_JSON` |
| Trae CN | `config/token.trae.json` | `TOKEN_TRAE_JSON` |

文件内容就是旧 `token.json` 里对应的那一个顶层节点，字段与结构完全不变。例如 `config/token.wps.json`：

```json
{ "wps": { "accounts": [ { "account_name": "主号", "user_id": 123, "cookies": "..." } ] } }
```

文件名本身已表明平台，因此也接受省略外层节点的写法：`{ "accounts": [ ... ] }`，两种都行。

字段全量参考见 [`config/template_token.json`](config/template_token.json)（它只是文档，不参与运行）。

**从旧的单文件迁移**（`config/token.json` 里四个平台都在一份里）：

```bash
python ci/migrate_config.py            # 先预览：会生成哪几份、各有多少账号
python ci/migrate_config.py --apply    # 实际拆分
# 确认新文件可用后，可加 --remove-legacy 顺带删掉旧文件
```

迁移是**保结构的整节点搬运**：`token.json` 的 `wps` 节点原样搬进 `token.wps.json`，字段一个不改。
旧的 `token.json` 会保留，但**只要对应平台文件存在就不会再读它**；如果某个平台没有独立文件，
才会回退到旧文件并在日志里提示。

拆分完做一次结构自检（比在 CI 上试错快得多）：

```bash
python ci/platform_guard.py --validate
```

输出会列出每个平台的文件、账号数与「已配置 / 未配置 / 结构错误」，不打印任何凭据内容。

然后按平台编码为 Secret（也支持直接粘贴 JSON 原文，工作流会自动识别）：

- macOS / Linux：`base64 -w0 config/token.wps.json`
- Windows PowerShell：
  ```powershell
  [Convert]::ToBase64String([System.IO.File]::ReadAllBytes("config/token.wps.json"))
  ```

各平台字段的获取方法见下方 [🔑 账号信息获取教程](#-账号信息获取教程)。

### 3. 配置 GitHub Secrets
进入你 fork 的仓库页面：**Settings → Secrets and variables → Actions → New repository secret**。

| Secret 名称 | 必填 | 内容 |
|---|---|---|
| `TOKEN_KANXUE_JSON` | 按需 | `config/token.kanxue.json` 的 base64 或 JSON 原文 |
| `TOKEN_WPS_JSON` | 按需 | `config/token.wps.json` 的 base64 或 JSON 原文 |
| `TOKEN_SMZDM_JSON` | 按需 | `config/token.smzdm.json` 的 base64 或 JSON 原文 |
| `TOKEN_TRAE_JSON` | 按需 | `config/token.trae.json` 的 base64 或 JSON 原文 |
| `TOKEN_JSON` | 兼容 | 旧用法：一份含多平台的 JSON，动作会自动按平台拆开 |
| `NOTIFICATION_JSON` | 否 | `config/notification.json` 的 base64 或 JSON 原文；不推送可跳过 |

至少要配一个平台，否则工作流会在校验阶段报「没有任何平台配置了有效账号」。

**某个平台的账号过期时，只替换它自己的那个 Secret 即可**，其它平台完全不受影响；
同名平台如果同时存在独立 Secret 和 `TOKEN_JSON`，以独立 Secret 为准。

推送也可改用环境变量注入（与 `NOTIFICATION_JSON` 二选一，工作流已把常用通道映射进来）：
`BARK_PUSH`、`BARK_ICON`、`BARK_SOUND`、`BARK_GROUP`、`BARK_LEVEL`、`BARK_URL`、`SCKEY`、`SENDKEY`、
`PUSHPLUS_TOKEN`、`PUSHPLUS_TOPIC`、`TG_BOT_TOKEN`、`TG_USER_ID`、`TG_API_HOST`、`FSKEY`、
`DINGTALK_ACCESS_TOKEN`、`DINGTALK_SECRET`、`QYWX_KEY`、`QYWX_ORIGIN`、`GOTIFY_URL`、`GOTIFY_TOKEN`、
`NTFY_URL`、`NTFY_TOPIC`、`PUSHDEER_PUSHKEY`。
其余通道（CoolPush、Qmsg、企业微信应用等）请用 `NOTIFICATION_JSON`，字段见
[`config/template_notification.json`](config/template_notification.json)。

### 4. 启用 Workflow
进入 **Actions** 标签页，点击 **"I understand my workflows, go ahead and enable them"** 启用工作流。

- 定时触发：北京时间每天 08:12 与 14:12 各一次
- 手动触发：**Actions → 多平台每日签到 → Run workflow**，支持两个输入
  - `platforms`：只跑指定平台，key 用英文逗号分隔，例如 `kanxue,wps`
  - `dry_run`：只校验配置与依赖，不执行签到

### 5. 执行模型与可调参数

- `prepare` 任务逐个平台校验各自的配置文件：**没有任何平台可用**时才整体失败；
  单个平台的文件损坏只会在日志里点名，不影响其它平台——那一个 job 变红，其余照跑
- `prepare` 还会做一次**矩阵一致性校验**（`--check-matrix`）：平台注册表与 workflow 静态矩阵必须逐行相同，
  否则「加了平台却忘记加矩阵」会静默不执行。漂移时按提示跑 `python ci/platform_guard.py --sync-matrix` 修复
- `checkin` 使用**静态矩阵**（平台清单写在 workflow 里）。每个 job 在装依赖之前先跑 `ci/platform_guard.py` 自查：
  只看**自己那份**配置文件——文件缺失或账号数为 0 就跳过，文件存在但内容不对就报错（该 job 变红，其它平台不受影响）
- 之所以不用动态矩阵：`prepare` 加载了 `TOKEN_JSON`，GitHub 会在作业结束时丢弃「疑似包含 Secret」的作业输出，下游 `fromJSON` 只能拿到空串并报 `empty input`；静态矩阵彻底绕开这个耦合
- **退出码即事实**：四个平台脚本在「存在失败账号」时返回 1（job 变红），全部成功或今日已签才返回 0；
  本地调试若不想让失败显红，加 `--allow-failures`
- 单平台超时由矩阵控制（300–1500 秒），外层 job 上限 40 分钟
- 重试默认关闭（签到/答题接口普遍非幂等，盲目重试会造成重复提交）。需要时在
  **Settings → Secrets and variables → Actions → Variables** 添加：
  - `CHECKIN_RETRY_MAX`：最大尝试次数，默认 `1`
  - `CHECKIN_RETRY_DELAY_SECONDS`：重试等待基数，默认 `15`
- Trae 脚本在 CI 环境下自动关闭启动抖动；工作流里另有 `TRAE_JITTER_MAX: "0"` 显式固定，需要错峰改为 `600` 即可

### 6. 查看执行结果
- **Actions** 标签页按平台展示 job 状态，点进去可看完整日志
- 每次 job 会写一张摘要表到运行详情页（平台、入口、是否已配置、账号数、超时、状态）
- 失败时上传 `logs-<平台key>` 工件（`**/*.log`，保留 7 天）。
  出于安全考虑，**`config/` 目录不作为工件上传**——其中含可直接复用的登录凭据

## 🔑 账号信息获取教程

### 获取难度一览

| 平台 | 能否用浏览器直接获取 | 需要工具 |
|---|---|---|
| 🔐 看雪论坛 | ✅ 完全可以 | 仅浏览器 F12 |
| 📝 WPS Office | ✅ 完全可以 | 仅浏览器 F12 |
| 💰 什么值得买 | ✅ 签到部分可以（众测/互动任务需抓包补 `setting`） | 浏览器 F12 为主，抓包可选 |
| 🐅 Trae CN | ✅ 完全可以 | 仅浏览器 F12 |

> 💡 总结：**四个平台都能用浏览器搞定**。什么值得买只有众测/互动任务需要 APP 抓包补 `setting`，
> 只做每日签到时留空即可。

### 使用 EditThisCookie 导出 Cookie（免 F12，推荐）

EditThisCookie 是浏览器 Cookie 管理扩展，登录网站后点一下就能导出全部 Cookie，不需要打开开发者工具，也不会触发任何反调试机制。

**第 1 步：安装**

Edge / Chrome 应用商店搜索 `EditThisCookie` 安装（Chrome 商店地址：https://chromewebstore.google.com/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg ）。安装后工具栏会出现一个饼干图标。

**第 2 步：设置导出格式（一次性）**

1. 点击工具栏饼干图标 → 右下角齿轮（设置/Options）
2. 找到「选择 cookies 的导出格式」，选 **`Semicolon separated name=value pairs`**
3. 保存

**第 3 步：导出 Cookie**

1. 浏览器登录目标网站（如 https://www.smzdm.com ）
2. 点击工具栏的 EditThisCookie 饼干图标
3. 点右上角 **导出（Export）** 按钮 —— 剪贴板里直接就是一行分号分隔的字符串：

```
__ckguid=xxxxx; device_id=xxxxx; smzdm_id=123456; user=user123; ...
```

把这行完整复制，填进配置文件的 `"cookie"` 字段即可，无需任何转换。

---

### 🔐 看雪论坛

需要字段：`cookie`、`csrf_token`、`user_agent`

纯网页操作，浏览器就能搞定，无需抓包工具。`cookie` 和 `user_agent` 可以用 EditThisCookie 导出；`csrf_token` 需按下面第 4 步获取。

**获取步骤：**

1. Chrome/Edge 打开 https://bbs.kanxue.com 并登录
2. 按 `F12` 打开开发者工具，切到 **Network（网络）** 标签
3. 在论坛里随便点一个页面（比如刷新首页），让 Network 里出现新请求
4. 点击任意一条发往 `bbs.kanxue.com` 的请求 → 右侧 **Headers** 面板：
   - **Request Headers** 下的 `Cookie:`，冒号后面的整串复制 → 这就是 `cookie`
   - 同样在 Request Headers 里找 `User-Agent:`，整串复制 → 这就是 `user_agent`
5. 获取 `csrf_token`：
   - 在论坛页面按 `Ctrl+U` 查看网页源代码，`Ctrl+F` 搜索 `csrf_token`
   - 找到形如 `<meta name="csrf-token" content="xxxxxx">` 的地方，复制 content 的值
   - 也可以手动签到一次，在 Network 里找到 `user-signin.htm` 这条 POST 请求，其表单数据（Form Data）里的 `csrf_token` 字段值就是它

**填写示例：**

```json
{
  "kanxue": {
    "accounts": [
      {
        "account_name": "我的看雪",
        "cookie": "xxx_session=abcdef123456; xxx_uid=88888; xxx_token=fedcba654321",
        "csrf_token": "0.a1b2c3d4e5f6g7h8.9i0j1k2l3m4n5o6p",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      }
    ]
  }
}
```

> `csrf_token` 与 Cookie 同源失效：Cookie 过期后两个都要重新取。

---

### 📝 WPS Office

需要字段：`user_id`（数字）、`cookies`、`user_agent`

纯网页操作，浏览器就能搞定。`cookies` 和 `user_agent` 可以用 [EditThisCookie](#使用-editthiscookie-导出-cookie免-f12推荐) 直接导出（在 www.wps.cn 页面上导出即可，`uid=` 字段会一并包含）。

**获取步骤：**

1. Chrome/Edge 打开 WPS 官网 https://www.wps.cn 并登录（或直接访问会员活动页 https://personal-act.wps.cn ）
2. 按 `F12` → **Network** 标签 → 刷新页面
3. 找到发往 `personal-act.wps.cn` 或 `personal-bus.wps.cn` 的任意请求 → **Headers**：
   - **Request Headers** 里的 `Cookie:` 整串复制 → 这就是 `cookies`（确保包含 `act_csrf_token` 字段；如果没有，先在活动页随便点一下再抓）
   - 同处复制 `User-Agent:` → 这就是 `user_agent`
4. 获取 `user_id`（数字）：
   - 方法 A：在 Cookie 字符串里搜索 `uid=`，等号后面的数字就是 user_id
   - 方法 B：Network 里点开任意一条返回 JSON 的请求 → **Preview/Response** 标签，找 `userid`、`user_id` 或 `data.userid` 字段
   - 注意 JSON 里它是数字类型，配置文件里**不要加引号**

**填写示例：**

```json
{
  "wps": {
    "accounts": [
      {
        "account_name": "我的WPS",
        "user_id": 123456789,
        "cookies": "wps_uid=123456789; act_csrf_token=abc123; wps_sid=xyz789; ...",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      }
    ]
  }
}
```

---

### 💰 什么值得买

需要字段：`name`（自定义账号名）、`cookie`、`user_agent`、`setting`

**方法 A：浏览器获取（推荐先试，无需抓包）**

社区多个独立签到项目（Sitoi/dailycheckin 等）验证过：网页 Cookie 可以直接用于签到接口。

> ⚠️ 什么值得买有 F12 反调试（打开开发者工具会不停弹出 `debugger` 断点），推荐用 EditThisCookie 扩展导出，绕开 F12。

1. Chrome/Edge 打开 https://www.smzdm.com 并登录
2. 按 [使用 EditThisCookie 导出 Cookie](#使用-editthiscookie-导出-cookie免-f12推荐) 的四步操作，得到 `cookie` 字符串和 `user_agent`
3. `setting` 填空字符串 `""`

> ⚠️ 网页 Cookie 的适用范围：**每日签到大概率可用**；但本脚本的众测/互动任务走的是 APP 接口，网页 Cookie 可能失败。如果运行后只有众测任务报错、签到正常，说明网页 Cookie 够用；如果连签到都失败，改用方法 B。

**方法 B：APP 抓包（全功能）**

1. 手机与电脑连同一 Wi-Fi，用 Fiddler 等工具代理手机流量并安装证书
2. Fiddler 过滤栏输入 `smzdm`
3. 手机打开什么值得买 APP 并登录
4. 在 APP 里进入「签到」页面或刷新「我的」页面，Fiddler 会捕获到发往 `*.smzdm.com` 的请求
5. 点击一条 POST 请求（如 `/checkin` 或 `/user/info`）：
   - **Request Headers** 里的 `Cookie:` 整串复制 → `cookie`
   - **Request Headers** 里的 `User-Agent:` 整串复制 → `user_agent`（APP 的 UA 通常长这样：`smzdm 11.1.35 rv:167 (iPhone ...)`，保留原样）
   - **请求体（Form Data / JSON）** 里名为 `setting` 的参数，值是一长串加密字符串 → `setting`

> 💡 `setting` 不是每个接口都带。找不到时筛选 POST 请求逐条查看 Form Data；众测/互动类接口（`zhongce`、`interactive` 相关）几乎都携带它。

**填写示例：**

```json
{
  "smzdm": {
    "accounts": [
      {
        "name": "我的smzdm",
        "cookie": "device_smzdm=xxx; smzdm_id=123456; user=user123; sess=abcdef...",
        "user_agent": "smzdm 11.1.35 rv:167 (iPhone 6s; iOS 15.8.3; zh_CN)/iphone_smzdmapp/11.1.35",
        "setting": "{\"browser_info\":\"...\",\"env\":\"APP\"...}"
      }
    ]
  }
}
```

---

### 🐅 Trae CN

需要字段：`account_name` + 下面三种凭证之一，**推荐 `sessionid`**。

| 凭证 | 字段 | 有效期 | 适用 |
|---|---|---|---|
| 长效登录 Cookie | `sessionid` | 约 60 天，每次运行自动续期 | 推荐，多账号无设备限制 |
| 网页会话 | `session`（X-Cloudide-Session） | 约 14 天，需手工更新 | 有现成会话时可用 |
| 桌面令牌 | `access_token` + `expires_at` + `device_id` | 取决于客户端 | 受设备绑定限制，单账号尚可 |

**获取 `sessionid`（推荐）：**

1. 浏览器打开 https://www.trae.cn 并登录目标账号
2. 按 `F12` → **应用（Application）** → **Cookie** → `https://www.trae.cn`
3. 找到 `sessionid` 一行，复制其 Value（可能很长，含 `%2F` 等无需转义）

**填写示例：**

```json
{
  "trae": {
    "accounts": [
      { "account_name": "Trae-主号", "sessionid": "粘贴 sessionid 的值" }
    ]
  }
}
```

**行为说明：**

- 每次运行先用 `sessionid` 调 `/cloudide/api/v3/trae/Login` 续期，再换 JWT 签到；只用这一个 Cookie 即可
- 网页会话模式使用随机设备，不受「一机一设备」限制；桌面令牌模式必须用该账号自己注册的 `device_id`
- 领取请求体带 `req_source=2`（与官方客户端一致），设备头只发小写 `x-device-id` 一个
- 领取返回 `9074`（容量门/风控）或 `9095`（设备当日被占用）时，等待 20s±25% 抖动后换新设备重试，默认 2 次；
  可用 `TRAE_9074_RETRY`、`TRAE_9074_BACKOFF`（秒，0 表示不等待）调整。连发重试会延长服务端惩罚窗口，不建议调大
- 重复配置（不同 `sessionid` 指向同一 UserID）会报「重复」而不是误报「今日已签到」
- CI 环境自动跳过本机客户端扫描、关闭启动抖动；本地运行仍保留 0–600 秒随机抖动
- 定时任务排在 08:12 / 14:12（北京时间），避开 00:00–00:10 这个签到最拥挤的时段

**命令行：**

```bash
python script/trae/main.py                 # 正常签到
python script/trae/main.py --dry-run       # 只查状态，不领取积分
python script/trae/main.py --config path   # 指定配置文件
python script/trae/main.py --allow-failures  # 有账号失败时仍返回 0（默认返回 1）
```

**退出码：** 0 = 全部成功或今日已签；1 = 存在失败账号，或配置/运行异常。

---

### ⚠️ 安全提醒

- `cookie` / `sessionid` / `setting` 等字段等同于你的登录凭证，**不要截图发到群里、不要提交到公开仓库**
- 本项目只通过 GitHub Secrets 注入这些信息，Secrets 对他人不可见
- `config/token.<平台>.json` 与旧的 `config/token.json` 都已被 `.gitignore` 排除；模板文件 `config/template_token.json` 是公开的，只放占位文字
- 各平台 Cookie 都有有效期（几天到几个月不等），失效后脚本会报登录态错误，重新按上面步骤取一次并更新 Secret 即可

## 🔧 本地运行（可选）

需要 Python 3.11+，无 Node.js 依赖。

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 准备配置：一个平台一份文件（字段参考 config/template_token.json 对应节点）
#    例如只要跑看雪，就只写 config/token.kanxue.json：
#    { "kanxue": { "accounts": [ { "account_name": "...", "cookie": "...", "csrf_token": "..." } ] } }
#    如果手上还是旧的单文件 config/token.json，先拆分：
python ci/migrate_config.py --apply
# 然后做一次结构自检
python ci/platform_guard.py --validate

# 3. 运行（任选平台；脚本默认按仓库根目录定位配置，可在任意 cwd 下执行）
python script/kanxue/sign_in.py
python script/wps/main.py
python script/smzdm/sign_daily_task/main.py
python script/trae/main.py --dry-run

# 验证时可指向临时配置，避免动到真实凭据
python script/kanxue/sign_in.py --config /tmp/token.test.json

# 4. 本地模拟 CI 的入口包装（超时 + 重试 + 退出码）
ENTRY_TIMEOUT_SECONDS=300 RETRY_MAX=1 bash ci/run_entry.sh script/kanxue/sign_in.py
```

四个平台脚本的参数一致：

| 参数 | 作用 |
|---|---|
| `--config PATH` | 指定配置文件；默认读本平台自己的 `config/token.<key>.json` |
| `--allow-failures` | 有失败账号时仍返回 0（默认返回 1，便于 CI 报红） |
| `--dry-run` | 只查状态不领取（仅 Trae 支持；其余平台接口无独立的状态查询） |

## 📁 项目结构

```
Cat-Checkin/
├── .github/
│   ├── workflows/checkin.yml        # 定时 + 手动触发，按平台矩阵执行
│   └── actions/prepare-config/      # 复用动作：从 Secrets 还原并校验配置
├── ci/
│   ├── platform_guard.py            # 平台守卫：配置校验 / 平台筛选 / 矩阵一致性校验
│   ├── migrate_config.py            # 把旧的单文件配置拆成按平台独立的文件
│   └── run_entry.sh                 # 统一入口包装：超时、重试、退出码
├── config/
│   ├── template_notification.json   # 推送配置模板（含全部字段说明）
│   ├── template_token.json          # 账号字段模板（四个平台，仅作参考）
│   ├── token.kanxue.json            # ⚠️ 看雪账号，已被 .gitignore 排除
│   ├── token.wps.json               # ⚠️ WPS 账号
│   ├── token.smzdm.json             # ⚠️ 什么值得买账号
│   ├── token.trae.json              # ⚠️ Trae 账号
│   └── token.json                   # 旧的单文件配置（拆分后不再读取）
├── script/
│   ├── kanxue/                      # 看雪论坛
│   ├── wps/                         # WPS Office（任务中心 + 天天领福利）
│   ├── smzdm/                       # 什么值得买
│   └── trae/                        # Trae CN（含本机账号导入工具）
├── platform_config.py               # 配置定位与解包：文件名规则 / 旧文件回退 / 结构校验
├── notification.py                  # 推送模块（文件 > 环境变量 > 默认值）
├── requirements.txt
└── README.md
```

## ❓ 常见问题

**Q：怎么知道字段值是否抓对了？**
A：先在本地跑 `python script/<平台>/main.py`，看是否能完成签到并触发推送。能在本地跑通，到 GitHub Actions 通常也能跑通。

**Q：GitHub Actions 跑失败但本地正常？**
A：通常是因为 Secret 中的 base64 编码复制时不完整（少/多了换行）。重新在本地生成一次确认长度不为 0；也可以直接粘贴 JSON 原文，不必 base64。

**Q：怎么修改执行时间？**
A：编辑 `.github/workflows/checkin.yml` 中的 `cron` 表达式。GitHub Actions 使用 UTC 时区；北京时间 = UTC + 8。例如北京时间 20:00 = UTC 12:00 → `cron: "0 12 * * *"`。

**Q：为什么不在仓库里直接放 token.json？**
A：会把包含 Cookie / 账号敏感信息的文件提交到公开仓库，会有泄露风险。工作流在执行时通过 Secret 解码生成该文件，运行结束后随 Runner 一起销毁。

**Q：我只配置了 2 个平台，其余平台的 job 会报错吗？**
A：不会。矩阵是固定清单，但每个 job 先跑 `ci/platform_guard.py` 自查，账号数为 0 就跳过（跳过的 job 只花十几秒，不装依赖）；判断逻辑会把仍是模板占位值的字段视为未配置。

**Q：某个平台 job 显示 124 / 超时怎么办？**
A：124 来自 `timeout` 命令，表示该平台超过矩阵里的 `timeout` 秒。调大对应平台超时，或排查脚本是否卡在网络重试。

**Q：某个平台的账号过期了，只想换这一个平台怎么办？**
A：只替换它自己的文件（本地 `config/token.<key>.json`）或 Secret（`TOKEN_<KEY>_JSON`）即可，
其它平台的文件与 Secret 完全不用动，下一次运行也只会用新的那份。

**Q：拆成四份之后，某个平台的文件删了会不会影响别人？**
A：不会。每个脚本只读自己那份，缺失就是「这个平台未配置」，对应 job 跳过，其余照常跑。
唯一的例外：如果旧的 `config/token.json` 还在，被删掉的那个平台会**回退到旧文件**（日志和校验表都会标
「旧 token.json」）。确实想停用某平台，请连旧文件一起删掉，或干脆不配它的 Secret。

**Q：平台文件写错了（比如把看雪的配置复制成 wps）会怎样？**
A：校验阶段会报「配置里没有 wps 节点（现有节点：kanxue）」，并且**只有这个平台的 job 失败**，
其它平台照常签到。这正是拆分的意义：错误被限制在一份文件里。

**Q：某个账号失败会不会把整个 job 弄红？**
A：会，而且这是刻意的。四个平台脚本都以「是否存在失败账号」决定退出码：全部成功或今日已签返回 0，任一账号失败返回 1。
这样 Actions 上的绿色才代表「真的都签到了」。只想收到通知、不想报红时，本地加 `--allow-failures`。

**Q：没有任何账号被执行时为什么也算失败？**
A：退出码 1。因为「跑了但什么都没做」和「跑成功了」是两件事，前者需要你检查配置（字段没填、占位值没换、region 过滤后为空等）。
如果确实只想跑空转验证，用 `--allow-failures`。

**Q：怎么做一次不发推送的演练？**
A：设置环境变量 `NOTIFICATION_DISABLED=1`，所有推送通道都会被跳过，日志里会明确写「未配置可用的推送通道 / 已跳过」。
平时日志里若出现「推送通知已发送: Bark」这样的行，说明确实有通道返回了成功；没有通道时不会再假装发送成功。

**Q：新增一个平台要改哪些地方？**
A：两处必须一起改（漏改会被 CI 拦下）：① `ci/platform_guard.py` 的 `PLATFORMS` 加一行；
② 执行 `python ci/platform_guard.py --sync-matrix` 把注册表同步到工作流矩阵。
`prepare` 作业里的 `--check-matrix` 会在起 job 之前校验这两处一致，漂移时直接失败并打印差异行。

**Q：失败工件里为什么没有 config/？**
A：旧版本会把 `config/` 一并上传，等于把可直接复用的登录凭据写进工件。现在只上传 `**/*.log`；需要排查配置问题时，请在本地用 `python ci/platform_guard.py --validate` 复现。

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。
