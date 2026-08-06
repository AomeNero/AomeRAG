---
name: pg-lua-recipe
description: PG 图案发生器（Pattern Generator）Lua 测试脚本（Recipe）开发助手。用于编写、修改、查询或排查精测电测设备 PG 的 Lua 脚本——包括为液晶模组生成整套 Recipe、编写点屏初始化/上下电时序/老化测试/图案功能等单个 .lua 文件、查询 SYS/PWR/MIPI/DP/LVDS/TTL/I2C/SPI/REGS 等接口用法、修复现有 recipe 问题。任何提到 recipe、点屏、模组老化、MIPI/LVDS/eDP/TTL 信号、PG 脚本，或为电测/液晶模组行业写 Lua 代码的任务，都应主动使用此 skill，即使用户没有明确说 "PG" 或 "skill"。给新模组搭测试脚本、参考 PG 接口写寄存器/I2C/SPI 操作、生成 Lua 模板示例时同样适用。
---

# pg-lua-recipe — PG 图案发生器 Lua Recipe 开发

为精测 PG 图案发生器编写 Lua 测试脚本的专用技能。本 skill 内置 API 参考、编写指南和可直接复用的示例模板。

## 核心概念

- **Recipe**：UIS 上位机中每款液晶模组的测试脚本，一套 Lua 文件，实际加载运行的就是它。
- **Template**：`assets/RecipeTemplate/` 是 Recipe 的模板，不绑定具体模组；复制一份并填入模组参数即生成该模组的 Recipe。
- 所有交互接口是 C 侧暴露的全局函数，按模块命名：`SYS.` `PWR.` `MSG.` `TIME.` `GPIO.` `MIPI.` `REGS.` `DP.` `LVDS.` `TTL.` `I2C.` `SPI.` `ADDP.` `OPTICAL.`。

## 必读参考（动手前按需读取）

| 资源 | 何时读 |
|------|--------|
| `references/API_Reference.md` | 写任何接口调用前，先读对应模块段落，拿到精确签名/参数/返回值。含 LVDS/MIPI/eDP 典型流程。 |
| `references/Lua模板编写指南.md` | 涉及整套 Recipe、文件结构、命名、上下电时序、排查时必读。 |
| `assets/RecipeTemplate/` | 需要具体代码骨架/风格时，对照对应模板文件复制改写。 |

## 工作流程

### A. 生成整套 Recipe
1. 读 `references/Lua模板编写指南.md` §4（8 步流程），并读 `API_Reference.md` 中对应信号类型段落。
2. 收集模组规格：信号类型、时序 8 参数 + 刷新率、电源电压/限流、接口 Lane/位宽/频率、初始化 DCS 命令。缺参数时用合理默认值并明确标注待确认项。
3. 严格保持 `assets/RecipeTemplate/` 的目录结构与文件命名，生成完整文件集：
   - `main.lua`（入口，`require` ImageCfg/PowerCfg/TimingCfg/PScript/PowerOn）
   - `TimingCfg.lua`（时序参数：按信号类型从 `mipi_TimingCfg.lua` / `lvds_TimingCfg.lua` / `dp_TimingCfg.lua` 中选对应那个，**重命名为 `TimingCfg.lua`**；不要输出带信号前缀的 3 个原文件）
   - `PowerOn.lua`（上下电 + `InitCode()`）
   - `Signal.lua`（信号相关配置）
   - `PowerCfg.lua`（电源配置）
   - `ImageCfg.lua`（图案配置）
   - `image/`（图案位图，按需）
4. 输出到 **workspace 目录**（服务端以 `/workspace` 静态挂载，客户可下载）。用 `write` 工具把完整文件集写入 `Recipe_<规格>_<信号>/` 目录（如 `Recipe_1080x1920_MIPI/`），保持上述目录结构。

### B. 编写/修改单个 Lua 文件
- 先定位 `assets/RecipeTemplate/` 中的对应模板，复制其结构再改，保持注释块和缩进风格一致。
- 改 `PowerOn.lua` 必须遵守上下电时序（见下文"上下电时序要点"）。

