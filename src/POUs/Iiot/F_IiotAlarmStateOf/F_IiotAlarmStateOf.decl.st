// Назначение: состояние тревоги слота uiSlot по словам источника по старшинству plc-process-lib:
//             вывод из работы, подавлена логикой, отложена, активна и не квитирована, активна, вернулась
//             без квитирования, норма.
// Автор:      kr0nsch
// Версия:     0.2.0
// Документ:   docs/plc_mqtt.md, раздел «Тревоги»
FUNCTION F_IiotAlarmStateOf : E_IiotAlarmState
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    stWords : ST_IiotAlarmWords;
END_VAR
VAR_INPUT
    uiSlot : UINT;
END_VAR
VAR
    wBit : WORD;
END_VAR
VAR CONSTANT
    SLOT0_MASK : WORD := 1;     // бит слота 0; маска слота uiSlot — сдвиг на uiSlot
END_VAR
