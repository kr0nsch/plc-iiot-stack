# -*- coding: utf-8 -*-
"""Запуск юнит-тестов coUnit (CfUnit) в CODESYS Control Win V3 — скрипт CODESYS Scripting (IronPython 2.7).

Запуск — только через tools/codesys/cds.py (python tools/codesys/cds.py test): задание из трёх
шагов в одном процессе CODESYS — import (с tests/, режим test), build, test. cds.py держит
глобальную блокировку рантайма и при необходимости запускает пользовательский процесс
рантайма (cds.py runtime start).

Шаг test (последовательность проверена прогоном на CODESYS 3.5.17.30 и Control Win V3):
1. шлюз: online.gateways, при отсутствии — add_new_gateway("Gateway-1", localhost:1217);
   адрес устройства: dev.set_gateway_and_ip_address(gateway, "127.0.0.1", 11740);
2. учётные данные — из файла job["credentials"] (вне git, значения не пишутся в журнал);
   online.set_default_credentials; вход oa.login(OnlineChangeOption.Never, True) — загрузка с
   удалением чужих приложений. Если вход не удался, а рантайм свежий (нет пользователей),
   создаётся первый пользователь: online_device.set_credentials_for_initial_user + connect;
3. oa.start(); опрос <runner>.AllTestSuitesFinished до таймаута;
4. итоги и результаты по наборам и тестам — read_value по индексам 1..N, пока имя не пустое;
5. oa.stop(); oa.logout(); результаты — job["results"] (build/test-results.json).
"""
from __future__ import absolute_import, print_function, unicode_literals

import time

import cds_common as C

MYPY = False
if MYPY:  # pragma: no cover
    from typing import Any, Dict, List, Optional  # noqa: F401


def read_credentials(path):
    # type: (str) -> Dict[str, str]
    try:
        data = C.read_json(path)
    except IOError:
        raise C.StepError('нет файла учётных данных рантайма %s (cds.py runtime init создаст его)' % path)
    except ValueError as exc:
        raise C.StepError('файл учётных данных %s — не JSON: %s' % (path, exc))
    user = data.get('user') or data.get('username')
    password = data.get('password')
    if not user or password is None:
        raise C.StepError('в файле %s нужны поля "user" и "password"' % path)
    return {'user': C._text(user), 'password': C._text(password)}


def setup_gateway(dev, runtime, log):
    # type: (Any, Dict[str, Any], C.Log) -> str
    """Шлюз и адрес устройства; возвращает строку цели входа для сообщений."""
    online = C.api().online
    name = runtime.get('gateway_name') or 'Gateway-1'
    gateways = list(online.gateways)
    gateway = None
    for gw in gateways:
        if C._text(gw.name).lower() == name.lower():
            gateway = gw
            break
    if gateway is None and gateways:
        gateway = gateways[0]
        log.info('шлюз %s не найден, используется %s' % (name, C._text(gateway.name)))
    if gateway is None:
        params = {
            'IP-Address': runtime.get('gateway_host') or 'localhost',
            'Port': int(runtime.get('gateway_port') or 1217),
        }
        gateway = online.gateways.add_new_gateway(name, params)
        log.info('добавлен шлюз %s (%s:%s)' % (name, params['IP-Address'], params['Port']))
    address = runtime.get('device_address') or '127.0.0.1'
    port = int(runtime.get('device_port') or 11740)
    dev.set_gateway_and_ip_address(gateway, address, port)
    target = '%s:%d (шлюз %s)' % (address, port, C._text(gateway.name))
    log.info('устройство: %s' % target)
    return target


def login(app, dev, creds, target, log):
    # type: (Any, Any, Dict[str, str], str, C.Log) -> Any
    """Вход и загрузка приложения; при неудаче — создание первого пользователя и повторный вход.

    Учётные данные (и имя пользователя) в журнал не пишутся. Если не удались обе попытки —
    StepError с кодом EXIT_INTERNAL (окружение) и обоими сообщениями CODESYS в одной строке.
    """
    se = C.api()
    online = se.online
    online.set_default_credentials(creds['user'], creds['password'])
    oa = online.create_online_application(app)
    try:
        oa.login(se.OnlineChangeOption.Never, True)
        return oa
    except Exception as exc:
        first = C.squash_ws(C._text(exc))
        log.warn('вход не удался (%s) — попытка создать первого пользователя на свежем рантайме' % first)
    # Свежий рантайм: обязательное управление пользователями, пользователей ещё нет
    try:
        od = online.create_online_device(dev)
        od.set_credentials_for_initial_user(creds['user'], creds['password'], True, False)
        od.connect()
        log.info('подключение к устройству выполнено')
        oa = online.create_online_application(app)
        oa.login(se.OnlineChangeOption.Never, True)
        return oa
    except Exception as exc:
        second = C.squash_ws(C._text(exc))
    raise C.StepError(
        'не удалось войти в рантайм %s: %s; повторная попытка (создание первого пользователя): %s. '
        'Проверьте: python tools/codesys/cds.py runtime status; учётные данные — файл '
        'CODESYS_RUNTIME_CREDENTIALS (docs/MANUAL_STEPS.md, раздел 4)' % (target, first, second),
        C.EXIT_INTERNAL,
    )


