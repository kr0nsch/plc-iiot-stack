// Отказ остаётся, только если измерение всё ещё недостоверно
xFault := xFault AND NOT xValueValid;
Acknowledge := NOT xFault;
