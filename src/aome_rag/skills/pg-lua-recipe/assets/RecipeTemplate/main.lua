require 'ImageCfg'
require 'PowerCfg'
require 'TimingCfg'
require 'PScript'
require 'PowerOn'


--**********************************************
--* Function Name  : PG_INIT
--* Description    : Init
--* Input          : nil
--* Return         : nil
--**********************************************
function PG_INIT()

	MIPI.SetLinkNum(gLink);                    
    MIPI.SetColorBitWide(gBit);              
    SYS.SetSignalType(gSignalType);            
    MIPI.Init(gActiveH, gActiveV, gHBP, gHSW, gHFP, gVBP, gVSW, gVFP);---porch
    MIPI.RefrshRate(gFrameRate);            
    MIPI.DSIFrequence(gMIPI_DSI);               
    MIPI.SetMIPILaneNum(gMIPI_LANE);
    PWR.InitPower();                           
    SYS.InitFunDefault()

end

--**********************************************
--* Function Name : F_STEP_RESET
--* Description : power and Init pg
--* Input : nil
--* Return : nil
--**********************************************

function F_STEP_RESET()
 F_POWER_OFF();
end

--**********************************************
--* Function Name : F_STEP_01()
--* Description : step 01
--* Input : nil
--* Return : nil
--**********************************************
function F_STEP_01()
 F_POWER_ON();
 StepFunction(1);
end

--**********************************************
--* Function Name : F_STEP_02()
--* Description : step 02
--* Input : nil
--* Return : nil
--**********************************************
function F_STEP_02()
 StepFunction(2);
end

--**********************************************
--* Function Name : F_STEP_03()
--* Description : step 03
--* Input : nil
--* Return : nil
--**********************************************
function F_STEP_03()
 StepFunction(3);
end

