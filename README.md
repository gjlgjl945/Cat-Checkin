# Cat-Checkin 🐱

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

各平台字段的详细获取方法见下方 [🔑 账号信息获取教程](#-账号信息获取教程)。

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

按平台不同，你需要以下两类工具之一：

| 工具 | 适用场景 | 获取方式 |
|---|---|---|
| 浏览器 DevTools | 网页端可登录的平台（看雪、WPS） | Chrome/Edge 按 `F12` 即可，无需安装 |
| Fiddler Classic | APP / 微信小程序抓包（顺丰、鸿星尔克、什么值得买） | https://www.telerik.com/fiddler/fiddler-classic 免费下载 |

**Fiddler 抓包 HTTPS 的前置设置**（只需做一次）：

1. 打开 Fiddler → **Tools → Options → HTTPS**
2. 勾选 `Capture HTTPS CONNECTs` 和 `Decrypt HTTPS traffic`
3. 弹出证书安装提示时全部点"是"
4. **Connections** 标签页确认端口为 `8888`，勾选 `Allow remote computers to connect`
5. 手机和电脑连同一个 Wi-Fi，手机 Wi-Fi 设置里把代理改为「手动」，服务器填电脑 IP（`ipconfig` 查看），端口 `8888`
6. 手机浏览器访问 `http://ipv4.fiddler:8888` 下载并安装 Fiddler 证书（安卓还需在系统设置中信任该证书）

> ⚠️ 抓包完成后请及时关闭手机代理设置，否则断开电脑后手机无法上网。

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

纯网页操作，浏览器就能搞定，无需抓包工具。

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

纯网页操作，浏览器就能搞定。

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

1. Chrome/Edge 打开 https://www.smzdm.com 并登录
2. 按 `F12` → **Network（网络）** 标签 → 刷新页面
3. 点击 Network 里第一条 `www.smzdm.com` 请求 → **Headers** → **Request Headers**：
   - 复制 `Cookie:` 冒号后的整串 → 这就是 `cookie`
   - 复制 `User-Agent:` 整串 → 这就是 `user_agent`
4. `setting` 填空字符串 `""`

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

### ⚠️ 安全提醒

- `cookie` / `sign` / `setting` 等字段等同于你的登录凭证，**不要截图发到群里、不要提交到公开仓库**
- 本项目只通过 GitHub Secrets 注入这些信息，Secrets 对他人不可见
- 各平台 Cookie 都有有效期（几天到几个月不等），失效后脚本会报登录态错误，重新按上面步骤抓一次并更新 Secret 即可

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
