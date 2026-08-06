# recipe lua模板编写指南

> **适用范围**：武汉精测电子 PG 图案发生器（Pattern Generator）
> **语言**：Lua 5.x
> **依据**：`API_Reference.md`（14 个接口模块）+ `luaTemplate/` 现有 16 个模板文件
> **用途**：说明 `luaTemplate/` 模板目录中各文件的职责，指导为新液晶模组编写/修改 Recipe
> **术语**：UIS2.0 上位机中每款模组的测试文件称 **Recipe**（一套 Lua 脚本，实际加载运行的就是它）；`luaTemplate/` 是 Recipe 的模板，复制一份并填入模组参数即生成该模组的 Recipe。本文档由 UIS2.0 上层驱动，适配精测 PG 系列通用，不针对特定机型。

---

## 1. 模板机制概览

每款待测液晶模组在 PG 上产测时，需要一份 **Recipe**（测试脚本，UIS 加载执行的就是它）。`luaTemplate/` 是 Recipe 的模板，不绑定具体模组；复制一份并填入模组参数，即成为该模组的 Recipe。Recipe 由**配置表 + 入口函数 + 流程函数**组成：

```
配置表（UI 可编辑）  →  生成全局变量（g 前缀）  →  入口函数 PG_INIT 点屏
                                                      ↓
                                              PowerOn 上下电流程
                                                      ↓
                                        老化测试 / 图案功能 / 第三方命令
```

- 用户在 UIS 上位机上通过 `pgconfig.lua` 的配置表填参数，PG 端生成对应 `g*` 全局变量。
- 开机时调用 `PG_INIT()` 按信号类型初始化；流程函数（`F_STEP_01` / `F_STEP_RESET` 等）由设备步骤驱动。
- 所有交互接口均为 C 侧暴露的全局函数（见第 6 节），脚本内直接调用。

---

## 2. 目录结构与文件职责

> `luaTemplate/` 即 Recipe 模板：其中每个文件组装起来，就是一份 Recipe 所需的全部 Lua 脚本。

```
luaTemplate/
├── pgconfig.lua            # 配置表：信号类型 / 电源 / 时序 / MIPI/LVDS/EDP 参数（UI 展示用）
├── pginit/
│   ├── MIPI.lua            # MIPI 屏点屏初始化 PG_INIT
│   ├── EDP.lua             # eDP 屏点屏初始化 PG_INIT
│   ├── LVDS.lua            # LVDS 屏点屏初始化 PG_INIT（⚠ 内容疑为 EDP 副本，见 §8）
│   └── TTL.lua             # TTL 屏点屏初始化 PG_INIT（⚠ 内容疑为 EDP 副本，见 §8）
├── PowerOn.lua             # 上下电时序：RST / F_POWER_ON / F_POWER_OFF / InitCode
├── defaultFunc/
│   └── defaultFunc.lua     # 步骤入口：F_STEP_01（上电）/ F_STEP_RESET（复位）
├── aging/
│   ├── AgingMain.lua       # 老化主流程：AgingTest / AgingInit / AgingMiddleWait
│   └── AgingPub.lua        # 老化公共函数：电源配置、AgingTrunk、图案切换
├── pictureFunction/        # 图案功能入口（调用 CATPATTERN 实现）
│   ├── gamma.lua           # Gamma 调节
│   ├── readedid.lua        # 读 EDID
│   ├── readvcom.lua        # 读 VCOM
│   ├── writeedid.lua       # 写 EDID
│   └── writevcom.lua       # 写 VCOM
└── systemlua/
    └── Signal.lua          # 信号公共函数 + 上位机通信回调（aging/switchpattern 等）
```

---

## 3. 命名与编码约定

| 类别 | 规则 | 示例 |
|------|------|------|
| 全局配置变量 | `g` 前缀 | `gSignalType`, `gActiveH`, `gVDD` |
| 流程函数 | `F_` 前缀 | `F_POWER_ON`, `F_STEP_01` |
| 固定入口 | 固定函数名 | `PG_INIT`, `RST`, `InitCode`, `StartAging` |
| 电源类型常量 | `POWER_TYPE_*` | `POWER_TYPE_VDD`, `POWER_TYPE_VBL` |
| 开关/状态常量 | 大写 | `ON`/`OFF`, `HS`/`LP`, `OK`/`NG`/`STOP` |
| 老化状态常量 | 大写 | `AGING_RUN`, `AGING_PAUSE`, `AGING_STOP` |

