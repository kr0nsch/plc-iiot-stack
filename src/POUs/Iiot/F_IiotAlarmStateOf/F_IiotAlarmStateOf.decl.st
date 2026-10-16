// Назначение: состояние тревоги слота uiSlot по словам устройства: вывод из работы, отложена,
//             активна и не квитирована, активна, вернулась без квитирования, норма.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
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
