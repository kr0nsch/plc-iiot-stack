(*
    Назначение: базовый блок устройства — режим, диагностика NE 107, квитирование
    Автор: kr0nsch
    Версия: 1.0.0
    Документ: docs/ARCHITECTURE.md
*)
FUNCTION_BLOCK FB_DeviceBase
VAR_INPUT
    xEnable : BOOL := TRUE;     // разрешение работы
END_VAR
VAR_OUTPUT
    xFault : BOOL;              // отказ
    eNamur : E_NamurStatus;
END_VAR
VAR
    eModeInt : E_DeviceMode;
END_VAR
// Общего тела нет: логика — в производных блоках
END_FUNCTION_BLOCK

FUNCTION FB_DeviceBase__Reset : BOOL
VAR_INPUT
    xForce : BOOL;
END_VAR
VAR (* копии переменных FB_DeviceBase — приближение для статанализа *)
    xFault : BOOL;
    eNamur : E_NamurStatus;
    Reset : BOOL;
END_VAR
xFault := FALSE;
eNamur := E_NamurStatus.Good;
Reset := TRUE;
FB_DeviceBase__Reset := Reset;
END_FUNCTION

FUNCTION FB_DeviceBase__Start : BOOL
VAR_INPUT
    rSpeed_rpm : REAL;
END_VAR
FB_DeviceBase__Start := TRUE;
END_FUNCTION

FUNCTION FB_DeviceBase__Mode__get : E_DeviceMode
VAR (* копии переменных FB_DeviceBase — приближение для статанализа *)
    eModeInt : E_DeviceMode;
    Mode : E_DeviceMode;
END_VAR
Mode := eModeInt;
FB_DeviceBase__Mode__get := Mode;
END_FUNCTION

FUNCTION FB_DeviceBase__Mode__set : BOOL
VAR_INPUT
    Mode : E_DeviceMode;
END_VAR
VAR (* копии переменных FB_DeviceBase — приближение для статанализа *)
    eModeInt : E_DeviceMode;
END_VAR
eModeInt := Mode;
FB_DeviceBase__Mode__set := TRUE;
END_FUNCTION
