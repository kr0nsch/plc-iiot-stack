CASE eState OF
    E_MqttConnState.Disabled, E_MqttConnState.Closing:
        eNe107 := E_IiotNe107.CheckFunction;
    E_MqttConnState.Connected:
        IF xDegraded THEN
            eNe107 := E_IiotNe107.MaintenanceRequired;
        ELSE
            eNe107 := E_IiotNe107.Good;
        END_IF
ELSE
    IF uiConsecutiveFailures >= MAX(uiFailThreshold, 1) THEN
        eNe107 := E_IiotNe107.Failure;
    ELSIF udiConnects = 0 AND uiConsecutiveFailures = 0 THEN
        eNe107 := E_IiotNe107.CheckFunction;
    ELSE
        eNe107 := E_IiotNe107.OutOfSpecification;
    END_IF
END_CASE
