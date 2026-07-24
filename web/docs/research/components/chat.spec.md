# ChatApp（聊天主界面）规格

- 目标：`src/components/chat/*`（Sidebar / Composer / WelcomeScreen / MessageList / ChatApp）
- 截图参考：`docs/design-references/chat/01-home-1440-full.png`（原站）、`CLONE-home-1440.png`、`CLONE-thread-1440.png`
- 提取结构：`docs/research/chat-sidebar.json`
- 交互模型：**点击驱动**（切换会话、模式、开关、发送）

## 主题 token（与登录页同色系，LIGHT）
白底 `#fff` · 侧边栏/卡片底 `#f9fafb` · 主文字 `#0f1115` · 次灰 `#81858c` · 辅灰 `#61666b`
品牌蓝 `#3964fe` · 选中浅蓝 `#edf3fe` · 选中蓝边 `#b7c8fe` · 悬停 `rgba(0,0,0,.04)` · 分割线 `rgba(0,0,0,.1)`

## 外壳
flex row h-screen：侧边栏 261 + 主区 flex-1。

## 侧边栏（261，bg field，padding 6/12/10）
1. 顶栏（h48）：logo 字标(143×23) + 搜索/折叠图标钮（16，灰 #81858c，胶囊悬停）。
2. 新建对话钮（h40，白底，胶囊 100px，#0f1115，weight 500）："开启新对话"。
3. 会话列表（scrollbar-none）：sticky 分组头（"7 天内/30 天内"，12px #81858c，bg field）+ 会话项（h40，圆角 12，hover bg-hover，truncate 标题 + 悬停三点）。
4. 用户区（h44，圆角 12，hover）：32×32 圆形头像 + 用户名（#61666b）+ 三点菜单（设置/退出登录）。

## 主区
- 空对话 → WelcomeScreen：居中"你好，我是 DeepSeek" + 模式分段控件（快速/专家/识图，选中=白底蓝字胶囊）。
- 有对话 → MessageList（max-w 774，scrollbar-none）。

## 消息渲染
- 用户：右对齐气泡（bg field，圆角 2xl，max-w 80%）。
- 助手：可选「深度思考」可折叠块（边框 + bg field，Brain 蓝图标，"已深度思考(用时 N 秒)"，展开显灰文 + 复制）+ 模型徽标 + Markdown（标题/段落/粗体/行内码/深色代码块）+ 复制/重生成操作行。

## 输入框（Composer，max-w 774，居中）
- 圆角 26 白底框 + 边框/阴影，focus-within 蓝边。
- textarea（16px，placeholder "给 DeepSeek 发送消息"，自动增高，Enter 发送/Shift+Enter 换行）。
- 底排：深度思考 / 智能搜索 开关（h34 胶囊 18，未选=线边+#0f1115，选中=#edf3fe 底+#b7c8fe 边+#3964fe 字）+ 发送圆钮（有文本=蓝实心↑，无=灰）。
- 底部"AI 生成内容仅供参考"。

## 行为
切换会话/新建/模式/开关均为前端 state；发送追加用户消息 + mock 助手回复（深度思考开则带推理块、模型 R1）；"退出登录"回登录页。

## 已知保真度缺口（高保真，非逐像素）
- 图标用 lucide（近似，非 DeepSeek 原版自定义图标；原版 17 个 SVG 已存 `public/assets/chat/`）。
- 消息/流式为 mock，无真实后端。
- 移动端聊天（侧边栏抽屉）未实现；登录页已响应式。
- 二级菜单/状态为近似。
