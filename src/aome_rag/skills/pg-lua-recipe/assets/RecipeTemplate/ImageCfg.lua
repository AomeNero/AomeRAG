--/********************************************************************************
--**
--**Created by: Recipe editor version 1.0.0.1
--**
--**WARNING! All changes made in this file will be lost when you re edit!
--/********************************************************************************

-------------- Function -------------------------------------------
----------------------------------------------------------------

-------------- ImageTable -------------------------------------------
----- image name, before image function, after image function ----
ImageTable = {
    {'1.a1', '', ''},
    {'Checkerboard.a1', '', ''},
    {'CHESST50_MLH.a1', '', ''}
}
----------------------------------------------------------------

-------------- PatternTable -------------------------------------------
function GetPatterntTable()
    local tempTable = {};

    for k, v in pairs(ImageTable) do
        tempTable[k] = v[1]
    end
    return tempTable
end

PatternTable = GetPatterntTable();
----------------------------------------------------------------

function StepFunction(step)
    if ImageTable[step][2] ~= '' and _G[ImageTable[step][2]] ~= nil then
	       _G[ImageTable[step][2]]();
	   end
	   SYS.SwitchPtn(ImageTable[step][1])
	   if ImageTable[step][3] ~= ''  and _G[ImageTable[step][3]] ~= nil then
		   _G[ImageTable[step][3]]();
	   end
end