- 文件头使用精测电子标准注释块（File Name / Author / Version / Date / Model / Description）。
- 函数块使用 `--*****` 分隔注释，注明函数名、描述、输入、返回。
- 注释建议使用简体中文；注意 **UTF-8 编码**（现有 `defaultFunc.lua` 存在 GBK 乱码，见 §8）。

---

## 4. 基于模板编写一份新 Recipe 的流程

1. **定信号类型**：在 `pgconfig.lua` 的 `SignalType` 表确认 `val`（0=LVDS, 1=TTL, 2=MIPI, 3=eDP）。
2. **配参数表**：按屏体规格填写 `Tim`（ActiveH/ActiveV/HBP/HSW/HFP/VBP/VSW/VFP/FrameRate）、`PowerType`（9 路电源）、对应信号类型的参数表（MIPI / LVDS / EDP）。
3. **写点屏初始化**：在 `pginit/` 建立对应信号类型的 `PG_INIT()`，用 `g*` 全局变量依次配置信号类型、时序、刷新率、位宽、Lane 数，最后 `PWR.InitPower()` + `SYS.InitFunDefault()`。
4. **写上下电时序**：在 `PowerOn.lua` 实现 `RST()`（GPIO 复位）、`F_POWER_ON()`、`F_POWER_OFF()`、`InitCode(chn)`（写模组初始化 DCS 命令）。
5. **写步骤函数**：在 `defaultFunc.lua` 定义 `F_STEP_01`（上电）与 `F_STEP_RESET`（复位）。
6. **（可选）老化测试**：新建 `AgingCfg.lua`（配置全局变量）、`ImageCfg.lua`（图案表 `ImageTable`），复用 `AgingMain.lua` / `AgingPub.lua` 的流程。
7. **（可选）图案功能**：在 `pictureFunction/` 中让对应函数调用 `CATPATTERN()` 完成读写 EDID/VCOM、Gamma。
8. **（可选）第三方命令**：实现 `F_THIRD_CMD_PROCESS(cfg)` 供 `commonluafunc` 回调调用。

> 新增一个模组 = 复制一份 `luaTemplate/` 生成该模组的 **Recipe**，只改 **配置表 + pginit + PowerOn 时序 + 初始化代码**，流程框架文件（aging/、systemlua/、defaultFunc/ 等）无需改动。

---

## 5. 各文件详解

### 5.1 pgconfig.lua —— 配置表（UI 驱动）

每个表项的 `val` 是传给 PG 的数值，`key` 是给上层 UI 引导开发的名称；注释说明控件类型/默认值/取值范围。

| 表 | 内容 |
|----|------|
| `SignalType` | 信号类型单选（默认 MIPI=2） |
| `RecipeType` | 测试类型（Tester / Aging） |
| `PowerType` | 9 路电源枚举值 `0x0001~0x0100` |
| `PowerItem` | 每路电源的限流子项：OVP / OCP / UVP / UCP / FlyTime / FallTime |
| `Tim` | 时序 8 参数 + FrameRate |
| `MIPI` | Link / Bit / LANE / TYPE / MODE / DSI(MHz) / SplitMode / ContinuousMode / Phy_Mode |
| `LVDS` | LANE / BIT / LVDS_TYPE(VESA|JEIDA) / 三极性 / SplitMode / LINKORDER |
| `EDP` | SplitMode / backLightMode / PoliceMaker / HPD 训练延时 / TrainingMode / UseMaxLink / EQLevel / VODLevel / LaneCount / LinkRate / 极性 / Bit |
| `RULE` | UI 控件禁用规则（例：MIPI_TYPE=0 时禁用 Pulse/Event/Burst） |

### 5.2 pginit/*.lua —— 点屏初始化入口

`PG_INIT()` 在开机加载模组信息时调用，**只做参数下发，不做上电**。

- **MIPI.lua**：`MIPI.SetLinkNum` → `MIPI.SetColorBitWide` → `SYS.SetSignalType` → `MIPI.Init(时序)` → `MIPI.RefrshRate` → `MIPI.DSIFrequence` → `MIPI.SetMIPILaneNum` → `PWR.InitPower` → `SYS.InitFunDefault`。
- **EDP.lua**：`SYS.SetSignalType` → `DP.Init(...)` → `DP.SetGeneralTiming` → `DP.SetSplitMode` → `DP.RefrshRate` → `DP.SetColorBitWide`。
- **LVDS.lua / TTL.lua**：⚠ 当前内容与 EDP 相同（见 §8），正式使用前需改为对应接口（`LVDS.SETTIMIING` / `TTL.SetTiming` + `TTL.InitTTLParameters`）。

### 5.3 PowerOn.lua —— 上下电时序（最常修改）

