# AomeRAG 局域网服务器部署包（deploy/）

把 AomeRAG 打包成「便携瘦包」，交给一台外面（局域网内）的 Win10 机器，小白只需**解压 + 双击「启动.bat」**。

这套部署的定位（grilling 定稿）：

| 决策 | 选择 |
|---|---|
| 运营形态 | 服务器，多人浏览器访问 |
| 访问范围 | 纯局域网（不做公网穿透/真实鉴权） |
| 搭建动手 | 小白现场装 + 技术方远程协助 |
| 交付方式 | USB 整包（瘦包：不含 Ollama/模型，首次启动现场下载） |
| 知识库 | 打包现成索引 + md-data + raw-data，且服务器保留 /admin 清洗切片 |
| DeepSeek key | 打包时填（开发机 .env 里的 key） |
| 常驻 | 开机自启 + 7×24 |
| 更新 | 轻量更新包（kb/app 两种），放进 `updates/` 双击「重启.bat」应用 |

## 目录结构

```
deploy/
├─ build_bundle.ps1     # 开发机打包脚本 → deploy/out/AomeRAG-Server-<date>/
├─ build_update.ps1     # 生成更新包 update-<type>-<date>.zip
├─ server/              # 打包进 bundle 根目录的脚本与说明
│  ├─ 启动.bat          # 小白双击：装 Ollama→拉模型→防火墙→开机自启→启动
│  ├─ 重启.bat          # 杀旧服务→应用 updates/*.zip→重启
│  ├─ run_server.cmd    # 服务启动器（启动.bat/计划任务共用）
│  └─ 使用说明.txt      # 给小白的一页说明
└─ out/                 # 打包产物（gitignore 之外，通常不入库）
```

## 打包（开发机上运行）

```powershell
# 完整打包 + 自检 + 压缩成 zip
powershell -ExecutionPolicy Bypass -File deploy\build_bundle.ps1 -Zip

# 常用参数
-ApiKey "sk-xxx"   # 覆盖 .env 里的 DeepSeek key
-SkipFrontend      # 跳过 npm run build（web/dist 已存在时）
-SkipCheck         # 跳过打包后离线自检（不建议）
```

打包脚本会自动完成：`npm run build` → 复制 venv 的 base 便携 Python（3.12 win-x64）→ 复制 venv 依赖（排除本地可编辑安装）→ 复制 `src` / `web/dist` / `data/zvec`（含 LOCK 文件——zvec 打开集合需要它）/ `raw/` → 生成已填 key 的 `.env` → 下载便携 pandoc → **离线自检**（用包内 Python 起 app，`/stats` 验证 zvec 可加载、n_chunks>0）。

> **打包前置条件**：开发机 `.env` 有 `DEEPSEEK_API_KEY`；`data/zvec` 已有向量索引（先 `/ingest/dir` 或 `/admin` 切片）；`web/dist` 能构建。

### 包结构（目标机器上）

```
AomeRAG-Server-<date>/
├─ runtime/python/      # 便携 Python 3.12 + 全部依赖（可重定位）
├─ app/                 # 应用：src + web/dist + data/zvec + raw/ + .env
├─ tools/pandoc.exe     # 便携 Pandoc（docx 清洗；启动时由 run_server.cmd 加 PATH）
├─ updates/             # 放更新包；重启.bat 应用后移到 updates/applied/
├─ 启动.bat / 重启.bat / run_server.cmd / 使用说明.txt
```

## 目标机器首次搭建

1. 解压整个文件夹到任意位置（比如 `D:\AomeRAG-Server`）。
2. 双击「启动.bat」→ UAC 点【是】。
3. 首次会自动：下载安装 Ollama（~700MB，静默，失败会提示手动装）→ `ollama pull bge-m3`（~1.2GB，带重试）→ 防火墙放行 8000 → 注册开机自启（计划任务 `AomeRAGService`，登录时拉起）→ 启动服务。
4. 局域网用户浏览器访问 `http://<机器IP>:8000`。

## 更新流程

