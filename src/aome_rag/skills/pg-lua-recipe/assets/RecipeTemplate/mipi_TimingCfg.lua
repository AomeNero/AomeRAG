--/********************************************************************************
--**
--**Created by: Recipe editor version 1.0.0.1
--**
--**WARNING! All changes made in this file will be lost when you re edit!
--/********************************************************************************

-------------- porch -------------------------------------------
gActiveH = 0	-- Horizontal Active Period
gActiveV = 0	-- Vertical Active Period
gHBP = 0	-- Horizontal Back Porch
gHSW = 0	-- Horizontal Sync Active(HSYNC)
gHFP = 0	-- Horizontal Front Porch
gVBP = 0	-- Vertical Back Porch
gVSW = 0	-- Vertical Sync Active Period(VSYNC)
gVFP = 0	-- Vertical Front Porch
gFrameRate = 60	-- Vertical Freq(Hz)
----------------------------------------------------------------

-------------- MIPI -------------------------------------------
gSignalType = 2 -- [0:lvds, 1:ttl, 2:mipi, 3:dp, 4:spi]
gLink = 2	--Link[1:1Link, 2:2Link, 4:4Link, 8:8Link]
gBit = 8	--Bit[6:6Bit, 8:8Bit, 10:10Bit, 12:12Bit]
gMIPI_LANE = 4	--[1: 1Lane, 2: 2Lane, 3: 3Lane, 4: 4Lane, 8: 8Lane]
gMIPI_TYPE = 1	--[0:Video, 1:CMD]
gMIPI_MODE = 0	--[0:Pulse, 1:Event, 2:Burst] Video mode is valid
gMIPI_DSI = 1000	--MHz(1-10000MHz)
gMIPI_SplitMode = 0	--[0:noSpilt, 1:Right-Left, 2:Odd-Even]
gMIPI_ContinuousMode = 0	--[0:Non-continuous, 1:continuous]
gMIPI_Phy_Mode = 1	--[0:Dphy-MC, 1:Dphy-SSD, 2:Cphy_EXT, 3:Cphy]

----------------------------------------------------------------

-------------- EDP -------------------------------------------
gSignalType = 3 -- [0:lvds, 1:ttl, 2:mipi, 3:dp, 4:spi]
gSplitMode = 0	
gbackLightMode = 0	
gPoliceMaker = 0	
gAUXLevelHPDTrainingDelay = 0	
gTrainingMode = 0	
gUseMaxLink = 0	
gEQLevel = 0	
gVODLevel = 0	
gEDP_TYPE = 0	--lane
gEDP_H_syncPolarity = 0	
gEDP_V_syncPolarity = 0	
gEDP_DE_syncPolarity = 0	
gEDP_LaneCount = 0	-- 8.1G edp
gEDP_LinkRate = 0	-- 8.1G edp
gMIPI_LANE = 0	--lane
gBit = 0	--bit

----------------------------------------------------------------

-------------- LVDS -------------------------------------------
gSignalType = 0 -- [0:lvds, 1:ttl, 2:mipi, 3:dp, 4:spi]
gLANE = 0	--lane
gBIT = 0	--bit
gLVDS_TYPE = 0	
gLVDS_H_syncPolarity = 0	
gLVDS_V_syncPolarity = 0	
gLVDS_DE_syncPolarity = 0	
gLVDS_SplitMode = 0	
gLVDS_LINKORDER = ParseLineOrderStr("1234")	--lane

----------------------------------------------------------------