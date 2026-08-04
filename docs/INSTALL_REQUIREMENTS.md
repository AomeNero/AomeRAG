# AomeRAG 本地部署需求文档

> 目标：让**非技术用户**在 **Windows 10** 电脑上，通过双击脚本完成安装，无需理解命令行。
> 前提：国内网络环境，无法访问 GitHub / Google / npm 官方源；`winget` 不可用。

---

## 1. 目标用户画像

| 属性 | 说明 |
|---|---|
| 操作系统 | Windows 10（64位） |
| 技术水平 | 会双击文件、会打开浏览器，不会用命令行 |
| 网络环境 | 国内，无法直接访问 GitHub / Google / npmjs.com |
| 硬件 | 普通办公电脑（8GB+ 内存，无独立显卡） |

---

## 2. 安装包需要包含的组件

### 2.1 运行时依赖（离线安装包）

| 组件 | 版本要求 | 国内下载地址 | 说明 |
|---|---|---|---|
| **Python** | 3.12.x 嵌入式包 | https://mirrors.huaweicloud.com/python/3.12.4/python-3.12.4-embed-amd64.zip | 不需要完整安装，嵌入式即可 |
| **Node.js** | 18.x LTS（仅构建时需要） | https://npmmirror.com/mirrors/node/v18.20.4/node-v18.20.4-x64.msi | 构建完前端后不需要 |
| **Pandoc** | 3.x | https://mirrors.tuna.tsinghua.edu.cn/github-release/jgm/pandoc/LatestRelease/ | docx 清洗用 |
| **Ollama** | 最新版 | https://ollama.com/download/OllamaSetup.exe | 本地 embedding 模型运行时 |
| **bge-m3 模型** | — | `ollama pull bge-m3`（Ollama 安装后执行） | 约 1.2GB，需 Ollama 运行中 |

### 2.2 项目组件（随安装包分发）

| 组件 | 来源 | 说明 |
|---|---|---|
| **后端** | PyInstaller 打包为 `aomerag.exe` | 单文件可执行，内嵌 Python 运行时 + 所有依赖 |
| **前端** | `npm run build` 产出 `web/dist/` | 静态文件，由 FastAPI 托管 |
| **知识库数据** | 预清洗的 `raw/md-data/` + Zvec 索引 `data/zvec/` | 预装知识库，开箱即用 |
| **配置模板** | `.env.example` → `.env` | 安装脚本自动填入 API Key |
| **SQLite 数据库** | `data/sessions.db` | 空数据库，首次运行自动创建 |

### 2.3 Python 依赖（离线 wheel 包）

以下依赖需提前下载 wheel 文件，打包进安装包的 `wheels/` 目录：

```
fastapi uvicorn pydantic pydantic-settings
httpx aiosqlite structlog
python-multipart
pandoc markitdown Pillow
zvec                    # 需要对应 Python 版本的 wheel
```

**下载方式**（在有网的机器上执行）：
```powershell
# 使用国内镜像批量下载 wheel
pip download -r requirements.txt -d wheels/ -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

---

## 3. 安装流程设计

### 3.1 用户操作步骤

```
1. 双击 "AomeRAG安装.bat"
2. 弹出黑色窗口，显示安装进度
3. 安装完成后桌面出现 "AomeRAG" 快捷方式
4. 双击快捷方式，浏览器自动打开
5. 首次打开弹出设置页面 → 填入 DeepSeek API Key → 保存
6. 开始使用
```

### 3.2 安装脚本职责（`install.bat`）

```
┌─────────────────────────────────────────────────┐
│  1. 检测 Python 嵌入式包是否已解压                  │
│     → 没有则解压到 %LOCALAPPDATA%\AomeRAG\python\  │
│                                                    │
│  2. 检测 Pandoc 是否已安装                          │
│     → 没有则静默安装到 %LOCALAPPDATA%\AomeRAG\      │
│                                                    │
│  3. 检测 Ollama 是否已安装                          │
│     → 没有则运行 OllamaSetup.exe 静默安装            │
│     → 等待 Ollama 服务启动                          │
│                                                    │
│  4. 检测 bge-m3 模型是否存在                        │
│     → 没有则执行 ollama pull bge-m3                 │
│                                                    │
│  5. 解压项目文件到 %LOCALAPPDATA%\AomeRAG\          │
│     - aomerag.exe（后端）                           │
│     - web/dist/（前端）                             │
│     - raw/md-data/（预装知识库）                     │
│     - data/zvec/（预建索引）                         │
│     - .env（配置模板）                               │
│                                                    │
│  6. 安装 Python wheels（离线）                      │
│                                                    │
│  7. 创建桌面快捷方式 "AomeRAG"                      │
│                                                    │
│  8. 完成！                                         │
└─────────────────────────────────────────────────┘
```

### 3.3 启动脚本职责（`start.bat`，快捷方式指向它）

```
1. 检测 Ollama 是否在运行 → 没有则启动
2. 检测 .env 中 API Key 是否已填写 → 没有则打开设置页面
3. 启动 aomerag.exe（后台运行）
4. 等待 http://localhost:8000 可访问
5. 自动打开浏览器
```

---

## 4. 网络问题解决方案

### 4.1 离线包准备（在有网的机器上）

| 操作 | 命令 / 说明 |
|---|---|
| 下载 Python 嵌入式包 | 浏览器访问华为云镜像下载 zip |
| 下载 Pandoc | 清华镜像下载 `.msi` 安装包 |
| 下载 Ollama | 官网下载 `OllamaSetup.exe` |
| 下载 bge-m3 模型 | `ollama pull bge-m3`（在有网机器上执行，模型缓存在 `%USERPROFILE%\.ollama\models`） |
| 下载 Python wheels | `pip download -d wheels/ -i https://pypi.tuna.tsinghua.edu.cn/simple/` |
| 构建前端 | `npm install --registry=https://registry.npmmirror.com && npm run build` |

