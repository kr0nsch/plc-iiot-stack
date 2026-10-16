rSpeedSp_rpm := F_Clamp(
    rValue := rSpeed_rpm,
    rMin := GVL_Const.MOTOR_SPEED_MIN_RPM,
    rMax := GVL_Const.MOTOR_SPEED_MAX_RPM);
THIS^.stSts.xRunning := FALSE;
