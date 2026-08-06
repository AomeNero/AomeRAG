--/******************** JC ***********************************************
--* File Name           : PowerOn.lua
--* Author              : Wuhan Jingce Electronic Group Co., Ltd.
--* Version             : V0.0.1
--* Date                : 2020-12-29
--* Model               : RM692C9 
--* Description         : Power on process
--*********************************************************************/

--**********************************************
--* Function Name  : RST
--* Description    : Init
--* Input          : nil
--* Return         : nil
--**********************************************
function RST()
	-- [0:1.8V, 13.3V]
    GPIO.SetGpioOutVol(1, 0);   
    GPIO.MIPISET1(1);   
    TIME.Delay(10);
    GPIO.MIPISET1(0);   
    TIME.Delay(10);
    GPIO.MIPISET1(1);   
end

--**********************************************
--* Function Name  : F_POWER_ON
--* Description    : power on VDD/VDDIO
--* Input          : nil
--* Return         : nil
--**********************************************
function F_POWER_ON()
    
    local Ret = 0
    local chn = 1
    MSG.Println("F_POWER_ON ...")

    PWR.SetPwrOnOff(chn, POWER_TYPE_TPVDD, ON);
    TIME.Delay(10);
    PWR.SetPwrOnOff(chn, POWER_TYPE_VDDIO, ON);
    TIME.Delay(10);
    PWR.SetPwrOnOff(chn, POWER_TYPE_VDD, ON);
    TIME.Delay(10);

    
    MIPI.ResetMIPIIP();	
    MIPI.SetMipiMode(gMIPI_TYPE); 	
    TIME.Delay(20);
    
    -- reset LCM_RST
    RST()
    -- Signal ready
    TIME.Delay(20);
    MIPI.Start(ON);
    TIME.Delay(20);
    
	-- Init code
    InitCode(chn)
	
    -- R11
    REGS.WRITE(chn, 0x05, 0x11)
    TIME.Delay(5);
    PWR.SetPwrOnOff(chn, POWER_TYPE_VBL, ON);
	TIME.Delay(120);
    PWR.SetPwrOnOff(chn, POWER_TYPE_ELVDD, ON);
    TIME.Delay(10);
    PWR.SetPwrOnOff(chn, POWER_TYPE_ELVSS, ON);
    TIME.Delay(10);
    -- R29
    REGS.WRITE(chn, 0x05, 0x29) ---Sleep,out

    MIPI.HSLP(HS)

    MSG.Println("F_POWER_ON ... end")

end

--**********************************************
--* Function Name  : F_POWER_ON
--* Description    : power on VDD/VDDIO
--* Input          : nil
--* Return         : nil
--**********************************************
function F_POWER_OFF()
    
    local chn = 1
    
    MSG.Println("F_POWER_OFF ... start")
    
    TIME.Delay(10);
    PWR.SetPwrOnOff(chn, POWER_TYPE_ELVSS, OFF);
    TIME.Delay(5);
    PWR.SetPwrOnOff(chn, POWER_TYPE_ELVDD, OFF);
    TIME.Delay(10);
    REGS.WRITE(chn, 0x05, 0x28)

    TIME.Delay(130);
    PWR.SetPwrOnOff(chn, POWER_TYPE_VBL, OFF);
    TIME.Delay(20);
    
    REGS.WRITE(chn, 0x05, 0x10)
    TIME.Delay(5);

    GPIO.MIPISET1(0)
    --MIPI.SIGNALCTRL(OFF);

    TIME.Delay(30);
    PWR.SetPwrOnOff(chn, POWER_TYPE_VGL, OFF);
    TIME.Delay(10);
    PWR.SetPwrOnOff(chn, POWER_TYPE_VDD, OFF);
    TIME.Delay(10);
    PWR.SetPwrOnOff(chn, POWER_TYPE_VDDIO, OFF);
    TIME.Delay(10);
    PWR.SetPwrOnOff(chn, POWER_TYPE_TPVDD, OFF);
    TIME.Delay(10);
    PWR.SetPwrOnOff(chn, POWER_TYPE_TPVDDIO, OFF);
    SYS.InitFunDefault()
    
    MSG.Println("F_POWER_OFF ... end")

end

--**********************************************
--* Function Name  : InitCode
--* Description    : InitCode
--* Input          : nil
--* Return         : nil
--**********************************************
function InitCode(chn)
    
    TIME.Delay(100)
	REGS.WRITE(chn, 0x39, 0xFE, 0x40)
	REGS.WRITE(chn, 0x39, 0x90, 0x00)
	REGS.WRITE(chn, 0x39, 0x91, 0x0B)
	REGS.WRITE(chn, 0x39, 0x95, 0x00)
	REGS.WRITE(chn, 0x39, 0x9F, 0x00)
	REGS.WRITE(chn, 0x39, 0xA0, 0x00)
	REGS.WRITE(chn, 0x39, 0xFE, 0x40)
	REGS.WRITE(chn, 0x39, 0x85, 0x17)
	REGS.WRITE(chn, 0x39, 0xFE, 0x90)
	REGS.WRITE(chn, 0x39, 0x16, 0xB7)
	
	-- Demura OFF
	REGS.WRITE(chn, 0x39, 0xFE, 0x22)
	REGS.WRITE(chn, 0x39, 0x77, 0x02)
	
	REGS.WRITE(chn, 0x39, 0xFE, 0x40)
	REGS.WRITE(chn, 0x39, 0x9A, 0x00)
	
	REGS.WRITE(chn, 0x39, 0xFE, 0x00)
	REGS.WRITE(chn, 0x39, 0xC2, 0x08)
	REGS.WRITE(chn, 0x39, 0x35, 0x00)
	REGS.WRITE(chn, 0x39, 0x51, 0x07, 0xFF)
	

end