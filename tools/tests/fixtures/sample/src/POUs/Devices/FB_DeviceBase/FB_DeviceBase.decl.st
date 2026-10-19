(*
    Назначение: базовый блок устройства — режим, диагностика NE 107, квитирование
    Автор: kr0nsch
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
