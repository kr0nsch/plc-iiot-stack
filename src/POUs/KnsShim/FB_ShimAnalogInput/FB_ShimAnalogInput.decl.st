// Назначение: заглушка флагмана вместо PL.FB_AnalogInput: переменные с именами выходов настоящего ФБ, без
//             логики. Здесь это входы: снаружи их пишут тесты (выход ФБ снаружи не записать, C0037),
//             а PRG_Iiot читает их той же записью GVL_Devices.fb<TAG>.<имя>, что и выходы во флагмане.
//             При встраивании во флагман удаляется вместе с папкой KnsShim.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Заглушка флагмана»
FUNCTION_BLOCK FB_ShimAnalogInput
VAR_INPUT
    rValue_eu : REAL;
    rValue_pct : REAL;
    xValid : BOOL;
    stSts : ST_AnalogInputSts;
END_VAR
