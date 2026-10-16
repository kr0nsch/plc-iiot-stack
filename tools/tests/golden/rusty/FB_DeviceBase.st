(*
    Назначение: базовый блок устройства — режим, диагностика NE 107, квитирование
    Автор: <ИМЯ ФАМИЛИЯ>
    Версия: 1.0.0
    Документ: docs/ARCHITECTURE.md
*)
FUNCTION_BLOCK ABSTRACT FB_DeviceBase IMPLEMENTS I_Device
VAR_INPUT
    xEnable : BOOL := TRUE;     // разрешение работы
END_VAR
VAR_OUTPUT
    xFault : BOOL;              // отказ
    eNamur : E_NamurStatus := E_NamurStatus.Good;
END_VAR
VAR
    eModeInt : E_DeviceMode := E_DeviceMode.Auto;
END_VAR
METHOD PUBLIC Reset : BOOL
VAR_INPUT
    xForce : BOOL;
END_VAR
xFault := FALSE;
eNamur := E_NamurStatus.Good;
Reset := TRUE;
END_METHOD
METHOD PUBLIC ABSTRACT Start
VAR_INPUT
    rSpeed_rpm : REAL;
END_VAR
END_METHOD
PROPERTY_GET Mode : E_DeviceMode
Mode := eModeInt;
END_PROPERTY
PROPERTY_SET Mode : E_DeviceMode
eModeInt := Mode;
END_PROPERTY
// Общего тела нет: логика — в производных блоках
END_FUNCTION_BLOCK
