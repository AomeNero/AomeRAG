---
name: pg-api
description: 武汉精测电子 PG361 图案发生器（Pattern Generator）的 Lua 脚本 API 参考助手。当用户提到 PG API 接口、PG361 API、PG 脚本接口、图案发生器，或正在编写、调试 PG361 的 Lua 脚本（脚本中调用 SYS、ADDP、GPIO、PWR、MSG、MIPI、REGS、DP、LVDS、TTL、I2C、SPI、TIME、OPTICAL 等模块接口，或询问 LVDS/MIPI/eDP 屏幕测试流程）时，务必使用本 skill，并参考 references/api.md 回答接口参数、返回值、用法相关问题。注意此处的 PG 指硬件图案发生器 PG361，与 PostgreSQL 数据库无关。
---

# PG361 图案发生器 API 助手

本 skill 用于回答与 **武汉精测电子集团 PG361 图案发生器（Pattern Generator）** Lua 脚本接口相关的问题。所有接口细节以 `references/api.md` 为唯一权威来源。

## 何时使用

当用户的提问涉及以下任意一种情况时使用本 skill：

- 直接提到 **PG API 接口**、**PG361 API**、**PG 脚本接口**、**图案发生器**
- 正在编写或调试 PG361 的 **Lua 脚本**，脚本中出现了 `SYS.*`、`GPIO.*`、`PWR.*`、`MSG.*`、`MIPI.*`、`REGS.*`、`DP.*`、`LVDS.*`、`TTL.*`、`I2C.*`、`SPI.*`、`TIME.*`、`OPTICAL.*` 这样的接口调用
- 询问某个具体接口的**参数、返回值、用法**（例如“SYS.SetSignalType 怎么用”“怎么读 MIPI 寄存器”“LVDS 屏幕测试流程是什么”）

## 如何回答

**第一步：阅读 API 文档。** 读取 `references/api.md`。这是一份 AI 可读的结构化 API 参考，涵盖 14 个接口模块、枚举常量与典型使用流程。不要凭记忆作答——硬件接口的参数类型、枚举值和返回码必须精确，凭记忆容易给错枚举值或返回值含义，直接导致脚本烧写到设备后行为异常。

**第二步：基于文档回答。**

- 引用接口时给出**准确的函数签名、参数、返回值和说明**，保留文档中的枚举取值（如 `SetSignalType` 的 `0:LVDS, 1:TTL, 2:MIPI, 3:eDP`）。
- 当用户场景跨多个模块时（例如初始化→配置信号→点亮屏幕），说明各模块如何配合，可参考文档末尾的“典型使用流程”。
- 文档中没有的接口，明确告知“当前 api.md 未记录该接口”，不要编造签名或参数。

## 文档结构速查（按需查阅 `references/api.md`）

| 模块/章节 | 用途 |
|------|------|
| 枚举与常量 | SignalType、PwrType、LogLevel、Color、GeoType 等取值定义 |
| SYS | 系统级：初始化、版本查询、图案/显示控制、图形字体 |
| ADDP | Lua 辅助工具：数据转换、表格/字符串处理、文件操作 |
| GPIO | GPIO 引脚控制：复位、电压、读写、PWM/频率测量、模拟 I2C |
| PWR | 电源管理：开关、电压/电流查询、PWM、限流告警 |
| MSG | 日志输出：DEBUG/WARNING/INFO/ERROR、弹窗 |
| MIPI | MIPI D-PHY/C-PHY：PHY 模式、初始化、Lane、ULPS、TE 同步 |
| REGS | MIPI 寄存器读写：DCS 命令、面板寄存器、Demura |
| DP | eDP 信号：时序、Lane、链路速率、AUX、HPD |
| LVDS | LVDS 信号：开关、时序、格式、预加重、开短路检测 |
| TTL | TTL 信号：时序、位偏移、RGB 顺序、相位、电压 |
| I2C | I2C 总线：电平、波特率、上拉、通道、读写 |
| SPI | SPI 总线：电平、通道、CS、标准 SPI / QSPI 读写 |
| TIME | 延时：普通延时、锁定延时 |
| OPTICAL | 光学探头：亮度读取、频率同步、闪烁测量 |
| 典型使用流程 | LVDS / MIPI / eDP 屏幕测试完整脚本示例 |

## 重要边界

- **PG ≠ PostgreSQL。** 本 skill 专指 PG361 硬件图案发生器。若用户问的是数据库（PostgreSQL / SQL / 查询优化等），不要使用本 skill。
- **以 `references/api.md` 为准。** 接口签名、枚举值、返回码只能来自文档，不接受外部推测。设备硬件接口容错性低，一个错误的枚举值就可能导致信号类型错配或电源配置异常。
