"""``python -m iiot_emulator`` — то же, что ``kns-emulator``."""

import sys

from .cli import main

sys.exit(main())