**`F_POWER_ON()` 推荐顺序**（OLED/MIPI 屏示例）：
```
1. 开 TPVDD → VDDIO → VDD（每步 TIME.Delay(10)）
2. MIPI.ResetMIPIIP() → MIPI.SetMipiMode(模式) → 延时
3. RST()：GPIO 复位脚 低→高（含两次 10ms 延时）
4. MIPI.Start(ON) 启动信号
5. InitCode(chn)：写模组初始化 DCS 命令（REGS.WRITE）
6. 写 0x11（退出 Sleep）→ 延时 → 开 VBL 背光 → 延时 → 开 ELVDD / ELVSS
7. 写 0x29（开启显示）→ MIPI.HSLP(HS)
```

**`F_POWER_OFF()` 推荐顺序**（逆序，防残影）：
```
1. 关 ELVSS → ELVDD → 写 0x28（关显示）→ 延时 → 关 VBL
2. 写 0x10（进 Sleep）→ GPIO.MIPISET1(0) 复位拉低
3. 关 VGL → VDD → VDDIO → TPVDD → TPVDDIO
4. SYS.InitFunDefault() 复位显示功能
```

**`RST()`**：`GPIO.SetGpioOutVol(1, 0)`（1.8V）→ 复位脚拉高 → 延时 → 拉低 → 延时 → 拉高。

**`InitCode(chn)`**：集中存放模组初始化命令，用 `REGS.WRITE(chn, 0x39, reg, value[, value...])` 逐条写入（0x39 为 DCS 长命令类型）。

### 5.4 defaultFunc.lua —— 步骤入口

- `F_STEP_01()`：测试第 1 步，调 `F_POWER_ON()`。
- `F_STEP_RESET()`：复位步骤，调 `F_POWER_OFF()`。
- 如需更多步骤（Step2ToStep1 回退等），可在此扩展，配合 `gStepBack` 与 `setstepno()` 使用。

### 5.5 aging/ —— 老化测试

- **AgingMain.lua**：主流程与状态机。
  - `AgingInit()`：用 `socket.gettime()` 初始化起止时间；按 `gChannelInfo` 使能位计算通道位图 `gChannelMaster/Slave/Dual`；初始化 `gAgingStatusInfo`。
  - `SendAgingInfo()`：组装老化状态表，调 `SYS.ReportInfo()` 上报 UIS/ARM。
  - `AgingMiddleWait()`：每轮检查暂停/停止/超时/通道 NG，NG 时关闭对应通道位。
  - `AgingTest()`：入口，`while(gEndTime >= socket.gettime())` 按 `gTrunkCfg` 逐条执行 `AgingTrunk`，累计 `runCount` 达 `gRound` 提前结束。
- **AgingPub.lua**：公共函数。
  - `AgingInitPwrCfg` / `AgingSetPwrByInitInfo` / `AgingSetPwrByTrunk`：三套电源配置在 `g*` 全局量与 `gInitPwrCfg` 表、`pwrCfg` 表间搬运，最终 `PWR.InitPower()`。Trunk 模式 OVP = 电压 × 1.2。
  - `AgingTestStart` / `AgingTestEnd`：老化前后处理（初始化、上电、发状态、下电、弹窗结果）。
  - `AgingTrunk(trunkNum)`：单条老化干线。按 `onOffCfg` 定时电源开关；按 `imageInterval` 定时切换图案（`AgingShowPTN` 调 `SYS.SwitchPtn`）；支持 `beforeFun`/`afterFun` 钩子。
  - `AgingShowPTN(PtnIndex)`：从 `ImageTable[PtnIndex]` 取 `{图案名, 显示前函数, 显示后函数}` 执行。
- **依赖配置**（模板中需自行提供）：`AgingCfg.lua`（`gAgingTestDuration`, `gChannelInfo`, `gTrunkCfg`, `gRound`, `gStopInterval` 等）、`ImageCfg.lua`（`ImageTable`）。

### 5.6 pictureFunction/ —— 图案功能

各文件为功能入口函数（gamma/readedid/readvcom/writeedid/writevcom），实现体调用 `CATPATTERN()` 完成实际读写。实际业务逻辑（探头采集、Gamma 调绑点等）可参考 `functioninterface.lua` 列出的函数清单实现，如 `F_GAMMA_TUNING_ONE_BAND()`、`READXYLV()`、`SetProbeSyncMode()` 等。

### 5.7 systemlua/Signal.lua —— 信号控制与通信