class Reader(object):
    """Чтение переменных онлайн-приложения с разбором значений."""

    def __init__(self, oa, log):
        # type: (Any, C.Log) -> None
        self.oa = oa
        self.log = log

    def raw(self, expr):
        # type: (str) -> Optional[str]
        try:
            return C._text(self.oa.read_value(expr))
        except Exception as exc:
            self.log.info('read_value(%s): %s' % (expr, exc))
            return None

    def value(self, expr, default=None):
        # type: (str, Any) -> Any
        raw = self.raw(expr)
        return default if raw is None else C.plc_value(raw)

    def values(self, exprs):
        # type: (List[str]) -> List[Any]
        try:
            raws = list(self.oa.read_values(exprs))
            return [C.plc_value(C._text(r)) for r in raws]
        except Exception:
            return [self.value(e) for e in exprs]


def read_results(reader, runner, max_suites, max_tests):
    # type: (Reader, str, int, int) -> Dict[str, Any]
    base = runner + '.TestResults.TestSuiteResults'
    totals = reader.values(
        [
            base + '.NumberOfTestSuites',
            base + '.NumberOfTestCases',
            base + '.NumberOfSuccessfulTestCases',
            base + '.NumberOfFailedTestCases',
        ]
    )
    n_suites = totals[0] if isinstance(totals[0], int) else max_suites
    suites = []  # type: List[Dict[str, Any]]
    for i in range(1, min(int(n_suites), max_suites) + 1):
        sbase = '%s.TestSuiteResults[%d]' % (base, i)
        # NumberOfTests/NumberOfFailedTests набора — поддиапазонные типы, read_value их не читает
        # («Type 'Subrange' is not a literal type», 3.5.17.30): идём по индексам, пока имя не пустое
        name = reader.value(sbase + '.Name')
        if not name:
            break
        cases = []  # type: List[Dict[str, Any]]
        for j in range(1, max_tests + 1):
            tbase = '%s.TestCaseResults[%d]' % (sbase, j)
            fields = reader.values(
                [
                    tbase + '.TestName',
                    tbase + '.TestClassName',
                    tbase + '.TestIsFailed',
                    tbase + '.TestIsSkipped',
                    tbase + '.FailureMessage',
                    tbase + '.FailureType',
                ]
            )
            test_name, class_name, failed, skipped, message, ftype = fields
            if not test_name:
                break
            status = 'SKIP' if skipped is True else ('FAIL' if failed is True else 'PASS')
            cases.append(
                {
                    'name': test_name,
                    'class_name': class_name or None,
                    'status': status,
                    'message': (message or None) if status == 'FAIL' else None,
                    'failure_type': (C._text(ftype) if ftype not in (None, '') else None) if status == 'FAIL' else None,
                }
            )
        short = name
        prefix = 'Device.Application.'
        if short.startswith(prefix):
            short = short[len(prefix):]
        suites.append(
            {
                'name': short,
                'path': name,
                'tests': len(cases),
                'failed': len([c for c in cases if c['status'] == 'FAIL']),
                'skipped': len([c for c in cases if c['status'] == 'SKIP']),
                'cases': cases,
            }
        )
    tests = sum(s['tests'] for s in suites)
    failed = sum(s['failed'] for s in suites)
    skipped = sum(s['skipped'] for s in suites)
    return {
        'totals': {
            'suites': len(suites),
            'tests': tests,
            'passed': tests - failed - skipped,
            'failed': failed,
            'skipped': skipped,
            'reported_suites': totals[0] if isinstance(totals[0], int) else None,
            'reported_tests': totals[1] if isinstance(totals[1], int) else None,
            'reported_successful': totals[2] if isinstance(totals[2], int) else None,
            'reported_failed': totals[3] if isinstance(totals[3], int) else None,
        },
        'suites': suites,
    }


