(*
    Прокладка CfUnit/coUnit для проверки RuSTy (только объявления, не для CODESYS).

    Имена и сигнатуры — по исследованию API coUnit 1.2.0.0 (_research/cfunit.md, раздел 2;
    исходник библиотеки на CODESYS Forge). Компилятором CODESYS не проверялись.
    Пространство имён библиотеки (coUnit. или CfUnit.) убирает run_rusty.py
    (--strip-namespace, по умолчанию coUnit и CfUnit).
    Тела пустые: RuSTy проверяет типы и вызовы, но не компонует программу.
*)

TYPE T_MaxString : STRING[255]; END_TYPE

FUNCTION_BLOCK FB_TestSuite
VAR
    InstancePath : T_MaxString;
END_VAR

METHOD PUBLIC AreAllTestsFinished : BOOL
END_METHOD

METHOD PUBLIC AssertEquals
VAR_INPUT
    Expected : ANY;
    Actual : ANY;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertTrue
VAR_INPUT
    Condition : BOOL;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertFalse
VAR_INPUT
    Condition : BOOL;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_BOOL
VAR_INPUT
    Expected : BOOL;
    Actual : BOOL;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_BYTE
VAR_INPUT
    Expected : BYTE;
    Actual : BYTE;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_WORD
VAR_INPUT
    Expected : WORD;
    Actual : WORD;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_DWORD
VAR_INPUT
    Expected : DWORD;
    Actual : DWORD;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_LWORD
VAR_INPUT
    Expected : LWORD;
    Actual : LWORD;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_SINT
VAR_INPUT
    Expected : SINT;
    Actual : SINT;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_INT
VAR_INPUT
    Expected : INT;
    Actual : INT;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_DINT
VAR_INPUT
    Expected : DINT;
    Actual : DINT;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_LINT
VAR_INPUT
    Expected : LINT;
    Actual : LINT;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_USINT
VAR_INPUT
    Expected : USINT;
    Actual : USINT;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_UINT
VAR_INPUT
    Expected : UINT;
    Actual : UINT;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_UDINT
VAR_INPUT
    Expected : UDINT;
    Actual : UDINT;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_ULINT
VAR_INPUT
    Expected : ULINT;
    Actual : ULINT;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_TIME
VAR_INPUT
    Expected : TIME;
    Actual : TIME;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_LTIME
VAR_INPUT
    Expected : LTIME;
    Actual : LTIME;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_DATE
VAR_INPUT
    Expected : DATE;
    Actual : DATE;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_DATE_AND_TIME
VAR_INPUT
    Expected : DATE_AND_TIME;
    Actual : DATE_AND_TIME;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_TIME_OF_DAY
VAR_INPUT
    Expected : TIME_OF_DAY;
    Actual : TIME_OF_DAY;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_STRING
VAR_INPUT
    Expected : T_MaxString;
    Actual : T_MaxString;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_WSTRING
VAR_INPUT
    Expected : WSTRING[255];
    Actual : WSTRING[255];
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_REAL
VAR_INPUT
    Expected : REAL;
    Actual : REAL;
    Delta : REAL;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertEquals_LREAL
VAR_INPUT
    Expected : LREAL;
    Actual : LREAL;
    Delta : LREAL;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertArrayEquals_BOOL
VAR_IN_OUT
    Expecteds : ARRAY[*] OF BOOL;
    Actuals : ARRAY[*] OF BOOL;
END_VAR
VAR_INPUT
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertArrayEquals_INT
VAR_IN_OUT
    Expecteds : ARRAY[*] OF INT;
    Actuals : ARRAY[*] OF INT;
END_VAR
VAR_INPUT
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertArrayEquals_DINT
VAR_IN_OUT
    Expecteds : ARRAY[*] OF DINT;
    Actuals : ARRAY[*] OF DINT;
END_VAR
VAR_INPUT
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertArrayEquals_REAL
VAR_IN_OUT
    Expecteds : ARRAY[*] OF REAL;
    Actuals : ARRAY[*] OF REAL;
END_VAR
VAR_INPUT
    Delta : REAL;
    Message : T_MaxString;
END_VAR
END_METHOD

METHOD PUBLIC AssertArrayEquals_LREAL
VAR_IN_OUT
    Expecteds : ARRAY[*] OF LREAL;
    Actuals : ARRAY[*] OF LREAL;
END_VAR
VAR_INPUT
    Delta : LREAL;
    Message : T_MaxString;
END_VAR
END_METHOD
END_FUNCTION_BLOCK

FUNCTION TEST
VAR_INPUT
    TestName : T_MaxString;
END_VAR
END_FUNCTION

FUNCTION TEST_ORDERED : BOOL
VAR_INPUT
    TestName : T_MaxString;
END_VAR
END_FUNCTION

FUNCTION TEST_FINISHED : BOOL
END_FUNCTION

FUNCTION TEST_FINISHED_NAMED
VAR_INPUT
    TestName : T_MaxString;
END_VAR
END_FUNCTION

FUNCTION IS_TEST_FINISHED : BOOL
VAR_INPUT
    TestName : T_MaxString;
END_VAR
END_FUNCTION

FUNCTION RUN
END_FUNCTION

FUNCTION RUN_IN_SEQUENCE
END_FUNCTION