- **信号包装**：`HSLP`/`Start`/`DPSignalCtrl`/`LvdsSignalCtrl`/`UlpsIn`/`UlpsOut`/`InitFunDefault`/`ResetMIPISignal`。注意这里调用的是**无前缀底层函数**（`MipiSetHsOrLp`、`SetMIPIOutEn`、`DpMainSignalCtl`…），与模块化 API（`MIPI.*` 等）并存。
- **上位机命令回调**（UDP 端口 12590）：
  - `aging(cmdbuf)`：解析 JSON，按 `mode`（start/resume/stop/pause）切换 `gAgingStatus`，start 时调 `StartAging("AgingTest")`。
  - `switchpattern(cfgBuf)`：`{"cmd":"switchpattern","patternname":"..."}` → `SYS.SwitchPtn`。
  - `commonluafunc(cfgBuf)`：转发到 `F_THIRD_CMD_PROCESS(thirdCfg)`。
  - `reportagingstatus()`：返回老化状态 JSON（cjson 编码）。
- **其他**：`writeIIC` 统一返回 0/1；`DemuraWriteData(state, file, Dsctype, mode, StarAdd, EndAdd, len)` 按 bin 文件写入 Demura。

---

## 6. API 模块速查（对应 API_Reference.md）

| 模块 | 用途 | 编写模板时常用接口 |
|------|------|--------------------|
| `SYS` | 系统 | `SetSignalType`, `SwitchPtn`, `InitFunDefault`, `ReportInfo`, `GetPgId`, `ClearExpiredFiles` |
| `PWR` | 电源 | `InitPower`, `SetPwrOnOff`, `SetRealPwrInfo`, `OFF`, `GetPwrInfo` |
| `MSG` | 日志 | `Debug`/`Info`/`Println`/`Warning`/`Error`/`Popup`（支持 `%s`/`%d` 格式化） |
| `TIME` | 延时 | `Delay(ms)`, `LockDelay(ms)`（延时期间阻止队列消息） |
| `GPIO` | 引脚 | `SetGpioOutVol`, `SetGpioOutOnOff`, `MIPISET1/2`, `GetGpioStatus`, `GetGpioHz` |
| `MIPI` | MIPI 信号 | `Init`, `SetMipiPhyMode`, `SetLaneNum`, `SetMipiMode`, `SetColorBitWide`, `Start`, `HSLP`, `UlpsIn/Out`, `TESyncSwitchPtn` |
| `REGS` | MIPI 寄存器 | `WRITE(chn, 0x39, reg, val...)` 写 DCS；`tWRITE` 写面板寄存器；`READ` 读 |
| `DP` | eDP 信号 | `Init`, `DPSignalCtrl`, `SetDPLaneNum`, `SetLinkRate`, `ReadDPByAUX`, `WriteDPByAUX` |
| `LVDS` | LVDS 信号 | `LvdsSignalCtrl`, `SETTIMIING`, `SetSignalFormat`, `CheckLvdsOpenShort`, `SetlvdsPem` |
| `TTL` | TTL 信号 | `TTLSignalCtrl`, `SetTiming`, `InitTTLParameters`, `SetTTLVoltage`, `SetTTLPhase` |
| `I2C` | I2C 总线 | `SetI2CLevel`, `SetI2CBps`, `I2CPullupEn`, `ReadI2C`, `WriteI2C`, `SetI2CChannel` |
| `SPI` | SPI 总线 | `SetSPILevel`, `SetSPIChannel`, `SpiSetCsMode`, `Read`/`Write`, `QspiFlashWriteByBIN` |
| `ADDP` | 辅助工具 | `Array2Hexstr`, `Split`, `TimeDiff`, `WriteFile`, `CarveTb`, `CompareTb` |
| `OPTICAL` | 光学探头 | `Init`, `SendCmd`, `GetLv`, `SetSyncMode`, `GetFlicker`, `ReConnect` |

**典型流程模板**（见 API 文档 §典型使用流程）：
- LVDS：`SYS.InitMainCfg` → `SetSignalType(0)` → `PWR.InitPower` → `LvdsSignalCtrl(1,1)` → `SwitchPtn`。
- MIPI：`SetSignalType(2)` → `MIPI.SetMipiPhyMode(0)` → 配置 Lane/位宽/模式 → `MIPI.Init` → `MIPI.Start` → `REGS.tWRITE(1, 0x11, {0x00})` 退出 Sleep → `0x29` 开显示。
- eDP：`SetSignalType(3)` → `DP.Init` → `SetDPLaneNum` → `SetLinkRate` → `DPSignalCtrl(1,1)` → `ReadDPByAUX` 读 EDID。

---

## 7. 编写要点与常见陷阱

