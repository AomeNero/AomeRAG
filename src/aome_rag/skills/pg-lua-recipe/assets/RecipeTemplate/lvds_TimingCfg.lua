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