### C. 查询 API 用法
- 读 `references/API_Reference.md` 对应模块，返回精确签名、参数含义、返回值、注意事项，必要时补一个最小示例。不要凭记忆编造接口签名。

### D. 排查 / 审查 Recipe
- 对照 `references/Lua模板编写指南.md` §7 逐条检查：上下电是否对称、延时是否合理、参数是否都从 `g*` 变量读取（无硬编码）、寄存器命令类型（0x39 长 DCS vs 短命令）是否正确、接口参数个数是否与签名一致（注意部分调用缺省 `chn`）、`require` 文件是否存在。
- 输出：问题定位 + 修改建议，不擅自改动用户代码。

## 核心编码约定

- **配置驱动**：可调参数（电压/时序/Lane/频率）一律从 `g*` 全局变量读取，不硬编码，否则 UI 修改不生效。
- **命名**：全局配置 `g` 前缀；流程函数 `F_` 前缀；固定入口 `PG_INIT` `RST` `InitCode` `F_POWER_ON` `F_POWER_OFF` `F_STEP_01` `F_STEP_RESET` `F_THIRD_CMD_PROCESS`。
- **常量**：电源用 `POWER_TYPE_VDD`/`VDDIO`/`ELVDD`/`ELVSS`/`VBL`/`VGH`/`VGL`/`TPVDD`/`TPVDDIO`；开关用 `ON`/`OFF`；信号用 `HS`/`LP`；老化状态用 `AGING_RUN`/`AGING_PAUSE`/`AGING_STOP`。
- **注释**：中文；文件头用精测标准注释块（File Name / Author / Version / Date / Model / Description）；函数块用 `--*****` 分隔注释；UTF-8 编码。
- **日志**：调试用 `MSG.Debug/Info/Println/Warning/Error`，给操作员的提示用 `MSG.Popup`。

## 上下电时序要点

**上电**：开 TPVDD→VDDIO→VDD（逐路延时）→ 复位 IP / 设模式 → 硬件 `RST()`（低→高）→ 启动信号 → 写初始化命令 → 退 Sleep(0x11) → 开背光 VBL → 开 ELVDD/ELVSS → 开显示(0x29)。
**下电**：严格逆序（先关 ELVSS/ELVDD 防残影）→ 关显示(0x28) → 关背光 → 进 Sleep(0x10) → 复位拉低 → 关 VGL/VDD/VDDIO/TPVDD/TPVDDIO → `SYS.InitFunDefault()`。
每步之间 `TIME.Delay` 不可省，参照模板毫秒值。

## 输出规范

- 整套 Recipe → 生成到 **workspace 目录**（服务端 `/workspace` 静态挂载，客户可下载），生成完整文件集后用 `bash` 工具把该目录压缩为 `Recipe_<目录名>.zip`：
  ```
  Compress-Archive -Path Recipe_1080x1920_MIPI -DestinationPath Recipe_1080x1920_MIPI.zip
  ```
- **回答必须给出可点击的 markdown 下载链接**（不要只写纯文本路径）：[下载 Recipe_<目录名>.zip](/workspace/<目录名>.zip)
  - 若用户需要完整地址，注明 = `http://<服务器IP>:8000` + 该路径。
  - `/workspace` 无目录列表，**不要给目录 URL**（会 404）；客户可下载 zip 整包，或已知路径的单个文件 `/workspace/<目录名>/<文件>`。
- 单文件 → 直接返回代码；API 查询 → 给出签名+示例；排查 → 给出问题+建议。
- 代码风格与 `assets/RecipeTemplate/` 现有模板保持一致。

## 已知模板问题（新建 recipe 时注意修正，勿原样照搬）

- 详见 `references/Lua模板编写指南.md` §8。

## 同步说明

本 skill 的 `references/` 与 `assets/RecipeTemplate/` 是 `D:\Code\skill` 项目根源文件的副本（`API_Reference.md`、`Lua模板编写指南.md`、`RecipeTemplate/`）。源文件更新后需手动同步到本 skill 内，否则内置副本会过期。
