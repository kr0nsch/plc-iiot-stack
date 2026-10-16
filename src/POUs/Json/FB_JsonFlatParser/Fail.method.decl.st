// Зафиксировать ошибку разбора в текущей позиции; поля разобранного объекта сбрасываются.
METHOD PRIVATE Fail
VAR_INPUT
    eReason : E_JsonError;
END_VAR
