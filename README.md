# Cat-Checkin 🐱

多平台每日自动签到，**GitHub Actions 友好**版本：无交互式输入、配置全部来自 Secrets / 环境变量、
按平台并行执行、单平台超时与重试可控、退出码与任务状态一一对应。

脚本主体同步自上游 ZaiZaiCat-Checkin，与上游的差异只保留「CI 适配」与「安全收口」两类，
逐文件差异与取舍理由见仓库根目录的 `SYNC_REPORT.md`。

## ✅ 平台清单

| 平台 | 入口脚本 | 定时任务 | 说明 |
|---|---|---|---|
| 🚚 顺丰速运 | `script/sf/main.py` | ✅ | 签到 + 积分任务（需 Node.js） |
| 🔐 看雪论坛 | `script/kanxue/sign_in.py` | ✅ | 每日签到 |
| 📱 恩山论坛 | `script/enshan/sign_in.py` | ✅ | 每日签到 |
| 📺 上海杨浦 | `script/shyp/main.py` | ✅ | 任务列表与积分任务 |
| 🏢 华润通-万象星 | `script/huaruntong/999/main.py` | ✅ | 答题签到 |
| 💳 华润通-微信版 | `script/huaruntong/huaruntong_wx/main.py` | ✅ | 签到送积分 |
| 🎯 华润通-文体未来荟 | `script/huaruntong/wentiweilaihui/main.py` | ✅ | 签到与积分查询 |
| 🛒 华润通-Ole' | `script/huaruntong/ole/main.py` | ❌ | 需动态获取微信 code 换 token，不适合无人值守 |
| 👟 鸿星尔克 | `script/erke/main.py` | ✅ | 签到 + 积分明细查询 |
| 📝 WPS Office | `script/wps/main.py` | ✅ | 任务中心 + 天天领福利 |
| 💰 什么值得买 | `script/smzdm/sign_daily_task/main.py` | ✅ | 每日签到 + 众测/互动任务 |
| 🌊 大潮 App | `script/dachao/main.py` | ✅ | 签到 + 阅读 + 抽奖（耗时较长） |
| 🤖 WorkBuddy | `script/workbuddy/main.py` | ✅ | 签到、令牌自动续期 |
| 🐅 Trae CN | `script/trae/main.py` | ✅ | 积分模式每日签到 |
| 🚀 Agent Router | `script/agentrouter/main.py` | ✅ | OAuth 登录即签到、余额查询 |

> **⚠️ 免责声明**
> 本项目中的大量代码由 AI 辅助编写生成，代码规范和格式可能存在不足之处，敬请见谅。
> 本项目仅供学习交流使用，请勿用于商业用途。使用本项目所造成的一切后果由使用者自行承担。

## 🚀 快速开始（GitHub Actions 部署）

### 1. Fork 仓库
点击右上角 **Fork**，把仓库 fork 到自己的 GitHub 账户下。

### 2. 准备 `config/token.json`

唯一权威模板是 [`config/template_token.json`](config/template_token.json)，已按平台节点列全字段与中文说明。
复制一份另存为 `config/token.json`，只保留你要跑的平台的账号（未配置的平台会被工作流自动跳过）。

先在本地做一次结构自检，比在 CI 上试错快得多：

```bash
python ci/platform_guard.py --config config/token.json --validate
```

输出会列出每个平台的账号数与「已配置 / 未配置」，并且不会打印任何凭据内容。

**只跑看雪 / WPS / 什么值得买**：可直接从
[`config/token.kanxue-wps-smzdm.json`](config/token.kanxue-wps-smzdm.json) 起步——三个节点已备好，
只需填凭据字段（留空表示未配置，工作流会跳过）。三个平台的字段获取方法见下方对应教程。

然后编码为 Secret（也支持直接粘贴 JSON 原文，工作流会自动识别）：

