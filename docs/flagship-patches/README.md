# Правки флагмана для встраивания IIoT-стека

Что нужно репозиторию kns-pump-station, чтобы в нём собиралась и работала ПЛК-часть этого стека
([MANUAL_STEPS.md, раздел 11](../MANUAL_STEPS.md#11-встраивание-во-флагман)). Всё это делает
`python tools_project/flagship_embed.py --repo <рабочая копия флагмана>`; здесь — то же для ревью и для
переноса руками.

| Файл | Что | Как применить |
|---|---|---|
| [0001-prg-iiot-task-and-gvl-iiot-symbols.patch](0001-prg-iiot-task-and-gvl-iiot-symbols.patch) | `tools/codesys/config.json`: `PRG_Iiot` в задаче `MainTask` после `PRG_Devices` и в `library.exclude`; `tools_project/codesys/symbol_rules.json`: правило `GVL_Iiot` (`stIiotCfg`, `stIiotSts` — чтение) | `git apply <путь>/0001-prg-iiot-task-and-gvl-iiot-symbols.patch` в корне флагмана; снят с `main` флагмана `f750cea`, проверен `git apply --check` |
| исходники ST | ядро `src/` (без `src/POUs/PRG_Main`), привязка `flagship/src/`, раздел «IIoT» в `GVL_Const` флагмана, наборы тестов `tests/` и `flagship/tests/`, список `tests/GVLs/GVL_TestsIiot.gvl.st` | `flagship_embed.py` — патчем не прикладываются: они генерируются из этого репозитория и устарели бы с первым изменением ядра |

Почему нужно правило `GVL_Iiot`: `symbol_config.py` флагмана снимает доступ со всех переменных, для которых
нет правила, — атрибут `{attribute 'symbol' := 'read'}` в исходнике `GVL_Iiot` этого не меняет. Проверено
19.10.2026 на рабочей копии флагмана `58fc169` со встроенной ПЛК-частью: без правила `GVL_Iiot` в файл символов
не попадает (сверка с правилами при этом проходит), с правилом — `GVL_Iiot: Read — 2`, у типа
`ST_MqttBrokerCfg` в символах 10 полей из 11, `sPassword` нет.

Проверено с этими правками ([TEST_REPORT.md](../TEST_REPORT.md#встраивание-во-флагман-и-стенд-против-его-рантайма)):
сборка приложения флагмана с `PRG_Iiot` в `MainTask` — 0 ошибок, 0 предупреждений; тестовое приложение —
423 теста coUnit из 423 (333 флагмана и 90 этого репозитория); приложение имитации — `PRG_Iiot` работает,
`GVL_Iiot.stIiotSts` читается по OPC UA.
