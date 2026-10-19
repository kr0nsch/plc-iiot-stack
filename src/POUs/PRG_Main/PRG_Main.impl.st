// Часы ПЛК в диапазоне ts схемы — так же, как проверяет их PRG_Iiot во флагмане
GVL_Iiot.stIiotSts.xClockValid := SysTimeRtcHighResGet(pTimestamp := uliTs_ms) = RTC_OK
    AND F_IiotClockValid(uliTs_ms := uliTs_ms);
