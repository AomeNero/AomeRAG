# 落地/登录页 — 页面拓扑 (PAGE_TOPOLOGY)

URL: https://chat.deepseek.com/sign_in

## 整体结构（自上而下）
```
body.zh_CN.light  (1440×900, bg #FFFFFF, overflow hidden)
└─ 根 div (flex column)
   ├─ 顶部占位 div (高 0，空)
   ├─ 居中容器 ._99ad066 (flex column, justify/align center, 1440×900)
   │  └─ 登录卡 .ds-auth-form-wrapper  ★唯一可见内容
   │     (608×524, flex column, align center, padding 40px 0, 无背景/边框/阴影)
   │     ├─ [1] Logo 区 (182×28, 居中) — DeepSeek 字标 SVG
   │     └─ [2] 双列区 (608×276, flex row, gap 32)
   │        ├─ 左列 表单 (336, flex column, flex 1)
   │        │  ├─ 手机号字段行 (336×70)：胶囊输入(48) + 辅助文案槽(22)
   │        │  ├─ 验证码字段行 (336×70)：胶囊输入(48, 含发送验证码) + 辅助槽(22)
   │        │  ├─ 协议行 (336×36, #81858C 12px)：含「用户协议」「隐私政策」链接
   │        │  ├─ 登录按钮 (336×42, 蓝胶囊)
   │        │  └─ 次级登录行 (336×18)：「密码登录」| 「使用 Apple 账号登录」
   │        └─ 右列 微信卡 (240×276, bg #F9FAFB, 圆角10, 边框 rgba(0,0,0,0.1))
   │           ├─ 二维码区 (238×160, 居中, iframe 占位)
   │           └─ 标签行 (238×22)：微信图标(20) + 「微信扫码登录」+ 绿勾(20, #00BC0C)
   ├─ 通知容器 top-right (fixed, z1500, 默认空)
   └─ 通知容器 bottom-right (fixed, z1500, 默认空)
```

## 区块清单
| # | 区块 | 类型 | 交互模型 | 状态 |
|---|------|------|---------|------|
| 1 | Logo | 静态 | 无 | — |
| 2a | 表单（左列） | 有状态 | 点击切换（验证码↔密码模式） | 2 模式 + focus 态 |
| 2b | 微信卡（右列） | 静态展示 | 无（二维码跨域） | — |
| 3 | 页脚 ICP/联系 | 静态 | 链接 | — |

## z-index 层级
- 内容流：z auto
- toast 通知：z 1500（fixed，默认空）

## 组装要点
- 登录卡水平+垂直居中于视口。
- 移动端：卡片 max-w 336，双列→单列，gap 32→20。
- body `overflow: hidden`（登录页不滚动，内容一屏装下；移动端内容增高后实际允许滚动——克隆中用 `overflow auto` 更稳）。
