# Lua API 接口文档

> **设备**: 武汉精测电子集团 PG 图案发生器(Pattern Generator)
> **语言**: Lua 5.x
> **说明**: 本文档为 AI 可读的结构化 API 参考，涵盖全部 14 个接口模块。

---

## 目录

| 模块 | 名称 | 接口数 | 功能概述 |
|------|------|--------|----------|
| [SYS](#sys) | 系统接口 | 38 | 初始化、版本查询、图案切换、显示功能控制 |
| [ADDP](#addp) | Lua辅助工具 | 15 | 数据转换、表格操作、字符串处理、文件操作 |
| [GPIO](#gpio) | GPIO引脚控制 | 17 | 复位、电压设置、状态读取、PWM/频率测量、模拟I2C |
| [PWR](#pwr) | 电源管理 | 13 | 电源开关、电压/电流查询、PWM输出、限流告警 |
| [MSG](#msg) | 日志输出 | 8 | DEBUG/WARNING/INFO/ERROR日志、弹窗提示 |
| [MIPI](#mipi) | MIPI D-PHY/C-PHY | 26 | PHY模式、初始化、Lane配置、ULPS、TE同步 |
| [REGS](#regs) | MIPI寄存器读写 | 4 | DCS命令读写、面板寄存器、Demura数据 |
| [DP](#dp) | eDP信号控制 | 26 | 时序、Lane配置、链路速率、AUX通道、HPD |
| [LVDS](#lvds) | LVDS信号控制 | 14 | 信号开关、时序、格式、预加重、开短路检测 |
| [TTL](#ttl) | TTL信号控制 | 15 | 时序、位偏移、RGB顺序、相位、电压设置 |
| [I2C](#i2c) | I2C总线控制 | 7 | 电平、波特率、上拉、通道选择、读写 |
| [SPI](#spi) | SPI总线控制 | 18 | 电平、通道、CS模式、标准SPI/QSPI读写 |
| [TIME](#time) | 延时控制 | 3 | 普通延时、锁定延时 |
| [OPTICAL](#optical) | 光学探头控制 | 13 | 亮度读取、频率同步、闪烁测量 |

---

## 枚举与常量

### 信号类型 (SignalType)

| 值 | 说明 |
|----|------|
| 0 | LVDS |
| 1 | TTL |
| 2 | MIPI |
| 3 | eDP |

### 电源类型 (PwrType)

| 值 | 名称 | 说明 |
|----|------|------|
| 0x0001 | VDD | 核心供电 |
| 0x0002 | VDDIO | I/O供电 |
| 0x0004 | ELVDD | OLED正极 |
| 0x0008 | ELVSS | OLED负极 |
| 0x0010 | VBL | 背光 |
| 0x0020 | VGH | 栅极高压 |
| 0x0040 | VGL | 栅极低压 |
| 0x0080 | TPVDD | 触控供电 |
| 0x0100 | TPVDDIO | 触控I/O供电 |

### 日志等级 (LogLevel)

| 值 | 说明 |
|----|------|
| 1 | 开启所有日志 (ERROR, WARNING, INFO, DEBUG) |
| 2 | 开启 ERROR, WARNING, INFO |
| 3 | 开启 ERROR, WARNING |
| 4 | 开启 ERROR |
| 5 | 关闭所有日志 |

### 颜色枚举 (Color)

| 值 | 颜色 |
|----|------|
| 0 | 黑 |
| 1 | 红 |
| 2 | 绿 |
| 3 | 蓝 |
| 4 | 黄 |
| 5 | 青 |
| 6 | 反色 |
| 7 | 白 |

### 几何类型 (GeoType)

| 值 | 形状 |
|----|------|
| 0 | 圆 |
| 1 | 正方形 |
| 2 | 菱形 |
| 3 | 三角形 |
| 4 | 矩形 |
| 5 | 线 |
| 6 | 矩形填充 |

---

<a id="sys"></a>

## SYS - 系统接口模块

提供图案发生器(PG)的系统级操作接口。

### 初始化与配置

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `SYS.InitMainCfg` | `()` | 无 | `number` [0:OK, 1:NG] | 初始化主配置，根据全局变量设置信号类型、时序、颜色位宽、通道数、分屏模式等 |
| `SYS.InitMainSysCfg` | `()` | 无 | 无 | 初始化系统配置，设置PG ID、IP地址、PG类型、板卡类型等 |
| `SYS.InitFunDefault` | `()` | 无 | 无 | 恢复显示功能到默认状态(关闭色块、十字光标、图案移动等) |
| `SYS.SetSignalType` | `(type)` | `type:number` - 信号类型 [0:LVDS, 1:TTL, 2:MIPI, 3:eDP] | `number` [0:OK, 1:NG] | 设置信号类型 |
| `SYS.CheckSignalStatus` | `()` | 无 | `number` - 信号类型值 | 检查当前信号状态 |

### 版本查询

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `SYS.GetScriptVersion` | `()` | 无 | `string` | Lua公共脚本版本号 |
| `SYS.GetArmVersion` | `()` | 无 | `string` | ARM端软件版本号 |
| `SYS.GetQtGuiVersion` | `()` | 无 | `string` | Qt GUI上位机版本号 |
| `SYS.GetFPGAVersion` | `()` | 无 | `string` | FPGA固件版本号 |
| `SYS.GetDevicePowerVersion` | `()` | 无 | `string` | 电源板软件版本号 |
| `SYS.GetKernelVersion` | `()` | 无 | `string` | Linux内核版本号 |
| `SYS.GetKernelModuleVersion` | `()` | 无 | `string` | 内核模块版本号 |

### 图案与显示控制

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `SYS.SwitchPtn` | `(chn, ptnName)` | `chn:number` - 通道号[0x01/0x02/0x04/0x08/0x10]; `ptnName:string` - 图案名称 | `number` [0:OK, 1:NG] | 切换显示图案 |
| `SYS.SwitchPtnLock` | `(chn, ptnName, lockMs)` | `chn:number`; `ptnName:string`; `lockMs:number` - 锁定时间(ms) | `number` [0:OK, 1:NG] | 切换图案并锁定指定时间 |
| `SYS.SwitchRGB` | `(chn, R, G, B)` | `chn:number`; `R/G/B:number` - 灰阶值 | `number` [0:OK, 1:NG] | 开启RGB纯色显示 |
| `SYS.CloseRGB` | `()` | 无 | `number` [0:OK, 1:NG] | 关闭RGB纯色显示 |
| `SYS.ShowColorBlock` | `(chn, no, R, G, B, channel, sx, sy, ex, ey)` | `chn:number`; `no:number` - 色块编号; `R/G/B:number`; `channel:number` - [1或2]; `sx/sy:number` - 起始坐标; `ex/ey:number` - 结束坐标 | `number` [0:OK, 1:NG] | 开启色块显示 |
| `SYS.CloseColorBlock` | `()` | 无 | `number` [0:OK, 1:NG] | 关闭色块显示 |
| `SYS.GetPatternName` | `()` | 无 | `string` | 获取当前显示的图案名称 |
| `SYS.GetModuleName` | `()` | 无 | `string` | 获取当前模块名称 |

### 图形与字体显示

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `SYS.StartCrossCursor` | `(chn, x, y, R, G, B, step, startCoord, cursorEn, lineEn, screenPos)` | `chn:number`; `x/y:number` - 坐标; `R/G/B:number`; `step:number`; `startCoord:number`; `cursorEn:number`; `lineEn:number`; `screenPos:number` - [0:不反转, 1:反转] | `number` [0:OK, 1:NG] | 开启十字光标 |
| `SYS.CloseCrossCursor` | `()` | 无 | `number` [0:OK, 1:NG] | 关闭十字光标 |
| `SYS.StartPtnMove` | `(chn, xDir, xStep, yDir, yStep)` | `chn:number`; `xDir:number`; `xStep:number`; `yDir:number`; `yStep:number` | `number` [0:OK, 1:NG] | 开启图案移动 |
| `SYS.ClosePtnMove` | `()` | 无 | `number` [0:OK, 1:NG] | 关闭图案移动 |
| `SYS.StartShowFont` | `(chn, x, y, width, height, color, characters)` | `chn:number`; `x/y:number`; `width:number` (英文字符=height/2, 中文字符=height); `height:number` [48/64/80/96/112/128]; `color:number` - 颜色枚举; `characters:string` | `number` [0:OK, 1:NG] | 开启字体显示 |
| `SYS.CloseShowFont` | `()` | 无 | `number` [0:OK, 1:NG] | 关闭字体显示 |
| `SYS.StartShowMark` | `(chn, cnt, geoType, color, x, y, r)` | `chn:number`; `cnt:number`; `geoType:number` - 几何类型枚举; `color:number` - 颜色枚举; `x/y:number`; `r:number` - 半径 | `number` [0:OK, 1:NG] | 开启标记(几何图形)显示 |
| `SYS.CloseShowMark` | `()` | 无 | `number` [0:OK, 1:NG] | 关闭标记显示 |
| `SYS.StartYcbcr` | `(chn, mode)` | `chn:number`; `mode:number` - [0:RGBG, 1:GRGB, 2:BGRG, 3:RBGR] | `number` [0:OK, 1:NG] | 开启YCBCR模式 |
| `SYS.CloseYcbcr` | `()` | 无 | `number` [0:OK, 1:NG] | 关闭YCBCR模式 |

### 系统信息与工具

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `SYS.GetPowerStatus` | `()` | 无 | `string` ["on":已上电, "off":已断电] | 获取电源开关状态 |
| `SYS.GetDeviceBoardType` | `()` | 无 | `string` - 板卡类型描述 | 获取设备板卡类型 |
| `SYS.GetPgId` | `()` | 无 | `number` - PG ID | 获取图案发生器ID |
| `SYS.ReportInfo` | `(table)` | `table:table` - 信息表 | `number` [0:OK, 1:NG] | 上报信息到ARM系统 |
| `SYS.GetScriptPath` | `()` | 无 | `string` - 目录路径 | 获取Lua脚本所在目录 |
| `SYS.GetPgIP` | `()` | 无 | `string` - IP地址 | 获取PG端IP地址 |
| `SYS.GetPcIP` | `()` | 无 | `string` - IP地址 | 获取PC端IP地址 |
| `SYS.GetResetKeyIsPressed` | `()` | 无 | `number` [0:未按下, 1:已按下] | 获取复位按键状态 |
| `SYS.StopProcessEnable` | `()` | 无 | 无 | 停止进程使能 |
| `SYS.ClearExpiredFiles` | `(path, days)` | `path:string`; `days:number` - 过期天数(默认30) | 无 | 清理过期文件 |
| `SYS.GetTime` | `()` | 无 | `number` - 时间戳(ms) | 获取当前系统时间(毫秒) |
| `SYS.GetTimeSec` | `()` | 无 | `number` - 时间戳(s) | 获取当前系统时间(秒) |

---

<a id="addp"></a>

## ADDP - Lua辅助工具模块

提供数据类型转换、表格操作、文件写入、字符串处理等辅助函数。

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `ADDP.Array2Hexstr` | `(tb, sep)` | `tb:table` - 整数表; `sep:string` - 分隔符(可选, 默认",") | `string` - 如"0x01,0x02,0x03" | 整数表转十六进制字符串 |
| `ADDP.Array2Decstr` | `(tb, sep)` | `tb:table`; `sep:string` (可选) | `string` - 如"1,2,3" | 整数表转十进制字符串 |
| `ADDP.Array2Floatstr` | `(tb, sep)` | `tb:table`; `sep:string` (可选) | `string` - 如"1.0000,2.0000" | 表转浮点数字符串(默认四位小数) |
| `ADDP.AsciiChar2Hex` | `(str)` | `str:string` | `table` - 字节值表 | ASCII字符串转字节表 |
| `ADDP.AsciiHex2Char` | `(tb)` | `tb:table` - 字节值表 | `string` | 字节表转ASCII字符串 |
| `ADDP.CompareTb` | `(tb1, tb2, len)` | `tb1:table`; `tb2:table`; `len:number` | `number` [0:相同, 1:不同] | 比较两个表前len个元素 |
| `ADDP.ConvertDataToUint32` | `(tb, littleEndian)` | `tb:table` - 4字节表; `littleEndian:boolean` | `number` - Uint32值 | 字节表转Uint32 |
| `ADDP.ConvertDataToUint16` | `(tb, littleEndian)` | `tb:table` - 2字节表; `littleEndian:boolean` | `number` - Uint16值 | 字节表转Uint16 |
| `ADDP.ConvertUint32ToData` | `(data, littleEndian)` | `data:number`; `littleEndian:boolean` | `table` - 4字节表 | Uint32转字节表 |
| `ADDP.ConvertUint16ToData` | `(data, littleEndian)` | `data:number`; `littleEndian:boolean` | `table` - 2字节表 | Uint16转字节表 |
| `ADDP.WriteFile` | `(path, content)` | `path:string`; `content:string` | `number` [0:OK, 1:NG] | 写字符串到文件(追加模式) |
| `ADDP.CarveTb` | `(tb, startPos, length)` | `tb:table`; `startPos:number` (从1开始); `length:number` | `table` | 从表中截取子表 |
| `ADDP.Split` | `(str, sep)` | `str:string`; `sep:string` - 分隔符 | `table` - 字符串表 | 字符串分割 |
| `ADDP.ParseLineOrderStr` | `(str)` | `str:string` - 如"4321" | `table` - 如{4,3,2,1} | 行序字符串解析为数字表 |
| `ADDP.TimeDiff` | `(startTime, endTime)` | `startTime:number`; `endTime:number` | `table` - {days, hour, min, sec, log} | 计算时间戳差值 |

---

<a id="gpio"></a>

## GPIO - GPIO引脚控制模块

提供GPIO引脚控制，包括复位、电压设置、状态读取、PWM/频率测量、GPIO模拟I2C。

### 复位控制

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `GPIO.MIPISET1` | `(chn, state)` | `chn:number`; `state:number` [0:低, 1:高] | `number` [0:OK, 1:NG] | 设置MIPI复位1 |
| `GPIO.MIPISET2` | `(chn, state)` | `chn:number`; `state:number` [0:低, 1:高] | `number` [0:OK, 1:NG] | 设置MIPI复位2 |
| `GPIO.RESET1` | `(chn, state)` | 同MIPISET1 | `number` [0:OK, 1:NG] | 设置复位1(等同于MIPISET1) |
| `GPIO.RESET2` | `(chn, state)` | 同MIPISET2 | `number` [0:OK, 1:NG] | 设置复位2(等同于MIPISET2) |

### GPIO输出控制

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `GPIO.SetGpioOutVol` | `(chn, pinId, vol)` | `chn:number`; `pinId:number`; `vol:number` [0:1.8V, 1:3.3V] | `number` [0:OK, 1:NG] | 设置GPIO输出电压 |
| `GPIO.SetGpioNC` | `(chn, pinId)` | `chn:number`; `pinId:number` | `number` [0:OK, 1:NG] | 设置GPIO为高阻态(Hi-Z) |
| `GPIO.SetGpioOutOnOff` | `(chn, pinId, status)` | `chn:number`; `pinId:number` (1-10板载, >10扩展); `status:number` [0:低, 1:高] | `number` [0:OK, 1:NG] | 设置GPIO输出开关 |

### GPIO输入读取

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `GPIO.GetGpioStatus` | `(chn, pinId)` | `chn:number`; `pinId:number` (1-10) | `number` [0:低, 1:高] | 获取GPIO输入状态 |
| `GPIO.GetGpioVol` | `(chn, pinId)` | `chn:number`; `pinId:number` (1-10) | `number` - 电压(0-5V) | 获取GPIO输入电压 |
| `GPIO.GetGpioSwire` | `()` | 无 | `number` [0:低, 1:高] | 获取Swire信号状态(MIPI接口42脚) |
| `GPIO.GetGpioAvddEn` | `(chn)` | `chn:number` | `number` [0:低, 1:高] | 获取AVDDEN信号状态(MIPI接口41脚) |
| `GPIO.GetGpioTPINT` | `(chn)` | `chn:number` | `number` [0:低, 1:高] | 获取TP_INT(TP_ATTN)信号状态(MIPI接口51脚) |

### PWM与频率测量

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `GPIO.GetGpioPWM` | `(chn, channel)` | `chn:number`; `channel:number` (1-10) | `number` - PWM占空比(0-100) | 获取GPIO输入PWM占空比 |
| `GPIO.GetGpioHz` | `(chn, channel)` | `chn:number`; `channel:number` (1-10) | `number` - 频率值(Hz) | 获取GPIO输入频率 |
| `GPIO.ClearGpioPwm` | `(chn)` | `chn:number` | 无 | 清除GPIO PWM测量值 |

### GPIO模拟I2C

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `GPIO.I2cInit` | `(clk, sda, delay)` | `clk:number` - SCL引脚; `sda:number` - SDA引脚; `delay:number` - 延时计数 | `number` | 初始化GPIO模拟I2C |
| `GPIO.I2cWriteNoStop` | `(addr, buf, len)` | `addr:number`; `buf:number`; `len:number` | 无 | GPIO模拟I2C写(不发Stop) |
| `GPIO.I2CWrite` | `(i2cId, devAddr, regLen, regAddr, writeLen, writeUnit, writeData)` | `i2cId:number`; `devAddr:number`; `regLen:number`; `regAddr:number`; `writeLen:number`; `writeUnit:number`; `writeData:table` | `number` | GPIO模拟I2C写(发Stop) |
| `GPIO.I2CReadNoStop` | `(i2cId, devAddr, regLen, regAddr, readLen, readUnit)` | 同I2CWrite前6参数 | `table` - 读取数据 | GPIO模拟I2C读(不发Stop) |

---

<a id="pwr"></a>

## PWR - 电源管理模块

提供电源管理功能，包括电源初始化、开关控制、电压/电流查询、PWM输出、告警与限流。

### 电源控制

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `PWR.InitPower` | `()` | 无 | `number` [0:OK, 1:NG] | 初始化电源信息，配置各路电源参数并下发到电源板 |
| `PWR.SetPwrOnOff` | `(chn, pwrType, status)` | `chn:number`; `pwrType:number` - 电源类型枚举; `status:number` [0:关, 1:开] | 无 | 设置电源开关 |
| `PWR.SetRealPwrInfo` | `(chn, pwrType, vol, ovp, uvp, ocp, ucp)` | `chn:number`; `pwrType:number`; `vol:number`(mV); `ovp:number`(mV); `uvp:number`(mV); `ocp:number`(mA); `ucp:number`(mA) | 无 | 实时设置电源信息(断电20ms后生效) |
| `PWR.OFF` | `()` | 无 | `number` | 关闭所有电源并同步到UIS上位机 |

### 电源查询

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `PWR.GetPwrInfo` | `(chn, pwrType)` | `chn:number`; `pwrType:number` | `table` - {ret, pwrType, vol, cur, ovp, uvp, ocp, ucp, vPeak, vValley, cPeak} | 获取电源信息 |
| `PWR.GetPowerStatus` | `()` | 无 | `string` ["on"/"off"] | 获取电源板开关电状态 |
| `PWR.queryPwrInfo` | `(chn, pwrType)` | `chn:number`; `pwrType:number` | `table` | 查询单路电源信息 |
| `PWR.queryAllPwrInfo` | `()` | 无 | `table` | 查询所有电源信息 |

### PWM与告警

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `PWR.SetPwmCfg` | `(freq, duty)` | `freq:number` (1~15000Hz); `duty:number` (0~1) | `number` [0:OK, 1:NG] | 配置PWM输出 |
| `PWR.SetPowerLimitInfo` | `()` | 无 | 无 | 设置电源限流信息 |
| `PWR.PwrAlarmCtrl` | `(mode)` | `mode:number` [0:关闭单通道, 1:关闭所有] | `number` [0:OK, -1:NG] | 电源告警断电控制 |
| `PWR.PwrLimitCtrl` | `(pwrType, flag, value)` | `pwrType:number`; `flag:number` [0:禁用, 1:使能]; `value:number` | `number` [0:OK, -1:NG] | 电源限流控制 |
| `PWR.PwrOnLED` | `()` | 无 | 无 | 开启LED驱动电源(RS232) |
| `PWR.GetAlarmStatus` | `()` | 无 | `number` [0:无告警, 1:有告警] | 获取电源告警状态 |
| `PWR.ClearAlarmStatus` | `()` | 无 | `number` [0:OK, -1:NG] | 清除电源告警状态 |

---

<a id="msg"></a>

## MSG - 日志输出模块

提供UIS上位机日志输出功能，支持不同等级的日志和弹窗提示。

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `MSG.Debug` | `(format, ...)` | `format:string`; `...` - 格式化参数 | 无 | 输出DEBUG级别日志(蓝色) |
| `MSG.Info` / `MSG.Println` / `MSG.PRINTLN` | `(format, ...)` | `format:string`; `...` | 无 | 输出INFO级别日志(绿色)，三者等价 |
| `MSG.Warning` | `(format, ...)` | `format:string`; `...` | 无 | 输出WARNING级别日志(棕色) |
| `MSG.Error` | `(format, ...)` | `format:string`; `...` | 无 | 输出ERROR级别日志(红色) |
| `MSG.Popup` | `(logString, color)` | `logString:string`; `color:string` (可选, 如"green","red") | 无 | 弹窗显示日志(默认绿色) |
| `MSG.setLogLevel` | `(level)` | `level:number` [1~5] - 日志等级枚举 | 无 | 设置日志等级 |
| `MSG.getLogLevel` | `()` | 无 | `number` - 当前日志等级 | 获取当前日志等级 |

---

<a id="mipi"></a>

## MIPI - MIPI D-PHY/C-PHY 信号控制模块

提供MIPI D-PHY/C-PHY信号控制，包括PHY模式、初始化、Lane配置、ULPS、TE同步等。

### PHY模式与初始化

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `MIPI.SetMipiPhyMode` | `(mode)` | `mode:number` [0:D-PHY, 1:C-PHY] | `number` [0:OK, 1:NG] | 设置MIPI PHY模式 |
| `MIPI.Init` | `(chn)` | `chn:number` | `number` [0:OK, 1:NG] | 初始化MIPI参数 |
| `MIPI.SetMtpValue` | `(voltage)` | `voltage:number` | `number` [0:OK, 1:NG] | 设置MTP电压 |
| `MIPI.ResetMIPIIP` | `(chn)` | `chn:number` | `number` [0:OK, 1:NG] | 复位MIPI IP |
| `MIPI.SetDiscreteMode` | `(chn, mode)` | `chn:number`; `mode:number` | `number` [0:OK, 1:NG] | 设置离散时钟模式 |

### 信号参数配置

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `MIPI.SetLaneNum` / `MIPI.SetMIPILaneNum` | `(chn, laneNum)` | `chn:number`; `laneNum:number` [1/2/3/4/8] | `number` [0:OK, 1:NG] | 设置Lane数量(两者等价) |
| `MIPI.SetLinkNum` | `(chn, links)` | `chn:number`; `links:number` [1/2/4/8] | `number` [0:OK, 1:NG] | 设置Link数量发送到FPGA |
| `MIPI.RefrshRate` | `(chn, rate)` | `chn:number`; `rate:number`(Hz) | `number` [0:OK, 1:NG] | 设置刷新率 |
| `MIPI.DSIFrequence` | `(chn, freq)` | `chn:number`; `freq:number`(MHz) | `number` [0:OK, 1:NG] | 设置DSI频率 |
| `MIPI.SetColorBitWide` | `(chn, bits)` | `chn:number`; `bits:number` [6/8/10/12] | `number` [0:OK, 1:NG] | 设置颜色位宽 |
| `MIPI.SetSplitMode` | `(chn, mode)` | `chn:number`; `mode:number` [0:不分屏, 1:左右, 2:奇偶] | `number` [0:OK, 1:NG] | 设置分屏模式 |
| `MIPI.SetSyncMode` | `(chn, mode)` | `chn:number`; `mode:number` [0:Burst, 1:Pulse, 2:Event] | `number` [0:OK, 1:NG] | 设置同步模式(Video模式有效) |
| `MIPI.SetMipiMode` | `(chn, mode)` | `chn:number`; `mode:number` [0:Video, 1:CMD] | `number` [0:OK, 1:NG] | 设置MIPI模式(命令模式) |
| `MIPI.HSLP` | `(chn, mode)` | `chn:number`; `mode:number` [0:LP, 1:HS] | `number` [0:OK, 1:NG] | 设置HS/LP模式 |
| `MIPI.SetMIPIReadTimout` | `(time)` | `time:number` | `number` [0:OK, 1:NG] | 设置MIPI读取超时时间 |

### 信号控制

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `MIPI.Start` | `(chn)` | `chn:number` | `number` [0:OK, 1:NG] | 启动MIPI信号输出 |
| `MIPI.CloseSignal` | `(chn)` | `chn:number` | `number` [0:OK, 1:NG] | 关闭MIPI信号 |
| `MIPI.UlpsIn` | `(chn)` | `chn:number` | `number` [0:OK, 1:NG] | 进入ULPS低功耗状态 |
| `MIPI.UlpsOut` | `(chn)` | `chn:number` | `number` [0:OK, 1:NG] | 退出ULPS低功耗状态 |

### 其他功能

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `MIPI.TESyncSwitchPtn` | `(chn, gpioCh, enable, delay)` | `chn:number`; `gpioCh:number`; `enable:number` [0:禁用, 1:使能]; `delay:number` | `number` [0:OK, 1:NG] | TE同步切换图案 |
| `MIPI.SetRgbReverse` | `(chn, value)` | `chn:number`; `value:number` [0:正常, 1:反转] | `number` [0:OK, 1:NG] | 设置RGB反转 |
| `MIPI.OverLap` | `(chn, overlap)` | `chn:number`; `overlap:number` - 叠加像素数 | `number` [0:OK, 1:NG] | 设置叠加像素数(分屏折叠) |
| `MIPI.CH` | `(chn, channel)` | `chn:number`; `channel:number` | `number` [0:OK, 1:NG] | 设置MIPI通道 |
| `MIPI.CphyPowerOnOff` | `(chn, status)` | `chn:number`; `status:number` [0:关, 1:开] | `number` [0:OK, 1:NG] | C-PHY(SSD2832)电源开关 |
| `MIPI.CphySingalOnOff` | `(chn, status)` | `chn:number`; `status:number` [0:关, 1:开] | `number` [0:OK, 1:NG] | C-PHY信号开关 |

---

<a id="regs"></a>

## REGS - MIPI寄存器读写模块

提供MIPI D-PHY/C-PHY寄存器读写，支持DCS命令和Demura数据写入。

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `REGS.WRITE` | `(chn, dataType, param)` | `chn:number`; `dataType:number` - 数据类型; `param:table` - 写入数据 | `number` [0:OK, 1:NG] | 写MIPI寄存器(DCS命令) |
| `REGS.tWRITE` | `(chn, regAddr, writeData)` | `chn:number`; `regAddr:number` - 寄存器地址; `writeData:table` | `number` [0:OK, 1:NG] | 写面板寄存器 |
| `REGS.READ` | `(chn, regAddr, readLen)` | `chn:number`; `regAddr:number`; `readLen:number` | `table` - 读取的数据 | 读MIPI寄存器 |
| `REGS.WRITE_Demura` | `(chn, data)` | `chn:number`; `data:table` - Demura数据 | `number` [0:OK, 1:NG] | 写MIPI寄存器(Demura通道) |

---

<a id="dp"></a>

## DP - eDP信号控制模块

提供eDP信号控制，包括时序、Lane配置、链路速率、同步极性、AUX通道读写、HPD状态等。

### 初始化与信号控制

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `DP.Init` | `(chn)` | `chn:number` | `number` [0:OK, 1:NG] | 初始化DP时序参数 |
| `DP.DPSignalCtrl` | `(chn, enable)` | `chn:number`; `enable:number` [0:关, 1:开] | `number` [0:OK, 1:NG] | DP信号控制(开关) |

### Lane与速率

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `DP.SetDPLaneNum` | `(chn, laneNum)` | `chn:number`; `laneNum:number` [1/2/4/8] | `number` [0:OK, 1:NG] | 设置DP Lane数量 |
| `DP.SetLinkRate` | `(chn, rate)` | `chn:number`; `rate:number` [0:1.6G, 1:2.7G, 2:5.4G, 3:8.1G] | `number` [0:OK, 1:NG] | 设置链路速率 |
| `DP.SetFreqType` | `(chn, type)` | `chn:number`; `type:number` [0:4K, 1:8K] | `number` [0:OK, 1:NG] | 设置频率类型 |

### 时序与极性

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `DP.RefrshRate` | `(chn, rate)` | `chn:number`; `rate:number`(Hz) | `number` [0:OK, 1:NG] | 设置刷新率 |
| `DP.SetColorBitWide` | `(chn, bits)` | `chn:number`; `bits:number` [6/8/10/12] | `number` [0:OK, 1:NG] | 设置颜色位宽 |
| `DP.SetSplitMode` | `(chn, mode)` | `chn:number`; `mode:number` [0:不分屏, 1:左右, 2:奇偶] | `number` [0:OK, 1:NG] | 设置分屏模式 |
| `DP.SetSignalPolarity` | `(chn, hsync, vsync, de)` | `chn:number`; `hsync:number` [0:负, 1:正]; `vsync:number`; `de:number` | `number` [0:OK, 1:NG] | 设置信号极性 |
| `DP.SetHSyncPolarity` | `(chn, val)` | `chn:number`; `val:number` [0:负, 1:正] | `number` [0:OK, 1:NG] | 设置HSync极性 |
| `DP.SetVSyncPolarity` | `(chn, val)` | `chn:number`; `val:number` [0:负, 1:正] | `number` [0:OK, 1:NG] | 设置VSync极性 |
| `DP.SetDeSyncPolarity` | `(chn, val)` | `chn:number`; `val:number` [0:负, 1:正] | `number` [0:OK, 1:NG] | 设置DE极性 |

### 背光与训练

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `DP.SetBackLightMode` | `(chn, mode)` | `chn:number`; `mode:number` [0:Normal, 1:LED] | `number` [0:OK, 1:NG] | 设置背光模式 |
| `DP.SetPoliceMaker` | `(chn, mode)` | `chn:number`; `mode:number` [0:BTC, 1:JCDefined] | `number` [0:OK, 1:NG] | 设置PoliceMaker模式 |
| `DP.SetTrainingDelay` | `(chn, delay)` | `chn:number`; `delay:number` | `number` [0:OK, 1:NG] | 设置Training延时 |

### HPD与AUX

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `DP.GetHpdStatus` | `(chn)` | `chn:number` | `number` - HPD状态 | 获取HPD(Hot Plug Detect)状态 |
| `DP.DPAuxMIOEnable` | `(chn, enable)` | `chn:number`; `enable:number` [0:禁用, 1:使能] | `number` [0:OK, 1:NG] | 使能DP AUX MIO |
| `DP.ImproveMainBoardSignal` | `(chn, val)` | `chn:number`; `val:number` - 增强值 | `number` [0:OK, 1:NG] | 改善主板DP信号(驱动增强) |
| `DP.ImproveInterfaceBoardSignal` | `(chn, val)` | `chn:number`; `val:number` | `number` [0:OK, 1:NG] | 改善接口板DP信号(驱动增强) |

### 寄存器读写

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `DP.WriteDPReg` | `(chn, addr, value)` | `chn:number`; `addr:number`; `value:number` | `number` [0:OK, 1:NG] | 写DP IP寄存器 |
| `DP.ReadDPReg` | `(chn, addr)` | `chn:number`; `addr:number` | `number` - 寄存器值 | 读DP IP寄存器 |

### AUX通道操作

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `DP.ReadDPByAUX` | `(chn, addr, len)` | `chn:number`; `addr:number` - DPCD地址; `len:number` | `table` - 读取数据 | 通过AUX读DP |
| `DP.WriteDPByAUX` | `(chn, addr, data)` | `chn:number`; `addr:number` - DPCD地址; `data:table` | `number` [0:OK, 1:NG] | 通过AUX写DP |
| `DP.ReadDPByAUXI2C` | `(chn, devAddr, regAddr, len)` | `chn:number`; `devAddr:number`; `regAddr:number`; `len:number` | `table` - 读取数据 | 通过AUX的I2C读 |
| `DP.WriteDPByAUXI2C` | `(chn, devAddr, data)` | `chn:number`; `devAddr:number`; `data:table` | `number` [0:OK, 1:NG] | 通过AUX的I2C写 |
| `DP.WriteDPAUXByBuf` | `(chn, addr, len, data)` | `chn:number`; `addr:number`; `len:number`; `data:table` | `number` [0:OK, 1:NG] | 通过Buffer写AUX |
| `DP.ReadDPAUXI2CByBuf` | `(chn, devAddr, regAddr, len, mot)` | `chn:number`; `devAddr:number`; `regAddr:number`; `len:number`; `mot:number` - MOT标志 | `table` - 读取数据 | 通过Buffer读AUX I2C |
| `DP.WriteDPAUXI2CByBuf` | `(chn, devAddr, len, mot, data)` | `chn:number`; `devAddr:number`; `len:number`; `mot:number`; `data:table` | `number` [0:OK, 1:NG] | 通过Buffer写AUX I2C |

---

<a id="lvds"></a>

## LVDS - LVDS信号控制模块

提供LVDS信号控制，包括信号开关、时序、格式、极性、预加重、链路顺序、开短路检测等。

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `LVDS.LvdsSignalCtrl` | `(chn, enable)` | `chn:number`; `enable:number` [0:OFF, 1:ON] | `number` [0:OK, 1:NG] | LVDS信号开关控制 |
| `LVDS.SETTIMIING` | `(chn, ...)` | `chn:number`; `...` - 时序参数(ActiveH, ActiveV, HBP, HSW, HFP, VBP, VSW, VFP) | `number` [0:OK, 1:NG] | 设置LVDS FPGA时序 |
| `LVDS.SetSignalFormat` | `(chn, mode)` | `chn:number`; `mode:number` [0:VESA, 1:JEIDA] | `number` [0:OK, 1:NG] | 设置信号格式 |
| `LVDS.SetSignalPolarity` | `(chn, hsync, vsync, de)` | `chn:number`; `hsync:number` [0:负, 1:正]; `vsync:number`; `de:number` | `number` [0:OK, 1:NG] | 设置信号极性 |
| `LVDS.CheckLvdsOpenShort` | `(chn)` | `chn:number` | `number` - 检测结果 | 检测LVDS开短路 |
| `LVDS.RefrshRate` | `(chn, rate)` | `chn:number`; `rate:number`(Hz) | `number` [0:OK, 1:NG] | 设置刷新率 |
| `LVDS.SetColorBitWide` | `(chn, bits)` | `chn:number`; `bits:number` [6/8/10/12] | `number` [0:OK, 1:NG] | 设置颜色位宽 |
| `LVDS.SetLinkNum` | `(chn, links)` | `chn:number`; `links:number` [1/2/4/8] | `number` [0:OK, 1:NG] | 设置Link数量 |
| `LVDS.SetlvdsPem` | `(chn, enable)` | `chn:number`; `enable:number` [0:ON, 1:OFF] | `number` [0:OK, 1:NG] | 设置LVDS预加重(Pre-emphasis) |
| `LVDS.LvdsClkSignalCtrl` | `(chn, enable)` | `chn:number`; `enable:number` [0:OFF, 1:ON] | `number` [0:OK, 1:NG] | LVDS时钟信号控制 |
| `LVDS.LvdsSetLinkOrder` | `(chn, order)` | `chn:number`; `order:number` | `number` [0:OK, 1:NG] | 设置LVDS链路顺序 |
| `LVDS.CloseVdmaSignal` | `(chn)` | `chn:number` | `number` [0:OK, 1:NG] | 关闭LVDS VDMA信号 |
| `LVDS.WriteLvdsReg` | `(chn, addr, value)` | `chn:number`; `addr:number`; `value:number` | `number` [0:OK, 1:NG] | 写LVDS寄存器 |
| `LVDS.ReadLvdsReg` | `(chn, addr)` | `chn:number`; `addr:number` | `number` - 寄存器值 | 读LVDS寄存器 |

---

<a id="ttl"></a>

## TTL - TTL信号控制模块

提供TTL信号控制，包括信号开关、时序、初始化、位偏移、RGB顺序、相位、电压设置等。

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `TTL.TTLSignalCtrl` | `(chn, enable)` | `chn:number`; `enable:number` [0:OFF, 1:ON] | `number` [0:OK, 1:NG] | TTL信号控制(开关) |
| `TTL.SetTiming` | `(chn, ...)` | `chn:number`; `...` - 时序参数(ActiveH, ActiveV, HBP, HSW, HFP, VBP, VSW, VFP) | `number` [0:OK, 1:NG] | 设置TTL FPGA时序 |
| `TTL.InitTTLParameters` | `(chn)` | `chn:number` | `number` [0:OK, 1:NG] | 初始化TTL参数 |
| `TTL.SetTTLbitShift` | `(chn, shift)` | `chn:number`; `shift:number` | `number` [0:OK, 1:NG] | 设置TTL位偏移 |
| `TTL.SetTTLRGBOrder` | `(chn, order)` | `chn:number`; `order:number` | `number` [0:OK, 1:NG] | 设置TTL RGB顺序 |
| `TTL.SetTTLPhase` | `(chn, phase)` | `chn:number`; `phase:number` (0~360) | `number` [0:OK, 1:NG] | 设置TTL相位 |
| `TTL.TTLSignalLineEn` | `(chn, enable)` | `chn:number`; `enable:number` [0:禁用, 1:使能] | `number` [0:OK, 1:NG] | TTL信号线使能 |
| `TTL.SetSplitMode` | `(chn, mode)` | `chn:number`; `mode:number` [0:不分屏, 1:左右, 2:奇偶] | `number` [0:OK, 1:NG] | 设置分屏模式 |
| `TTL.RefrshRate` | `(chn, rate)` | `chn:number`; `rate:number`(Hz) | `number` [0:OK, 1:NG] | 设置刷新率 |
| `TTL.SetColorBitWide` | `(chn, bits)` | `chn:number`; `bits:number` [6/8/10/12] | `number` [0:OK, 1:NG] | 设置颜色位宽 |
| `TTL.SetLinkNum` | `(chn, links)` | `chn:number`; `links:number` [1/2/4/8] | `number` [0:OK, 1:NG] | 设置Link数量 |
| `TTL.SetTTLVoltage` | `(chn, vol)` | `chn:number`; `vol:number` [1500:1.5V, 2800:2.8V, 3300:3.3V] | `number` [0:OK, 1:NG] | 设置TTL电压 |
| `TTL.CloseVdmaSignal` | `(chn)` | `chn:number` | `number` [0:OK, 1:NG] | 关闭TTL VDMA信号 |
| `TTL.WriteTTLReg` | `(chn, addr, value)` | `chn:number`; `addr:number`; `value:number` | `number` [0:OK, 1:NG] | 写TTL寄存器 |
| `TTL.ReadTTLReg` | `(chn, addr)` | `chn:number`; `addr:number` | `number` - 寄存器值 | 读TTL寄存器 |

---

<a id="i2c"></a>

## I2C - I2C总线控制模块

提供I2C总线控制，包括I2C/SPI切换、电平设置、波特率、上拉、通道选择和读写。

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `I2C.I2CSPISwitch` | `(chn, mode)` | `chn:number`; `mode:number` [1:I2C, 0:SPI] | `number` [0:OK, 1:NG] | I2C/SPI切换 |
| `I2C.SetI2CLevel` | `(chn, level)` | `chn:number`; `level:number` [0:1.8V, 1:3.3V] (设置上拉后生效) | `number` [0:OK, 1:NG] | 设置I2C电平 |
| `I2C.SetI2CBps` | `(chn, bps)` | `chn:number`; `bps:number` | `number` [0:OK, 1:NG] | 设置I2C波特率 |
| `I2C.I2CPullupEn` | `(chn, enable)` | `chn:number`; `enable:number` [1:使能, 0:不使能] | `number` [0:OK, 1:NG] | 设置I2C上拉使能(主要在远端上拉) |
| `I2C.ReadI2C` | `(chn, devAddr, regLen, regAddr, readLen, readUnit)` | `chn:number`; `devAddr:number` - 设备地址; `regLen:number` - 寄存器地址长度; `regAddr:number`; `readLen:number`; `readUnit:number` | `table` - 读取数据 | I2C读取 |
| `I2C.WriteI2C` | `(chn, devAddr, addrLen, regAddr, writeLen, writeUnit, writeData)` | `chn:number`; `devAddr:number`; `addrLen:number`; `regAddr:number`; `writeLen:number`; `writeUnit:number`; `writeData:table` | `number` [0:OK, 1:NG] | I2C写入 |
| `I2C.SetI2CChannel` | `(chn, channel)` | `chn:number`; `channel:number` - E058A: [1:mipi c-phy, 2:mipi d-phy 1.5G, 3:dp]; E059A: [1:ttl, 2:d-phy 2.5G, 3:lvds, 4:dp] | `number` [0:OK, 1:NG] | 选择I2C通道 |

---

<a id="spi"></a>

## SPI - SPI总线控制模块

提供SPI总线控制，包括电平设置、通道选择、CS模式、标准SPI(3线/4线)和QSPI(6线)读写。

### 基础配置

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `SPI.SetSPICLevel` | `(chn, level)` | `chn:number`; `level:number` [0:1.8V, 1:3.3V] | `number` [0:OK, 1:NG] | 设置SPI电平(所有通道) |
| `SPI.SetSPILevel` | `(chn, level)` | `chn:number`; `level:number` [0:1.8V, 1:3.3V] | `number` [0:OK, 1:NG] | 设置SPI电平(单通道) |
| `SPI.I2CSPISwitch` | `(chn, mode)` | `chn:number`; `mode:number` [1:I2C, 0:SPI] | `number` [0:OK, 1:NG] | I2C/SPI切换 |
| `SPI.SetSPIChannel` | `(chn, channel)` | `chn:number`; `channel:number` - E058A: [1:c-phy, 2:d-phy 1.5G, 3:dp, 4:flash]; E059A: [1:ttl flash, 2:d-phy 2.5G, 3:lvds, 4:dp] | `number` [0:OK, 1:NG] | 选择SPI数据通道 |
| `SPI.SpiSetCsMode` / `SPI.SetSPICsMode` | `(chn, mode)` | `chn:number`; `mode:number` - CS模式 | `number` [0:OK, 1:NG] | 设置SPI CS模式(两者等价) |
| `SPI.SetI2cPullUp` / `SPI.SPIPullupEn` | `(chn, enable)` | `chn:number`; `enable:number` [1:使能, 0:不使能] | `number` [0:OK, 1:NG] | 设置I2C上拉(两者等价) |
| `SPI.SpiConfig` / `SPI.ConfigSpi` | `(chn, ...)` | `chn:number`; `...` - 配置参数 | `number` [0:OK, 1:NG] | SPI配置(两者等价) |
| `SPI.setSpiMode` | `(chn, mode)` | `chn:number`; `mode:number` | `number` [0:OK, 1:NG] | 设置SPI模式 |

### PL-SPI 读写

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `SPI.ReadSPI` | `(chn, ...)` | `chn:number`; `...` - 读取参数 | `table` - 读取数据 | PL-SPI读取 |
| `SPI.WriteSPI` | `(chn, ...)` | `chn:number`; `...` - 写入参数 | `number` [0:OK, 1:NG] | PL-SPI写入 |

### 标准SPI (3线/4线)

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `SPI.Read` | `(chn, ...)` | `chn:number`; `...` - 读取参数 | `table` - 读取数据 | 标准SPI读取(3线/4线) |
| `SPI.Write` | `(chn, ...)` | `chn:number`; `...` - 写入参数 | `number` [0:OK, 1:NG] | 标准SPI写入(3线/4线) |

### QSPI (6线)

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `SPI.FastReadQuadOutput` | `(chn, ...)` | `chn:number`; `...` | `table` - 读取数据 | QSPI快速读取(四输出) |
| `SPI.FastReadQuadIO` | `(chn, ...)` | `chn:number`; `...` | `table` - 读取数据 | QSPI快速读取(四输入输出) |
| `SPI.QuadInputPageProgram` | `(chn, ...)` | `chn:number`; `...` | `number` [0:OK, 1:NG] | QSPI四线页编程 |
| `SPI.ReadManufacturerQuadIO` | `(chn, ...)` | `chn:number`; `...` | `table` - 读取数据 | QSPI读取制造商ID |
| `SPI.QspiFlashWriteByBIN` | `(chn, ...)` | `chn:number`; `...` | `number` [0:OK, 1:NG] | QSPI按BIN文件写入Flash |

---

<a id="time"></a>

## TIME - 延时控制模块

提供延时控制功能。

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `TIME.Delay` / `TIME.DELAY` | `(delayTime)` | `delayTime:number` - 延时时间(ms) | `number` [0:OK, 1:NG] | 延时指定毫秒数(两者等价) |
| `TIME.LockDelay` | `(lockTimeMs)` | `lockTimeMs:number` - 锁定时间(ms) | `number` [0:OK, 1:NG] | 锁定延时(延时期间阻止队列消息处理) |

---

<a id="optical"></a>

## OPTICAL - 光学探头控制模块

提供光学探头控制，包括路径设置、初始化、指令发送、亮度读取、频率同步、闪烁测量等。

| 接口 | 签名 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `OPTICAL.SetProbePath` | `(path)` | `path:string` - 路径 | `number` [0:OK, 1:NG] | 设置探头路径 |
| `OPTICAL.Init` | `()` | 无 | `number` [0:OK, 1:NG] | 初始化光学探头 |
| `OPTICAL.SendCmd` | `(cmd)` | `cmd:number/string` - 指令 | `number` [0:OK, 1:NG] | 发送光学探头指令 |
| `OPTICAL.GetLv` | `()` | 无 | `table` - 亮度数据(x,y,Lv) | 读取亮度值 |
| `OPTICAL.SetSpeed` | `(speed)` | `speed:number` | `number` [0:OK, 1:NG] | 设置探头速度 |
| `OPTICAL.SetCH` | `(ch)` | `ch:number` | `number` [0:OK, 1:NG] | 设置探头通道 |
| `OPTICAL.SetDisplayMode` | `(mode)` | `mode:number` | `number` [0:OK, 1:NG] | 设置显示模式 |
| `OPTICAL.SetEffectiveData` | `(data)` | `data:number` | `number` [0:OK, 1:NG] | 设置有效数据 |
| `OPTICAL.SetSyncMode` | `(mode)` | `mode:number` | `number` [0:OK, 1:NG] | 设置同步模式 |
| `OPTICAL.SyncFreqBySelf` | `()` | 无 | `number` [0:OK, 1:NG] | 自动同步频率 |
| `OPTICAL.SyncFreqByPE` | `()` | 无 | `number` [0:OK, 1:NG] | 通过PE同步频率 |
| `OPTICAL.SetFlickerMode` | `(mode)` | `mode:number` | `number` [0:OK, 1:NG] | 设置闪烁测量模式 |
| `OPTICAL.GetFlicker` | `()` | 无 | `number` - 闪烁值 | 读取闪烁值 |
| `OPTICAL.ReConnect` | `()` | 无 | `number` [0:OK, 1:NG] | 重新连接光学探头 |

---

## 典型使用流程

### LVDS 屏幕测试流程

```lua
-- 1. 初始化系统
SYS.InitMainCfg()
SYS.InitMainSysCfg()

-- 2. 设置信号类型为LVDS
SYS.SetSignalType(0)  -- 0:LVDS

-- 3. 初始化电源
PWR.InitPower()
PWR.SetPwrOnOff(1, 0x0001, 1)  -- 开启VDD
TIME.Delay(100)

-- 4. 开启LVDS信号
LVDS.LvdsSignalCtrl(1, 1)  -- ON
LVDS.SetColorBitWide(1, 8)

-- 5. 切换图案
SYS.SwitchPtn(1, "white")
MSG.Debug("LVDS test started")
```

### MIPI 屏幕测试流程

```lua
-- 1. 初始化
SYS.InitMainCfg()
SYS.InitMainSysCfg()

-- 2. 设置MIPI模式
SYS.SetSignalType(2)  -- 2:MIPI
MIPI.SetMipiPhyMode(0)  -- 0:D-PHY

-- 3. 配置MIPI参数
MIPI.SetLaneNum(1, 4)
MIPI.SetColorBitWide(1, 8)
MIPI.SetMipiMode(1, 0)  -- 0:Video模式

-- 4. 初始化并启动
MIPI.Init(1)
MIPI.Start(1)

-- 5. 写寄存器
REGS.tWRITE(1, 0x11, {0x00})  -- 退出Sleep
TIME.Delay(120)
REGS.tWRITE(1, 0x29, {0x00})  -- 开启显示
```

### eDP 屏幕测试流程

```lua
-- 1. 初始化
SYS.InitMainCfg()
SYS.InitMainSysCfg()
SYS.SetSignalType(3)  -- 3:eDP

-- 2. 配置DP参数
DP.Init(1)
DP.SetDPLaneNum(1, 4)
DP.SetLinkRate(1, 2)  -- 2:5.4G
DP.SetColorBitWide(1, 8)

-- 3. 开启DP信号
DP.DPSignalCtrl(1, 1)

-- 4. 通过AUX读取EDID
local edid = DP.ReadDPByAUX(1, 0x50, 16)
MSG.Debug("EDID: %s", ADDP.Array2Hexstr(edid))
```
