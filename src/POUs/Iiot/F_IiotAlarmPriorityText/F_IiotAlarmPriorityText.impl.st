CASE ePriority OF
    E_IiotAlarmPriority.Low:
        F_IiotAlarmPriorityText := 'Low';
    E_IiotAlarmPriority.Medium:
        F_IiotAlarmPriorityText := 'Medium';
    E_IiotAlarmPriority.High:
        F_IiotAlarmPriorityText := 'High';
    E_IiotAlarmPriority.Critical:
        F_IiotAlarmPriorityText := 'Critical';
ELSE
    F_IiotAlarmPriorityText := '';
END_CASE