> **⚠️ 重要：首次装好后，以后所有更新都走下面的「更新包」，不要再重拷整个 `AomeRAG-Server-<date>` 文件夹。**
> 服务器上的 `runtime/`（便携 Python+依赖）和 `tools/`（pandoc）共约 557MB，**从不变**；
> 每次重拷全量包等于把这 557MB + 上万个小文件白白传一遍，又慢又没意义。更新包只含变更部分。

知识库更新（先在开发机 `/admin` 跑清洗+切片，确认索引新了再打）：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\build_update.ps1 -Type kb
```

应用代码更新（改代码后先 `npm run build`）：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\build_update.ps1 -Type app
```

把生成的 `update-*.zip` 拷到服务器 `updates\` 文件夹，双击「重启.bat」→ 自动解压覆盖到 `app\` 并重启。**会话历史 `data/sessions.db` 永远保留**（更新包不含它）。

`build_update.ps1` 打包后会自动自检（用开发机 venv 起 app）：
- `-Type kb`：打开更新包里的 zvec 索引，断言 `n_chunks > 0`（防止交付空/半写索引）
- `-Type app`：用更新包里的新代码干净启动（不依赖开发机索引）
- 自检失败会**拒绝生成更新包**；紧急时可用 `-SkipCheck` 跳过（不建议）

## 注意事项 / 已知限制

- **`build_*.ps1` 故意不用 `param(...)` 块，改为手动解析 `$args`**：PowerShell 5.1 在「带 param 块的脚本被调用、且后续用位置参数调用 cmdlet」时存在参数绑定 bug（会把字符串误绑到 `[switch]` 参数，例如 `Join-Path` 报 `SwitchParameter` 转换错）。改脚本时请保持这个约定，别改回 param 块。
- **magika 的 dotenv 副作用（已修复，勿回退）**：markitdown 的依赖 `magika` 在 import 时执行 `dotenv.load_dotenv(dotenv.find_dotenv())`，会把**目录树上最近的 `.env`**（可能是别的项目/开发机的）灌进环境变量；而 pydantic-settings 里环境变量优先于 `.env` 文件，会覆盖本包配置。曾导致打包的服务器把 `DEEPSEEK_MODEL` 读成 `deepseek-v4-flash`（agent 会因模型不支持 function-calling 而坏）。`build_bundle.ps1` 复制 site-packages 后会中和这行副作用；自检也会断言 `llm_model == deepseek-chat` 兜底。
- **鉴权是信任式的**：前端自动生成 `X-User-Id`，后端无校验。**只适合可信局域网**；不要暴露到公网。若要上公网，必须先加真正的登录/token 鉴权。
- **`/admin` 清洗是全量重生成**：`raw/raw-data` 没文件时点「清洗」会清空 `md-data`。打包时脚本会警告；若服务器要现场清洗，务必让 `raw-data` 里有原始文档。
- **Ollama 静默安装**：`OllamaSetup.exe /S` 若在个别机器上不生效，会弹出安装界面，让小白点几下「Install/安装」即可（bat 有兜底提示）。
- **开机自启用的是「登录时」计划任务**：机器需有人登录（或配置自动登录）。如需无人值守，把计划任务改为「启动时」并注意权限。
- **单 worker 锁死**：`aomerag` CLI 固定 `--workers 1`，符合 Zvec 写独占约束，勿改。
- **DeepSeek key 明文**：在服务器 `app\.env`。内网可接受；如要更严，可对该文件设置 ACL。

## 排障速查

| 现象 | 处理 |
|---|---|
| 网页打不开/白屏 | 看 `AomeRAGService` 窗口是否在；重跑「重启.bat」；`http://localhost:8000` 本地先试 |
| 提问转圈 | 机器能否上网（DeepSeek 云端）；Ollama 是否就绪（`ollama list`） |
| 打包自检 n_chunks=0 | `data/zvec` 是空的，先在开发机 `/ingest/dir` 建索引 |
| `.bat` 双击没反应 | 用右键「以管理员身份运行」 |
| 端口被占 | 换个 `--port`（改 `run_server.cmd`），并同步防火墙规则 |
