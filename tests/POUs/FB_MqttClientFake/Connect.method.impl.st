uiConnectCalls := uiConnectCalls + 1;
stLastCfg := stCfg;
IF xConnectAccepts THEN
    xConnectRequested := TRUE;
    Connect := TRUE;
END_IF
