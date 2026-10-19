// Назначение: текст качества для поля quality: good, uncertain, bad.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Телеметрия»
FUNCTION F_IiotQualityText : STRING(GVL_Const.IIOT_TEXT_LEN)
VAR_INPUT
    eQuality : E_IiotQuality;
END_VAR