1. **先配表再写码**：所有可调参数（电压、时序、Lane、频率）都应从 `g*` 全局变量读取，不要硬编码，否则 UI 修改不生效。
2. **上下电必须对称**：下电顺序与上电相反，OLED 屏务必先关 ELVSS/ELVDD 再关 VBL，防止残影烧屏。
3. **延时不可省**：电源切换、复位、Sleep in/out 后都要 `TIME.Delay`，参照模板中的毫秒值。
4. **寄存器写前先确认命令类型**：`REGS.WRITE(chn, 0x39, ...)` 用于长 DCS（多字节），短命令用 `tWRITE`；带 `0xFE` 页切换命令按顺序写。
5. **接口参数个数以 API 文档为准**：部分模板调用省略了 `chn` 参数（如 `GPIO.MIPISET1(1)`、`MIPI.ResetMIPIIP()`），若遇"参数个数不匹配"报错，补上通道号。
6. **新老接口并存**：`systemlua/` 里是无前缀底层函数（`SetMIPIOutEn`、`WriteI2C`…），模块化 API（`MIPI.*`、`I2C.*`…）更通用，新代码优先用模块化 API。
7. **老化配置分离**：老化跑的是 `AgingCfg.lua` + `ImageCfg.lua` 里的全局量，改配置不要动 `AgingMain.lua` / `AgingPub.lua` 流程逻辑。
8. **上报用 SYS.ReportInfo / MSG.Popup**：给上位机的状态走 `ReportInfo`（JSON 结构见 `SendAgingInfo`），给操作员看的提示用 `MSG.Popup`。

---

## 8. 当前模板中发现的疑似问题（未改动，请确认）

| 位置 | 问题 | 建议 |
|------|------|------|
| `pginit/LVDS.lua` | 整个文件内容是 eDP 的 `DP.Init` 代码，注释仍写"MIPI屏" | 应改为 `LVDS.SETTIMIING` / `LVDS.SetSignalFormat` 等 LVDS 接口 |
| `pginit/TTL.lua` | 同上，内容为 eDP 代码 | 应改为 `TTL.SetTiming` / `TTL.InitTTLParameters` 等 |
| `pginit/EDP.lua` | 注释"针对MIPI屏"与实际 eDP 代码不符 | 仅注释笔误，代码正确 |
| `defaultFunc.lua` | 注释为乱码（GBK 编码，如 `--����`） | 转 UTF-8 后重写中文注释 |
| `systemlua/Signal.lua` | `LvdsSignalCtrl(val)` 内部调用自身，形成无限递归 | 应调用底层 `LvdsSignalCtrl(val)` 的 C 实现或改名包装 |
| `AgingMain.lua` | `require("AgingCfg")` / `require("ImageCfg")` 文件未包含在模板中 | 新建模组时需自备这两个配置文件 |
| `PowerOn.lua` | `MIPI.SetMipiMode(gMIPI_TYPE)` 等调用缺 `chn` 参数 | 与 API 签名不一致，若报错补通道号 |

---

## 附录 A：常用全局变量速查

| 变量 | 含义 |
|------|------|
| `gSignalType` | 信号类型 0=LVDS 1=TTL 2=MIPI 3=eDP |
| `gActiveH/gActiveV/gHBP/gHSW/gHFP/gVBP/gVSW/gVFP` | 时序 8 参数 |
| `gFrameRate` | 刷新率（Hz） |
| `gBit` | 颜色位宽 6/8/10/12 |
| `gLink` | Link 数量 1/2/4/8 |
| `gMIPI_LANE` / `gMIPI_DSI` / `gMIPI_TYPE` | MIPI Lane 数 / DSI 频率(MHz) / 模式(Video=0,CMD=1) |
| `gSplitMode` | 分屏 0=不分屏 1=左右 2=奇偶 |
| `gbackLightMode/gPoliceMaker/gEDP_LaneCount/gEDP_LinkRate` | eDP 背光/Pole 模式/Lane/链路速率 |
| `gVDD/gVDDIO/gVBL/gVGH/gVGL/gELVDD/gELVSS/gTPVDD/gTPVDDIO` | 各路电源电压（mV）及 `_Limit_OVP/OCP/UVP/UCP/FlyTime/FallTime` |
| `gAgingStatus` / `gAgingStatusInfo` | 老化运行状态 / 上报信息表 |
| `gChannelInfo` / `gTrunkCfg` / `ImageTable` | 老化通道 / 干线 / 图案表（由 AgingCfg/ImageCfg 提供） |
| `gStepBack` | 回退控制 1=仅上电 2=断电再上电 3=直接上电 |
