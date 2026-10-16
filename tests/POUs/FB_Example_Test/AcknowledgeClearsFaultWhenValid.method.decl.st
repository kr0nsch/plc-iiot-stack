// Квитирование при достоверном измерении снимает отказ, выход снова управляется.
METHOD PRIVATE AcknowledgeClearsFaultWhenValid
VAR
    fbDut : FB_Example;         // проверяемый экземпляр, новый при каждом вызове метода
    xAckResult : BOOL;          // результат Acknowledge()
END_VAR
