--/******************** JC ***********************************************
--* File Name          : Signal.lua
--* Author             : Wuhan Jingce Electronic Group Co., Ltd.
--* Version            : V0.0.1
--* Date               : 2019-12-27
--* Description        :  Signal Interface
--*********************************************************************/
LP = 0;
HS = 1;
ON = 1;
OFF = 0;
gStepBack = 1

---set mipi transmission : LP/HS
function HSLP(val)
    MipiSetHsOrLp(val);
end

--MIPI 20902 on/off
function Start(val)
    SetMIPIOutEn(val);
end

--DP Signal Ctrl val: ON/OFF
function DPSignalCtrl(channel,val)

    if  val == 1 then
        DpMainSignalCtl(channel, 60);
        DpSlaveSignalCtl(channel, 60);
    else 
        closeVdmaSignalFunc();
        DpMainSignalCtl(channel, 0);
        DpSlaveSignalCtl(channel, 0);
    end

end

---Lvds Signal Ctrl
function LvdsSignalCtrl(val)
    LvdsSignalCtrl(val);
end
-- ENTRY ULPS UlpsIn
function UlpsIn()
    REGS.WRITE(0,0x5,0x28,0x00)	
    TIME.Delay(10);
    REGS.WRITE(0,0x5,0x10,0x00)
    TIME.Delay(10);
    MipiUlpsIN()
end

--OUT ULPS
function UlpsOut()
    MipiUlpsIOut() 
    REGS.WRITE(0,0x5,0x11,0x10)	
    TIME.Delay(10);
    REGS.WRITE(0,0x5,0x29,0x00) 
end


--close all signal functions
function InitFunDefault()
    ClearColorBlock();   ---Clear Color Block
    CloseCrossCursor();  ---Close Cross Cursor
    ClosePtnMove();      ---Close Ptn Move
    CloseShowFont();     ---Close Show Font
    TIME.Delay(120);
    CloseYcbcr();        --Close Ycbcr
    CloseRgb()
end

function ResetMIPISignal()
	ResetMIPIChannel();
	SetMIPILinkNum(gLink);                      --设置FPGA的link数
	SetMIPIBpc(gBit);                  --设置bit数
	--SYS.SetSignalType(gSignalType);              --信号类型
	InitMIPIParameters(gActiveH,gActiveV,gHBP,gHSW,gHFP,gVBP,gVSW,gVFP);---模组porch
	SetFreshRate(gFrameRate);                 --刷新率
	SetDsiFreqMipiIp(gMIPI_DSI);                     --DIS速率
	SetMIPILaneNum(gMIPI_LANE);             --lane数
	SetMipiMode(gMIPI_TYPE)
	--MIPI.SetMipiPhyMode(gMIPI_PhyMode);    ----phy mode -- gMIPI_PhyMode
end

--Control exceptions caused by failback
function Step2ToStep1()

    if gStepBack == 1 then
        if GetDeviceOnOffStatus() == "on" then
            MSG.Println("At this time, it is already powered on!","green")
            setstepno(2);
        else
            F_STEP_01()
        end
    elseif gStepBack == 2 then
        F_STEP_RESET()
        TIME.Delay(300);
        F_STEP_01()

    elseif gStepBack == 3 then
        F_STEP_01()

    end
    
end

function DPInit(backLightMode,PoliceMaker,AUXLevel,HPDTrainingDelay,LaneCnt,UseMaxLink,LinkRate,HSDSyncPolarity,VSDSyncPolarity,DEPolarity)
    
    local TrainingMode = 0;
    local EQLevel = 0;
    local VODLevel = 0;
    
    InitDPParameters(backLightMode,PoliceMaker,AUXLevel,HPDTrainingDelay,LaneCnt,TrainingMode,UseMaxLink,LinkRate,EQLevel,VODLevel,HSDSyncPolarity,VSDSyncPolarity,DEPolarity)
    
end



