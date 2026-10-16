// Опубликовать состояние узла (QoS 1, retain). TRUE — клиент принял.
METHOD PRIVATE PublishStatus : BOOL
VAR_INPUT
    xOnline : BOOL;
    sReason : STRING(GVL_Const.IIOT_TEXT_LEN);
END_VAR
