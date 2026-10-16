# -*- coding: utf-8 -*-
"""cds.py — импорт, сборка, тесты, экспорт и библиотеки CODESYS из консоли (Python 3.11+).

    python tools/codesys/cds.py import [--tests] | export [--tests] [--to DIR] | build [--tests]
                                test | roundtrip | library [--install] [--compiled] | deps [--rebuild]
                                runtime start|stop|status|restart|init | junit | report

Это запускатель: реализация — tools/codesys/cdshost/cli.py. Файл намеренно написан на общем
подмножестве Python 2.7 и 3 (как скрипты CODESYS в этом каталоге, см. tools/tests/test_py27_compat.py),
чтобы в IronPython он хотя бы выдал понятную ошибку. Справка: python tools/codesys/cds.py --help,
docs/MANUAL_STEPS.md, tools/README.md.
"""
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys

if sys.version_info < (3, 11):
    sys.stderr.write('cds.py: нужен Python 3.11+ (запущен %s) / Python 3.11+ is required\n' % sys.version.split()[0])
    sys.exit(2)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdshost.cli import main

if __name__ == '__main__':
    sys.exit(main())
