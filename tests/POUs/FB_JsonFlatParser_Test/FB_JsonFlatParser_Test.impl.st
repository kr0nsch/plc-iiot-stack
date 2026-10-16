// Каждый тест-метод вызывается каждый цикл; coUnit отслеживает завершённые (TEST_FINISHED).
ParsesFlatObjectWithAllTypes();
TracksIntegerLiterals();
AcceptsWhitespaceAndEmptyObject();
RejectsNestedObjectsAndArrays();
RejectsDuplicateKeys();
RejectsSyntaxErrors();
RejectsTrailingCharacters();
ValidatesNumberGrammarAndRange();
DecodesEscapes();
RejectsRawControlCharacters();
LimitsKeyAndValueLength();
LimitsFieldCount();
FailedParseClearsPreviousFields();