### 4.2 Ollama 模型离线迁移

```powershell
# 在有网的机器上打包模型
# 模型存储在 %USERPROFILE%\.ollama\models\blobs\ 和 manifest\
# 将整个 .ollama 目录复制到安装包

# 在目标机器上
# Ollama 安装后会自动读取 %USERPROFILE%\.ollama\models\
# 无需额外操作
```

### 4.3 npm 镜像源（构建时使用）

```
https://registry.npmmirror.com          # 淘宝 npm 镜像
https://mirrors.huaweicloud.com/npm/    # 华为云 npm 镜像
```

### 4.4 pip 镜像源（构建时使用）

```
https://pypi.tuna.tsinghua.edu.cn/simple/   # 清华
https://mirrors.aliyun.com/pypi/simple/     # 阿里云
https://repo.huaweicloud.com/repository/pypi/simple/  # 华为云
```

---

## 5. 安装包目录结构

```
AomeRAG-Installer/
├── install.bat                 # 安装脚本（双击运行）
├── start.bat                   # 启动脚本（桌面快捷方式指向此文件）
├── README.txt                  # 简要说明（3 步上手）
│
├── bin/
│   ├── aomerag.exe             # PyInstaller 打包的后端
│   ├── python/                 # Python 3.12 嵌入式包（解压后）
│   └── pandoc/                 # Pandoc 便携版
│
├── wheels/                     # 离线 Python 依赖包
│   ├── fastapi-*.whl
│   ├── uvicorn-*.whl
│   └── ...（约 30-50 个 .whl 文件）
│
├── web/
│   └── dist/                   # 预构建的前端静态文件
│
├── data/
│   ├── zvec/                   # 预建的向量索引
│   └── sessions.db             # 空 SQLite 数据库
│
├── raw/
│   ├── raw-data/               # 原始知识库文件（可选，用于重新清洗）
│   └── md-data/                # 预清洗的 Markdown 知识库
│
├── prompt/
│   └── system-prompt.md        # 系统提示词
│
├── skills/                     # 技能文件
│   └── pg-api/
│
├── config/
│   ├── .env.example            # 配置模板
│   └── .env                    # 安装后生成（含用户 API Key）
│
└── ollama/
    └── models/                 # bge-m3 模型离线包（约 1.2GB）
```

---

## 6. 安装包大小估算

| 组件 | 大小 |
|---|---|
| Python 嵌入式包 | ~30MB |
| PyInstaller 打包后端 | ~50MB |
| Pandoc 便携版 | ~30MB |
| 前端 dist | ~1MB |
| Python wheels | ~20MB |
| bge-m3 模型 | ~1.2GB |
| 知识库数据（md-data + zvec） | 取决于数据量，预估 50-200MB |
| Ollama 安装包 | ~200MB |
| **合计** | **约 1.6-1.8GB** |

---

## 7. 首次启动设置流程

```
用户双击 "AomeRAG" 桌面快捷方式
         │
         ▼
  ┌──────────────────┐
  │ start.bat 检测：  │
  │ 1. Ollama 运行中？ │──否──→ 自动启动 Ollama
  │ 2. API Key 已填？  │──否──→ 打开浏览器到设置页
  │ 3. 知识库已索引？   │──否──→ 静默执行 ingest
  └──────────────────┘
         │
         ▼
  浏览器打开 http://localhost:8000
  → 如果 API Key 未填，跳转到首次设置页面
  → 用户输入 DeepSeek API Key → 保存
  → 进入聊天页面，开始使用
```

---

## 8. 已知限制与注意事项

| 限制 | 说明 | 应对 |
|---|---|---|
| Ollama 首次拉模型慢 | bge-m3 约 1.2GB，国内网络可能需要 10-30 分钟 | 安装包内预置模型离线包 |
| 无 GPU 加速 | 普通办公电脑无独立显卡，embedding 速度较慢 | 单次查询影响不大（<2秒） |
| 单进程限制 | Zvec 写独占，不支持多实例 | 安装脚本确保端口 8000 未被占用 |
| 知识库更新 | 用户追加新文件需手动触发 clean + ingest | 提供管理页面一键操作 |
| API Key 安全 | 存储在本地 .env 文件 | 仅本地使用，不上传任何服务器 |
| 端口冲突 | 如果 8000 被占用会启动失败 | 安装脚本检测端口并提示 |

---

## 9. 需要开发的工作项

- [ ] **PyInstaller 打包脚本**：将 `aome_rag` 打包为单文件 `aomerag.exe`
- [ ] **install.bat**：安装脚本（检测环境、解压文件、装依赖、创建快捷方式）
- [ ] **start.bat**：启动脚本（检测服务、启动后端、打开浏览器）
- [ ] **首次设置页面**：前端新增 `/setup` 路由，引导用户填写 API Key
- [ ] **知识库追加功能**：管理页面支持上传新文件 → 自动 clean + ingest
- [ ] **离线打包脚本**：自动化下载所有离线依赖的脚本
- [ ] **README.txt**：面向非技术用户的 3 步上手说明
