ApplyCommand := TRUE;
CASE diRule OF
    1:  // P101 SetAuto
        GVL_Hmi.stP101Cmd.stCommon.xSetAuto := TRUE;
    2:  // P101 SetManual
        GVL_Hmi.stP101Cmd.stCommon.xSetManual := TRUE;
    3:  // P101 Start
        GVL_Hmi.stP101Cmd.xStart := TRUE;
    4:  // P101 Stop
        GVL_Hmi.stP101Cmd.xStop := TRUE;
    5:  // P101 SpeedSp
        GVL_Hmi.stP101Cmd.rSpeedSp_pct := rValue;
    6:  // P101 Ack
        GVL_Hmi.stP101Cmd.stCommon.xAck := TRUE;
    7:  // P101 Reset
        GVL_Hmi.stP101Cmd.stCommon.xReset := TRUE;
    8:  // P102 SetAuto
        GVL_Hmi.stP102Cmd.stCommon.xSetAuto := TRUE;
    9:  // P102 SetManual
        GVL_Hmi.stP102Cmd.stCommon.xSetManual := TRUE;
    10:  // P102 Start
        GVL_Hmi.stP102Cmd.xStart := TRUE;
    11:  // P102 Stop
        GVL_Hmi.stP102Cmd.xStop := TRUE;
    12:  // P102 SpeedSp
        GVL_Hmi.stP102Cmd.rSpeedSp_pct := rValue;
    13:  // P102 Ack
        GVL_Hmi.stP102Cmd.stCommon.xAck := TRUE;
    14:  // P102 Reset
        GVL_Hmi.stP102Cmd.stCommon.xReset := TRUE;
    15:  // P103 SetAuto
        GVL_Hmi.stP103Cmd.stCommon.xSetAuto := TRUE;
    16:  // P103 SetManual
        GVL_Hmi.stP103Cmd.stCommon.xSetManual := TRUE;
    17:  // P103 Start
        GVL_Hmi.stP103Cmd.xStart := TRUE;
    18:  // P103 Stop
        GVL_Hmi.stP103Cmd.xStop := TRUE;
    19:  // P103 SpeedSp
        GVL_Hmi.stP103Cmd.rSpeedSp_pct := rValue;
    20:  // P103 Ack
        GVL_Hmi.stP103Cmd.stCommon.xAck := TRUE;
    21:  // P103 Reset
        GVL_Hmi.stP103Cmd.stCommon.xReset := TRUE;
    22:  // V1 SetAuto
        GVL_Hmi.stV1Cmd.stCommon.xSetAuto := TRUE;
    23:  // V1 SetManual
        GVL_Hmi.stV1Cmd.stCommon.xSetManual := TRUE;
    24:  // V1 Start
        GVL_Hmi.stV1Cmd.xStart := TRUE;
    25:  // V1 Stop
        GVL_Hmi.stV1Cmd.xStop := TRUE;
    26:  // V1 Ack
        GVL_Hmi.stV1Cmd.stCommon.xAck := TRUE;
    27:  // V1 Reset
        GVL_Hmi.stV1Cmd.stCommon.xReset := TRUE;
    28:  // LT101 Ack
        GVL_Hmi.stLT101Cmd.stCommon.xAck := TRUE;
    29:  // LT101 Reset
        GVL_Hmi.stLT101Cmd.stCommon.xReset := TRUE;
    30:  // LS102 Ack
        GVL_Hmi.stLS102Cmd.stCommon.xAck := TRUE;
    31:  // LS102 Reset
        GVL_Hmi.stLS102Cmd.stCommon.xReset := TRUE;
    32:  // LS103 Ack
        GVL_Hmi.stLS103Cmd.stCommon.xAck := TRUE;
    33:  // LS103 Reset
        GVL_Hmi.stLS103Cmd.stCommon.xReset := TRUE;
    34:  // IT111 Ack
        GVL_Hmi.stIT111Cmd.stCommon.xAck := TRUE;
    35:  // IT111 Reset
        GVL_Hmi.stIT111Cmd.stCommon.xReset := TRUE;
    36:  // TS112 Ack
        GVL_Hmi.stTS112Cmd.stCommon.xAck := TRUE;
    37:  // TS112 Reset
        GVL_Hmi.stTS112Cmd.stCommon.xReset := TRUE;
    38:  // MS113 Ack
        GVL_Hmi.stMS113Cmd.stCommon.xAck := TRUE;
    39:  // MS113 Reset
        GVL_Hmi.stMS113Cmd.stCommon.xReset := TRUE;
    40:  // IT121 Ack
        GVL_Hmi.stIT121Cmd.stCommon.xAck := TRUE;
    41:  // IT121 Reset
        GVL_Hmi.stIT121Cmd.stCommon.xReset := TRUE;
    42:  // TS122 Ack
        GVL_Hmi.stTS122Cmd.stCommon.xAck := TRUE;
    43:  // TS122 Reset
        GVL_Hmi.stTS122Cmd.stCommon.xReset := TRUE;
    44:  // MS123 Ack
        GVL_Hmi.stMS123Cmd.stCommon.xAck := TRUE;
    45:  // MS123 Reset
        GVL_Hmi.stMS123Cmd.stCommon.xReset := TRUE;
    46:  // IT131 Ack
        GVL_Hmi.stIT131Cmd.stCommon.xAck := TRUE;
    47:  // IT131 Reset
        GVL_Hmi.stIT131Cmd.stCommon.xReset := TRUE;
    48:  // TS132 Ack
        GVL_Hmi.stTS132Cmd.stCommon.xAck := TRUE;
    49:  // TS132 Reset
        GVL_Hmi.stTS132Cmd.stCommon.xReset := TRUE;
    50:  // MS133 Ack
        GVL_Hmi.stMS133Cmd.stCommon.xAck := TRUE;
    51:  // MS133 Reset
        GVL_Hmi.stMS133Cmd.stCommon.xReset := TRUE;
    52:  // PT201 Ack
        GVL_Hmi.stPT201Cmd.stCommon.xAck := TRUE;
    53:  // PT201 Reset
        GVL_Hmi.stPT201Cmd.stCommon.xReset := TRUE;
    54:  // FT202 Ack
        GVL_Hmi.stFT202Cmd.stCommon.xAck := TRUE;
    55:  // FT202 Reset
        GVL_Hmi.stFT202Cmd.stCommon.xReset := TRUE;
    56:  // LS203 Ack
        GVL_Hmi.stLS203Cmd.stCommon.xAck := TRUE;
    57:  // LS203 Reset
        GVL_Hmi.stLS203Cmd.stCommon.xReset := TRUE;
    58:  // ES301 Ack
        GVL_Hmi.stES301Cmd.stCommon.xAck := TRUE;
    59:  // ES301 Reset
        GVL_Hmi.stES301Cmd.stCommon.xReset := TRUE;
    60:  // YS302 Ack
        GVL_Hmi.stYS302Cmd.stCommon.xAck := TRUE;
    61:  // YS302 Reset
        GVL_Hmi.stYS302Cmd.stCommon.xReset := TRUE;
    62:  // YS303 Ack
        GVL_Hmi.stYS303Cmd.stCommon.xAck := TRUE;
    63:  // YS303 Reset
        GVL_Hmi.stYS303Cmd.stCommon.xReset := TRUE;
    64:  // AT401 Ack
        GVL_Hmi.stAT401Cmd.stCommon.xAck := TRUE;
    65:  // AT401 Reset
        GVL_Hmi.stAT401Cmd.stCommon.xReset := TRUE;
    66:  // AT402 Ack
        GVL_Hmi.stAT402Cmd.stCommon.xAck := TRUE;
    67:  // AT402 Reset
        GVL_Hmi.stAT402Cmd.stCommon.xReset := TRUE;
    68:  // TT403 Ack
        GVL_Hmi.stTT403Cmd.stCommon.xAck := TRUE;
    69:  // TT403 Reset
        GVL_Hmi.stTT403Cmd.stCommon.xReset := TRUE;
    70:  // ZS404 Ack
        GVL_Hmi.stZS404Cmd.stCommon.xAck := TRUE;
    71:  // ZS404 Reset
        GVL_Hmi.stZS404Cmd.stCommon.xReset := TRUE;
    72:  // YS405 Ack
        GVL_Hmi.stYS405Cmd.stCommon.xAck := TRUE;
    73:  // YS405 Reset
        GVL_Hmi.stYS405Cmd.stCommon.xReset := TRUE;
    74:  // HS501 Ack
        GVL_Hmi.stHS501Cmd.stCommon.xAck := TRUE;
    75:  // HS501 Reset
        GVL_Hmi.stHS501Cmd.stCommon.xReset := TRUE;
    76:  // HS502 Ack
        GVL_Hmi.stHS502Cmd.stCommon.xAck := TRUE;
    77:  // HS502 Reset
        GVL_Hmi.stHS502Cmd.stCommon.xReset := TRUE;
ELSE
    ApplyCommand := FALSE;
END_CASE