- macOS / Linux：`base64 -w0 config/token.json`
- Windows PowerShell：
  ```powershell
  [Convert]::ToBase64String([System.IO.File]::ReadAllBytes("config/token.json"))
  ```

各平台字段的获取方法见下方 [🔑 账号信息获取教程](#-账号信息获取教程)。

### 3. 配置 GitHub Secrets
进入你 fork 的仓库页面：**Settings → Secrets and variables → Actions → New repository secret**。

| Secret 名称 | 必填 | 内容 |
|---|---|---|
| `TOKEN_JSON` | 是 | `config/token.json` 的 base64 编码，或直接粘贴 JSON 原文 |
| `NOTIFICATION_JSON` | 否 | `config/notification.json` 的 base64 编码或 JSON 原文；不推送可跳过 |

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
  - `platforms`：只跑指定平台，key 用英文逗号分隔，例如 `sf,wps,trae`
  - `dry_run`：只校验配置与依赖，不执行签到

### 5. 执行模型与可调参数

- `prepare` 任务先校验 `config/token.json`，配置不合法立即失败，避免十几个平台 job 一起报错
- `checkin` 使用**静态矩阵**（平台清单写在 workflow 里）。每个 job 在装依赖之前先跑 `ci/platform_guard.py` 自查：账号数为 0、或不在 `platforms` 输入范围内的平台直接跳过，不会让工作流变红
- 之所以不用动态矩阵：`prepare` 加载了 `TOKEN_JSON`，GitHub 会在作业结束时丢弃「疑似包含 Secret」的作业输出，下游 `fromJSON` 只能拿到空串并报 `empty input`；静态矩阵彻底绕开这个耦合
- `checkin` 任务按平台拆成独立 job（`max-parallel: 4`，`fail-fast: false`），单平台失败不影响其他平台，红色只代表该平台本身失败
- 单平台超时由矩阵控制（`script/*` 对应的 `timeout` 字段，300–1800 秒），外层 job 上限 40 分钟
- 重试默认关闭（签到/答题接口普遍非幂等，盲目重试会造成重复提交）。需要时在
  **Settings → Secrets and variables → Actions → Variables** 添加：
  - `CHECKIN_RETRY_MAX`：最大尝试次数，默认 `1`
  - `CHECKIN_RETRY_DELAY_SECONDS`：重试等待基数，默认 `15`
- Trae / WorkBuddy 脚本自带的启动抖动在 CI 中固定为 `0`（见工作流 `env`），如需错峰改为 `600` 即可，无需改代码

### 6. 查看执行结果
- **Actions** 标签页按平台展示 job 状态，点进去可看完整日志
- 每次 job 会写一张摘要表到运行详情页（平台、入口、是否已配置、账号数、超时、状态）
- 失败时上传 `logs-<平台key>` 工件（`**/*.log`，保留 7 天）。
  出于安全考虑，**`config/` 目录不再作为工件上传**——其中含可直接复用的登录凭据

## 🔑 账号信息获取教程

### 获取难度一览

| 平台 | 能否用浏览器直接获取 | 需要工具 |
|---|---|---|
| 📝 WPS Office | ✅ 完全可以 | 仅浏览器 F12 |
| 🔐 看雪论坛 | ✅ 完全可以 | 仅浏览器 F12 |
| 💰 什么值得买 | ✅ 签到部分可以（众测/互动任务需抓包补 `setting`） | 浏览器 F12 为主，抓包可选 |
| 🚚 顺丰速运 | ⚠️ 一般需要抓包（用手机或 PC 微信都行） | Fiddler 等抓包工具 |
| 👟 鸿星尔克 | ❌ 必须抓包（`openid/unionid` 是微信小程序内部标识，网页版不存在） | Fiddler 等抓包工具 |

> 💡 总结：**WPS 和看雪纯浏览器搞定**；**什么值得买先试浏览器**（大概率签到能跑通，只损失众测/互动任务）；**顺丰和鸿星尔克绕不开抓包**。如果实在不想抓包，顺丰和鸿星尔克这两个平台可以不配，其余三个照常工作。

### 抓包工具准备

按平台不同，你需要以下几类工具之一：

| 工具 | 适用场景 | 获取方式 |
|---|---|---|
| 浏览器 DevTools | 网页端可登录的平台（看雪、WPS） | Chrome/Edge 按 `F12` 即可，无需安装 |
| EditThisCookie 扩展 | 网页端 Cookie 一键导出（看雪、WPS、什么值得买），**免 F12、免抓包** | Edge/Chrome 应用商店搜 `EditThisCookie` 安装 |
| Fiddler Classic | APP / 微信小程序抓包（顺丰、鸿星尔克） | https://www.telerik.com/fiddler/fiddler-classic 免费下载 |

> 💡 推荐优先用 **EditThisCookie**：网页端三个平台（看雪、WPS、什么值得买）都能用它直接导出 Cookie，完全绕开 F12——尤其是什么值得买有反调试机制（打开 F12 会不停弹出 `debugger` 断点），用扩展导出可以彻底避开。

**Fiddler 抓包 HTTPS 的前置设置**（只需做一次）：

1. 打开 Fiddler → **Tools → Options → HTTPS**
2. 勾选 `Capture HTTPS CONNECTs` 和 `Decrypt HTTPS traffic`
3. 弹出证书安装提示时全部点"是"
4. **Connections** 标签页确认端口为 `8888`，勾选 `Allow remote computers to connect`
5. 手机和电脑连同一个 Wi-Fi，手机 Wi-Fi 设置里把代理改为「手动」，服务器填电脑 IP（`ipconfig` 查看），端口 `8888`
6. 手机浏览器访问 `http://ipv4.fiddler:8888` 下载并安装 Fiddler 证书（安卓还需在系统设置中信任该证书）

> ⚠️ 抓包完成后请及时关闭手机代理设置，否则断开电脑后手机无法上网。

---

### 使用 EditThisCookie 导出 Cookie（免 F12，推荐）

EditThisCookie 是浏览器 Cookie 管理扩展，登录网站后点一下就能导出全部 Cookie，不需要打开开发者工具，也不会触发任何反调试机制。

**第 1 步：安装**

Edge / Chrome 应用商店搜索 `EditThisCookie` 安装（Chrome 商店地址：https://chromewebstore.google.com/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg ）。安装后工具栏会出现一个饼干图标。

**第 2 步：设置导出格式（一次性）**

社区维护版 EditThisCookie 支持多种导出格式。先把它改成脚本直接可用的格式：

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

**备选：旧版扩展没有格式选项时（导出的是 JSON 数组）**

如果你装的版本设置里没有导出格式选项，导出会是 JSON 数组，需要转换一次。存成 `cookies.json` 后任选：

方式一：Python（本项目本身就需要 Python）：

```powershell
python -c "import json; print('; '.join(f\"{c['name']}={c['value']}\" for c in json.load(open('cookies.json', encoding='utf-8'))))"
```

方式二：PowerShell：

```powershell
$c = Get-Content cookies.json -Raw | ConvertFrom-Json
($c | ForEach-Object { "$($_.name)=$($_.value)" }) -join "; "
```

两种方式都会输出一行分号分隔的字符串，填进配置文件的 `"cookie"` 字段即可。

**第 4 步：获取 user_agent**

EditThisCookie 不提供 UA。在目标网站页面按 `F12` → 控制台输入 `navigator.userAgent` 回车，复制输出的字符串。（这一步不会触发什么值得买的 debugger 反调试——它只在打开 Sources 面板时循环暂停，控制台输一条命令不受影响；如果还是被卡住，按 `Ctrl+F8` 禁用断点后 `F8` 恢复即可。）

**适用平台对照：**

| 平台 | EditThisCookie 能否替代 F12 | 备注 |
|---|---|---|
| 🔐 看雪论坛 | ✅ 可以 | 在 bbs.kanxue.com 页面导出；`csrf_token` 仍需从页面源码或请求载荷里取 |
| 📝 WPS Office | ✅ 可以 | 在 www.wps.cn 或 personal-act.wps.cn 页面导出 |
| 💰 什么值得买 | ✅ 可以（强烈推荐） | 该站有 F12 反调试，扩展导出最省心 |
| 🚚 顺丰 / 👟 鸿星尔克 | ❌ 不适用 | APP/小程序流量，浏览器扩展碰不到，仍需抓包 |

---

### 🚚 顺丰速运

需要字段：`sign`、`channel`、`device_id`、`user_agent`

脚本通过顺丰的分享登录接口换取会话：`GET https://mcs-mimp-web.sf-express.com/mcs-mimp/share/app/shareLogin?bizCode=622&source=SFAPP&sign=<你的sign>`。

> ⚠️ 顺丰没有开放的网页登录入口，`sign` 无法用浏览器直接获取，需要抓包。但抓包目标很明确（见下），且可以用 **PC 微信代替手机**，不用装手机端证书。

**获取步骤（方式一：PC 微信 + Fiddler，推荐）：**

1. 电脑上打开 Fiddler（本机抓包无需配代理和证书，只需完成上面 [HTTPS 解密设置](#抓包工具准备) 的第 1~3 步）
2. PC 微信里打开「顺丰速运」小程序并登录，进入「我的 → 积分」页
3. Fiddler 过滤栏输入 `sf-express`
4. 在小程序里点几下积分任务页面，找到以下任意一种请求（社区已确认的目标 URL）：
   - `/mcs-mimp/share/weChat/shareGiftReceiveRedirect`
   - `/mcs-mimp/share/app/shareRedirect`
   - 或任何 URL 参数里带 `sign=` 的请求
5. 从该请求的完整 URL 里复制 `sign=` 后面的参数值（可能是 URL 编码过的，原样复制即可，脚本会自动解码）
6. `device_id`：同域请求体/URL 参数里的 `deviceId`；找不到就自己编一个 32 位十六进制字符串（服务端一般不严格校验，这是判断）
7. `user_agent`：从请求头复制；`channel` 填 `"weixin"`

**获取步骤（方式二：手机 APP + Fiddler 代理）：**

1. 按 [抓包工具准备](#抓包工具准备) 配好手机代理
2. 手机顺丰 APP 登录后进入「我的 → 积分」，随便触发页面刷新
3. 其余同上，从捕获的 `sf-express.com` 请求中提取 `sign` / `deviceId` / `User-Agent`

**填写示例：**

```json
{
  "sf": {
    "accounts": [
      {
        "account_name": "我的顺丰",
        "sign": "a1B2c3D4%2Fe5F6g7H8%3D",
        "channel": "weixin",
        "device_id": "8f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c",
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.49"
      }
    ]
  }
}
```

---

### 🔐 看雪论坛

需要字段：`cookie`、`csrf_token`、`user_agent`

纯网页操作，浏览器就能搞定，无需抓包工具。`cookie` 和 `user_agent` 也可以用 [EditThisCookie](#使用-editthiscookie-导出-cookie免-f12推荐) 直接导出；但 `csrf_token` 仍需按下面第 5 步获取。

**获取步骤：**

1. Chrome/Edge 打开 https://bbs.kanxue.com 并登录
2. 按 `F12` 打开开发者工具，切到 **Network（网络）** 标签
3. 在论坛里随便点一个页面（比如刷新首页），让 Network 里出现新请求
4. 点击任意一条发往 `bbs.kanxue.com` 的请求 → 右侧 **Headers** 面板：
   - 找到 **Request Headers** 下的 `Cookie:`，把冒号后面的整串复制出来 → 这就是 `cookie`
   - 同样在 Request Headers 里找 `User-Agent:`，整串复制 → 这就是 `user_agent`
5. 获取 `csrf_token`：
   - 在看雪论坛页面按 `Ctrl+U` 查看网页源代码，`Ctrl+F` 搜索 `csrf_token`
   - 找到形如 `<meta name="csrf-token" content="xxxxxx">` 或 JS 变量赋值的地方，复制 content 的值
   - 也可以直接手动签到一次，在 Network 里找到 `user-signin.htm` 这条 POST 请求，其表单数据（Form Data）里的 `csrf_token` 字段值就是它

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

---

### 👟 鸿星尔克

需要字段：`member_id`、`enterprise_id`、`unionid`、`openid`、`wx_openid`、`user_agent`

脚本调用的是鸿星尔克微信小程序的后端接口（`https://hope.demogic.com/gic-wx-app`）。小程序 appid 和签名算法已内置在脚本里，无需填写。

> ⚠️ **为什么必须抓包**：需要的 `openid` / `unionid` 是微信体系内的用户标识，只存在于小程序发出的请求里，鸿星尔克没有网页版，浏览器拿不到。这是五个平台里唯一绕不开手机抓包的。

**获取步骤：**

1. 按 [抓包工具准备](#抓包工具准备) 配好 Fiddler + 手机代理
2. Fiddler 过滤栏输入 `demogic`
3. 手机微信里打开「鸿星尔克会员中心」小程序并登录
4. 在小程序里点进「积分」或「签到」页面，Fiddler 会捕获到发往 `hope.demogic.com/gic-wx-app` 的请求
5. 点击其中一条请求（如 `integral_record.json` 或 `member_sign.json`）→ **Inspectors → WebView/JSON** 标签：
   - 从 **URL 查询参数或请求体** 中分别复制：
     - `memberId` → 填入 `member_id`
     - `enterpriseId` → 填入 `enterprise_id`
     - `unionid` → 填入 `unionid`
     - `openid` → 填入 `openid`
     - `wxOpenid` → 填入 `wx_openid`
   - 从 **Request Headers** 复制 `User-Agent`

> 💡 如果某个字段找不到，多翻几条不同的请求——不同接口携带的参数组合略有差异，五个值都能在 demogic.com 域名的请求里凑齐。
>
> 💡 嫌五个字段麻烦的话（这是判断）：社区有项目显示仅凭 `memberId` 也能完成签到。可以先只填 `member_id`、其余留空字符串跑一次试试；签到成功就省事了，失败再补全五项。

**填写示例：**

```json
{
  "erke": {
    "accounts": [
      {
        "account_name": "我的鸿星尔克",
        "member_id": "1234567890",
        "enterprise_id": "9876543210",
        "unionid": "oX7yz5Kxxxxxxxxxxxxxxxxxxxxxxx",
        "openid": "oA1b2C3d4E5f6G7h8I9j0K1l2M3n4",
        "wx_openid": "oZ9y8X7w6V5u4T3s2R1q0P9o8N7m6",
        "user_agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.49"
      }
    ]
  }
}
```

---

### 📝 WPS Office

需要字段：`user_id`（数字）、`cookies`、`user_agent`

纯网页操作，浏览器就能搞定。`cookies` 和 `user_agent` 也可以用 [EditThisCookie](#使用-editthiscookie-导出-cookie免-f12推荐) 直接导出（在 www.wps.cn 页面上导出即可，`uid=` 字段会一并包含）。

**获取步骤：**

1. Chrome/Edge 打开 WPS 官网 https://www.wps.cn 并登录（或直接访问会员活动页 https://personal-act.wps.cn ）
2. 按 `F12` → **Network** 标签 → 刷新页面
3. 找到发往 `personal-act.wps.cn` 或 `personal-bus.wps.cn` 的任意请求 → **Headers**：
   - **Request Headers** 里的 `Cookie:` 整串复制 → 这就是 `cookies`（确保里面包含 `act_csrf_token` 字段；如果没有，先在活动页随便点一下再抓）
   - 同处复制 `User-Agent:` → 这就是 `user_agent`
4. 获取 `user_id`（数字）：
   - 方法 A：在 Cookie 字符串里搜索 `uid=`，等号后面的数字就是 user_id
   - 方法 B：Network 里点开任意一条返回 JSON 的请求 → **Preview/Response** 标签，找 `userid`、`user_id` 或 `data.userid` 字段
   - 注意 JSON 里它是数字类型，配置文件里不要加引号

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

1. 按 [抓包工具准备](#抓包工具准备) 配好 Fiddler + 手机代理
2. Fiddler 过滤栏输入 `smzdm`
3. 手机打开什么值得买 APP 并登录
4. 在 APP 里进入「签到」页面或刷新「我的」页面，Fiddler 会捕获到发往 `*.smzdm.com` 的请求
5. 点击一条 POST 请求（如 `/checkin` 或 `/user/info`）：
   - **Request Headers** 里的 `Cookie:` 整串复制 → 这就是 `cookie`
   - **Request Headers** 里的 `User-Agent:` 整串复制 → 这就是 `user_agent`（APP 的 UA 通常长这样：`smzdm 11.1.35 rv:167 (iPhone ...)`，保留原样即可）
   - **请求体（Form Data / JSON）** 里找名为 `setting` 的参数，值是一长串加密字符串 → 这就是 `setting`

> 💡 `setting` 不是每个接口都带。如果一时找不到，筛选 POST 请求逐条查看 Form Data；众测/互动类接口（`zhongce`、`interactive` 相关）几乎都携带它。

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

> 用方法 A 时只需把 `setting` 的值改为 `""`，其余字段填浏览器取到的内容。

---

### 🧩 其他平台（上游新增）

以下平台的字段差异较大，各自的取值与限制写在对应子目录的 README 里，避免本文档失焦：

| 平台 | 取值说明 | 备注 |
|---|---|---|
| 📱 恩山论坛 | `script/enshan`：`cookies` + `formhash` + `user_agent` | 纯浏览器 F12 即可 |
| 📺 上海杨浦 | `script/shyp`：`token` + `device_id` + `site_id` + `user_agent` | `token` 取自请求头 `Authorization` |
| 🏢 华润通系（4 个） | `config/template_token.json` 的 `huaruntong.*` 节点 | `ole` 需动态换 code，未纳入定时任务 |
| 🌊 大潮 App | `config/template_token.json` 的 `dachao` 节点：手机号 + 加密口令 + `session_id` + `user_agent` | 阅读任务耗时较长，单平台超时 1800 秒 |
| 🤖 WorkBuddy | [script/workbuddy/README.md](script/workbuddy/README.md) | 可先用 `import_accounts.py` 在本机导入，再贴进 Secret |
| 🐅 Trae CN | [script/trae/README.md](script/trae/README.md) | 推荐只配 `sessionid`（约 60 天有效） |
| 🚀 Agent Router | [script/agentrouter/README.md](script/agentrouter/README.md) | 配 GitHub `user_session` |

> `script/workbuddy/import_accounts.py`、`script/trae/import_accounts.py`、`script/trae/web_checkin.py`
> 是**本地工具**：依赖本机客户端目录或命令行参数，仅供本机导入/排障，不参与 CI，也不在定时任务里调用。

---

### ⚠️ 安全提醒

- `cookie` / `sign` / `setting` 等字段等同于你的登录凭证，**不要截图发到群里、不要提交到公开仓库**
- 本项目只通过 GitHub Secrets 注入这些信息，Secrets 对他人不可见
- 各平台 Cookie 都有有效期（几天到几个月不等），失效后脚本会报登录态错误，重新按上面步骤抓一次并更新 Secret 即可

## 🔧 本地运行（可选）

需要 Python 3.11+ 与 Node.js 20+（顺丰脚本需要执行 JavaScript；CI 固定使用 Node.js 24）。

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 准备配置（唯一模板是 config/template_token.json）
cp config/template_token.json config/token.json
# 用编辑器填好真实账号信息，并做一次结构自检
python ci/platform_guard.py --config config/token.json --validate

# 3. 运行（任选平台；脚本均按仓库根目录定位配置，可在任意 cwd 下执行）
python script/sf/main.py
python script/kanxue/sign_in.py
python script/erke/main.py
python script/wps/main.py
python script/smzdm/sign_daily_task/main.py

# 4. 本地模拟 CI 的入口包装（超时 + 重试 + 退出码）
ENTRY_TIMEOUT_SECONDS=300 RETRY_MAX=1 bash ci/run_entry.sh script/kanxue/sign_in.py
```

## 📁 项目结构

```
Cat-Checkin/
├── .github/
│   ├── workflows/checkin.yml        # 定时 + 手动触发，按平台矩阵执行
│   └── actions/prepare-config/      # 复用动作：从 Secrets 还原并校验配置
├── ci/
│   ├── platform_guard.py            # 平台守卫：配置校验 / 平台筛选 / 是否已配置
│   └── run_entry.sh                 # 统一入口包装：超时、重试、退出码
├── config/
│   ├── template_notification.json   # 推送配置模板（含全部字段说明）
│   ├── template_token.json          # 账号配置模板（15 个平台节点，唯一权威）
│   └── token.json                   # ⚠️ 真实配置，已被 .gitignore 排除
├── script/
│   ├── sf/                          # 顺丰速运（含 code.js，需 Node.js）
│   ├── kanxue/  enshan/  erke/      # 看雪 / 恩山 / 鸿星尔克
│   ├── wps/  smzdm/  shyp/          # WPS / 什么值得买 / 上海杨浦
│   ├── huaruntong/{999,huaruntong_wx,ole,wentiweilaihui}/
│   ├── dachao/                      # 大潮 App（含 captcha、http_debug）
│   ├── workbuddy/  trae/            # 含本地导入工具 import_accounts.py
│   └── agentrouter/
├── notification.py                  # 推送模块（文件 > 环境变量 > 默认值）
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

**Q：我只配置了 3 个平台，其余平台的 job 会报错吗？**
A：不会。矩阵是固定清单，但每个 job 先跑 `ci/platform_guard.py` 自查，账号数为 0 就跳过（跳过的 job 只花十几秒，不装依赖）；
判断逻辑在 `ci/platform_guard.py`，它会把仍是模板占位值的字段视为未配置。

**Q：新增平台 / 上游同步后，怎么把它接进 CI？**
A：在 `ci/platform_guard.py` 的 `PLATFORMS` 表里加一条（key、入口、配置路径、必填凭据字段、超时），
再在 `config/template_token.json` 补上对应节点即可，工作流本身不用改。

**Q：某个平台 job 显示 124 / 超时怎么办？**
A：124 来自 `timeout` 命令，表示该平台超过矩阵里的 `timeout` 秒。调大对应平台超时，
或排查脚本是否卡在网络重试；`dachao` 因含阅读等待默认给到 1800 秒。

**Q：失败工件里为什么没有 config/ 了？**
A：旧版本会把 `config/` 一并上传，等于把可直接复用的登录凭据写进工件。现在只上传 `**/*.log`；
需要排查配置问题时，请在本地用 `python ci/platform_guard.py --validate` 复现。

**Q：为什么 `script/shyp/auto_buy.py` 没有同步过来？**
A：该文件把一枚真实 JWT（含手机号）硬编码在源码里，属于凭据泄露，且定时抢购不适合无人值守执行。
如需使用，请改为从配置读取，并在上游删除历史提交中的该凭据。

## 📄 开源协议
本项目采用 [MIT License](LICENSE) 开源协议。

---

**⭐ 如果这个项目对你有帮助，欢迎给个 Star！**
