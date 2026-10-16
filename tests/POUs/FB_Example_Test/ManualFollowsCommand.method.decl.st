// Ручной режим: выход повторяет команду оператора, измерение на выход не влияет
// и отказ не фиксируется (docs/ASSUMPTIONS.md, C5).
METHOD PRIVATE ManualFollowsCommand
VAR
    fbDut : FB_Example;         // проверяемый экземпляр, новый при каждом вызове метода
END_VAR
