// Квитирование при недостоверном измерении отказ не снимает.
METHOD PRIVATE AcknowledgeKeepsFaultWhileInvalid
VAR
    fbDut : FB_Example;         // проверяемый экземпляр, новый при каждом вызове метода
    xAckResult : BOOL;          // результат Acknowledge()
END_VAR