function reportagingstatus()

    local chnRes = {}
    local jsonAgingInfo = ""
    local res = "OK" -- "NG","STOP"
    local agingStatusInfo = {
        cmd			= "",
        pg				= {},      -- PG ID, exp:[1,2,3];[255]all PG
        channel		= {},    -- channel ID, exp:[1,2,3];[255]all channel
        type			= "",  -- Aging type : "Aging","TSS"
        ptnname		= "",       -- ptn name
        agingstatus	= "",  -- "pause","run","stop"
        result			= "",        -- run result
        errlog			= "",
        totaltime	= "",        -- total time
        remaintime	= "",        -- remain time
        chnres		= {},
    }

    --MSG.Println("SendAgingInfo")
    --MSG.Debug("gAgingStatus -- %d", gAgingStatus)
    if gAgingStatus == AGING_RUN then
        gAgingStatusInfo.KeyStatus = KEY_RESUME
    elseif gAgingStatus == AGING_STOP then
        gAgingStatusInfo.KeyStatus = KEY_STOP
    elseif gAgingStatus == AGING_PAUSE then
        gAgingStatusInfo.KeyStatus = KEY_PAUSE
    else
        gAgingStatusInfo.KeyStatus = KEY_STOP
    end


    for i = 1, #gChannelInfo do
        if gChannelInfo[i].result == OK then
            res =  "OK" 
        elseif gChannelInfo[i].result == NG then
            res =  "NG" 
        elseif gChannelInfo[i].result == STOP then
            res =  "STOP" 
        else
        end
        chnRes[i] = res
    end

    if gAgingStatusInfo.KeyStatus == KEY_STOP then
        gAgingStatusInfo.chnRes = {"STOP" ,"STOP" ,"STOP" ,"STOP" ,"STOP"}
    else
        gAgingStatusInfo.chnRes = chnRes
    end

    --gAgingStatusInfo.chnRes = {"OK" ,"OK" ,"NG" ,"NG" ,"OK"}
    -- SendAgingInfo data 
    agingStatusInfo.cmd				= "reportagingstatus"
    agingStatusInfo.pg				= gAgingStatusInfo.pg
    agingStatusInfo.channel		= gAgingStatusInfo.channel
    agingStatusInfo.type			= gAgingStatusInfo.runType
    agingStatusInfo.agingstatus	= gAgingStatusInfo.KeyStatus
    agingStatusInfo.result			= gAgingStatusInfo.result
    agingStatusInfo.errlog			= gAgingStatusInfo.errLog
    agingStatusInfo.totaltime		= gAgingStatusInfo.totalTime
    agingStatusInfo.remaintime	= math.floor(gAgingStatusInfo.remainTime)
    agingStatusInfo.chnres			= gAgingStatusInfo.chnRes
    agingStatusInfo.ptnname  = gAgingStatusInfo.ptnName

    jsonAgingInfo = cjson.encode(agingStatusInfo)
    --MSG.Debug(jsonAgingInfo)

    return jsonAgingInfo 
end


function aging(cmdbuf)

    local UISInfo = {}
    UISInfo = cjson.decode(cmdbuf[1])

    if InitTimes == 0 then
        gAgingTestDuration = UISInfo["totaltime"]
        Init()
        gInitTimes = gInitTimes + 1
    end
    
    gAgingStatusInfo.KeyStatus = UISInfo["mode"]
    gAgingStatusInfo.channel = gChannelSet
    gAgingStatusInfo.pg = {}
    gAgingStatusInfo.pg[1] = SYS.GetPgId()

    gAgingTestDuration = UISInfo["totaltime"]
    MSG.Println("set PG %d key Status : %s", gAgingStatusInfo.pg[1], UISInfo["mode"])
    if UISInfo["mode"] == "start" then
        gAgingStatus = AGING_RUN
        SendAgingInfo()
		-- enter AgingTest
        StartAging("AgingTest")

    elseif UISInfo["mode"] == "resume" then

        gAgingStatus = AGING_RUN
        SendAgingInfo()
    elseif UISInfo["mode"] == "stop" then
        gAgingStatus = AGING_STOP
    elseif UISInfo["mode"] == "pause" then
        gAgingStatus = AGING_PAUSE
    end

end


--socket 192.168.10.1:12590 UDP
--{"cmd":"switchpattern","pg":[[1],"channel":[[1],"patternname":"SS.a1"}
function switchpattern(cfgBuf)

    local cjson = require "cjson"
    local resStr = {
        result = "NG", -- "OK"
    }
    local ptnname = ""
    
    local thirdCfg = cjson.decode(cfgBuf[1])
    INFO("show ptn : %s", thirdCfg.patternname)
    local ret = SYS.SwitchPtn(thirdCfg.patternname)

    if ret == "OK" then
        resStr.result = "OK"
    else
        resStr.result = "NG"
    end

    local resBuf = cjson.encode(resStr)
    return resBuf
end

--socket 192.168.10.1:12590 UDP
--{"cmd":"commonluafunc","pg":[[1],"param":[["TPCHECK", "200"]}
function commonluafunc(cfgBuf)
    
    local cjson = require "cjson"
    local resStr = {
        result = "NG", -- "OK"
    }
    
    local thirdCfg = cjson.decode(cfgBuf[1])
    local ret, res = F_THIRD_CMD_PROCESS(thirdCfg)
    
    if ret == "OK" then
        resStr.result = "OK"
    else
        resStr.result = "NG"
    end
    --resStr["reslog"] = {"test third func",2,7}
    resStr["reslog"] = res

    local resBuf = cjson.encode(resStr)
    return resBuf
end

function writeIIC(I2CId, DevAddr, RegLen, RegAddr, WriteLen, WriteUnit, WriteData)
	local ret = 0;
	
	ret = WriteI2C(I2CId, DevAddr, RegLen, RegAddr, WriteLen, WriteUnit, WriteData)
	if ret ~= WriteLen then --统一返回结果。0：OK，1：NG
		ret = 1;
	end
    return ret;
end

--用于demura 烧录bin数据的接口
--state 传在HS或LP下写
--fileToOpen 文件路径
--Dsctype 写寄存器的方式：0x39，0x29.....
--mode 是0x2c 0x3c 0x4c 0x5c....
--StarAdd 从bin文件中哪里地方开始取数据
--EndAdd  从bin文件中哪里地方结束取数据
--len  每个包的大小
function DemuraWriteData(state,fileToOpen, Dsctype, mode,StarAdd, EndAdd, len)

      SetMipiModeHsOrLp(state);---设置HS/LP状态

    return DemuraWrite(fileToOpen, Dsctype, mode,StarAdd, EndAdd, len);
end