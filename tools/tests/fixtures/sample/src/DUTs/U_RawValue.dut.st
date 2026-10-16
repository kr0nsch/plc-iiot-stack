// Сырое значение из регистра Modbus: как DWORD или как REAL
TYPE U_RawValue :
UNION
    dwRaw : DWORD;
    rValue : REAL;
END_UNION
END_TYPE