def run(ctx, step):
    # type: (C.Context, Dict[str, Any]) -> Dict[str, Any]
    log = C.Log(step.get('log'))
    se = C.api()
    results = {
        'schema': 1,
        'started': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'project': step.get('project'),
        'finished': False,
    }  # type: Dict[str, Any]
    results.update(step.get('meta') or {})
    oa = None
    try:
        tests_cfg = step.get('tests') or {}
        runner = tests_cfg.get('runner') or 'coUnit.GVL_coUnit.coUnitRunner'
        timeout_s = float(tests_cfg.get('timeout_s') or 120)
        poll_ms = int(tests_cfg.get('poll_ms') or 500)
        max_suites = int(tests_cfg.get('max_suites') or 1000)
        max_tests = int(tests_cfg.get('max_tests_per_suite') or 100)
        creds = read_credentials(step['credentials'])
        proj, _ = ctx.open_project(step['project'], create=False, log=log)
        app = C.application(proj)
        dev = C.find_device(proj)
        if dev is None:
            raise C.StepError('в проекте нет устройства')
        target = setup_gateway(dev, step.get('runtime') or {}, log)
        log.info('вход в рантайм и загрузка приложения')
        oa = login(app, dev, creds, target, log)
        log.info('приложение загружено, состояние %s' % C._text(oa.application_state))
        oa.start()
        started = time.time()
        reader = Reader(oa, log)
        finished = False
        while time.time() - started < timeout_s:
            se.system.delay(poll_ms)
            if reader.value(runner + '.AllTestSuitesFinished') is True:
                finished = True
                break
        waited = round(time.time() - started, 1)
        results['finished'] = finished
        results['wait_s'] = waited
        if not finished:
            log.error('тесты не завершились за %s с (%s.AllTestSuitesFinished != TRUE)' % (timeout_s, runner))
        else:
            log.info('все наборы завершены за %s с' % waited)
            stored = reader.value(runner + '.TestResults.StoredGeneralTestResults')
            for _ in range(20):
                if stored is True:
                    break
                se.system.delay(poll_ms)
                stored = reader.value(runner + '.TestResults.StoredGeneralTestResults')
            results['stored_general_results'] = stored
        data = read_results(reader, runner, max_suites, max_tests)
        results.update(data)
        totals = data['totals']
        for suite in data['suites']:
            log.info('набор %s: тестов %d, упало %d, пропущено %d'
                     % (suite['name'], suite['tests'], suite['failed'], suite['skipped']))
            for case in suite['cases']:
                line = '  %s %s' % (case['status'], case['name'])
                if case['status'] == 'FAIL':
                    log.error(line + ': %s' % (case['message'] or ''))
                else:
                    log.info(line)
        if finished and totals['reported_tests'] is not None and totals['reported_tests'] != totals['tests']:
            log.warn('coUnit сообщает тестов %s, прочитано %d' % (totals['reported_tests'], totals['tests']))
        log.info('итог: наборов %d, тестов %d, пройдено %d, упало %d, пропущено %d'
                 % (totals['suites'], totals['tests'], totals['passed'], totals['failed'], totals['skipped']))
        ok = finished and totals['failed'] == 0 and totals['tests'] > 0
        if finished and totals['tests'] == 0:
            log.error('coUnit не нашёл ни одного теста')
        results['ok'] = ok
        out = {'ok': ok, 'finished': finished, 'totals': totals, 'results': step.get('results')}
        if not ok:
            out['error'] = 'тесты: упало %d из %d%s' % (
                totals['failed'], totals['tests'], '' if finished else ', прогон не завершён (таймаут)')
        return out
    except Exception as exc:
        results['ok'] = False
        results['error'] = C._text(exc)
        log.error('%s' % exc)
        raise
    finally:
        if oa is not None:
            try:
                oa.stop()
                log.info('приложение остановлено')
            except Exception as exc:
                log.warn('stop: %s' % exc)
            try:
                oa.logout()
                log.info('выход из рантайма')
            except Exception as exc:
                log.warn('logout: %s' % exc)
        results['ended'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        if step.get('results'):
            try:
                C.write_json(step['results'], results)
            except Exception:
                pass
        log.close()


if __name__ == '__main__':
    C.run_main('test')
