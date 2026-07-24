# SignIn（落地/登录页）规格

- 目标：`src/components/SignInPage.tsx` + `SignInForm.tsx` + `WeChatCard.tsx`
- 截图：`docs/design-references/landing/desktop-1440-full.png`、`mobile-390.png`、`desktop-1440-password-mode.png`
- 完整结构 JSON：`docs/research/sign-in-card-structure.json`
- 交互模型：**点击切换**（验证码↔密码模式）+ 输入聚焦态

## 设计 token（见 src/index.css @theme）
背景 `#fff` · 主文字 `#0f1115` · 品牌蓝 `#3964fe` · 输入底 `#f9fafb` · 次灰 `#81858c` · 辅灰 `#61666b` · 线 `rgb(0 0 0/.1)` · 微信绿 `#00bc0c`

## 布局
- 居中卡 `.ds-auth-form-wrapper`：flex column items-center，padding `40px 0`，宽 608（桌面）/ 336（移动）。
- 子1：Logo（182×28，`/assets/logo-wordmark.svg`，蓝）。
- 子2：双列 flex row gap 32（桌面）/ flex col gap 20（移动）。
  - 左列 表单 336（flex-1）：手机号行70 + 验证码/密码行70 + 协议36 + 登录钮42 + 次级行18。
  - 右列 微信卡 240（flex-none）：bg field、圆角10、边框 line、padding 38 0 24。

## 输入框（h48 胶囊）
- bg field，rounded-full，未聚焦边框 line，聚焦（focus-within）边框 brand。
- 手机号（验证码模式）：`+86` 前缀 + input[placeholder=请输入手机号, tel]，wrapper px-2.5。
- 验证码：input[请输入验证码] + 1px 竖线 + 「发送验证码」蓝字钮（点击 60s 倒计时），wrapper pl-4 pr-5。

## 状态：两种模式
- 验证码（默认）：+86 手机号 + 验证码 + 发送验证码；切换钮「密码登录」。
- 密码：手机号/邮箱(text，无+86) + 密码(password)；切换钮「验证码登录」。

## 登录钮
w-full h42，bg brand，白字，rounded-full，font-medium 500。hover 轻微变暗。

## 协议文案（逐字）
注册登录即代表已阅读并同意我们的 [用户协议] 与 [隐私政策]，未注册的手机号将自动注册
（用户协议/隐私政策为 #0f1115 链接）

## 次级登录行
居中 gap8，12px 灰字胶囊：[密码登录/验证码登录] | [使用 Apple 账号登录]（hover 浅灰底）

## 微信卡
- 二维码区 160 高居中（跨域 iframe → 占位 QR）。
- 标签：微信图标(20) + 「微信扫码登录」+ 绿勾(20, #00bc0c)。

## 页脚
absolute bottom-0 水平居中，12px：[浙ICP备2023025841号](蓝,→beian.miit.gov.cn) · [联系我们](→飞书表单)。

## 响应式
- `md`(768) 断点：`<md` 单列（卡 336，gap 20）；`>=md` 双列（卡 608，gap 32）。
