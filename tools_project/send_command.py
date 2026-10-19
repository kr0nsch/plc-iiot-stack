"""Команда оператора по MQTT и ответ ПЛК (или эмулятора) — для проверки стенда из командной строки.

Назначение: собрать команду по ``schema/command.schema.json`` (поля ``schema_version``, ``cmd_id``, ``ts``,
``origin``, ``command``, ``value``), опубликовать её в ``<site>/<area>/<unit>/<device>/cmd/<command>``
от пользователя-оператора из ``.env`` и дождаться ответа ``cmd_ack`` с тем же ``cmd_id``. Белый список
и диапазоны проверяет ПЛК, а не этот инструмент: команду вне белого списка он тоже отправит — так видно
отказ ``not_whitelisted``.

Автор: kr0nsch. Документ: docs/USAGE.md, раздел «Команда».

Примеры (стенд поднят: ``make demo`` или ``tools_project/local_stack.ps1 start -Emulator``)::

    python tools_project/send_command.py P102 SetManual
    python tools_project/send_command.py P103 SpeedSp 70
    python tools_project/send_command.py KNS1 SetStepped        # станция: GVL_Station.stStationCmd
    python tools_project/send_command.py P101 SetOos            # нет в белом списке: rejected

Код выхода: 0 — ``accepted``, 1 — ``rejected``, 2 — нет ответа или ошибка подключения.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import jsonschema

import stack_catalog as sc
from local_stack import StackError, load_env

REPO = Path(__file__).resolve().parent.parent


def build_command(command: str, value: float | None, origin: str, cmd_id: str | None = None) -> dict[str, Any]:
    """Тело команды по схеме; версия — из ``schema/topics.json``."""
    body: dict[str, Any] = {
        "schema_version": sc.load_topics()["schema_version"],
        "cmd_id": cmd_id or uuid.uuid4().hex,
        "ts": int(time.time() * 1000),
        "origin": origin,
        "command": command,
    }
    if value is not None:
        body["value"] = int(value) if float(value).is_integer() and command.endswith("Req") else value
    return body


def schema_errors(body: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft202012Validator(sc.load_schema("command"))
    return [e.message for e in validator.iter_errors(body)]


def whitelisted(device: str, command: str) -> bool:
    return any(e.device == device and e.command == command for e in sc.load_whitelist())


def send(env: dict[str, str], host: str, device: str, body: dict[str, Any], timeout: float) -> dict[str, Any] | None:
    """Опубликовать команду (QoS 1, без retain) и вернуть ответ cmd_ack или None."""
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion

    st = sc.station()
    prefix = f"{st['site']}/{st['area']}/{st['unit']}"
    command = body["command"]
    answer: list[dict[str, Any]] = []
    got = threading.Event()
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"send-command-{uuid.uuid4().hex[:8]}")
    client.username_pw_set(env["MQTT_OPERATOR_USER"], env["MQTT_OPERATOR_PASSWORD"])

    def on_message(_client: Any, _userdata: Any, msg: Any) -> None:
        payload = json.loads(msg.payload)
        if payload.get("cmd_id") == body["cmd_id"]:
            answer.append(payload)
            got.set()

    client.on_message = on_message
    client.connect(host, int(env.get("MQTT_PORT", "1883")), keepalive=30)
    client.loop_start()
    try:
        client.subscribe(f"{prefix}/{device}/cmd_ack/{command}", qos=1)
        time.sleep(0.5)  # подписка до команды: ответ без retain
        info = client.publish(f"{prefix}/{device}/cmd/{command}", json.dumps(body), qos=1, retain=False)
        info.wait_for_publish(timeout=10)
        got.wait(timeout)
    finally:
        client.loop_stop()
        client.disconnect()
    return answer[0] if answer else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("device", help="устройство: P101, LT101, KNS1, LIC101, …")
    parser.add_argument("command", help="команда: Start, Stop, SetAuto, SpeedSp, Ack, SetStepped, …")
    parser.add_argument("value", nargs="?", type=float, help="значение (SpeedSp — 0…100 %%)")
    parser.add_argument("--host", default="127.0.0.1", help="брокер MQTT (по умолчанию 127.0.0.1)")
    parser.add_argument("--env-file", type=Path, default=REPO / ".env", help="файл .env (по умолчанию .env)")
    parser.add_argument("--origin", default="operator@send_command", help="поле origin команды")
    parser.add_argument("--timeout", type=float, default=15.0, help="ожидание ответа, с (по умолчанию 15)")
    args = parser.parse_args(argv)
    body = build_command(args.command, args.value, args.origin)
    for err in schema_errors(body):
        print(f"предупреждение: команда не по схеме ({err}) — ПЛК её отклонит", file=sys.stderr)
    if not whitelisted(args.device, args.command):
        print(f"предупреждение: {args.device}/{args.command} нет в белом списке — ПЛК ответит not_whitelisted")
    try:
        env = load_env(args.env_file)
        ack = send(env, args.host, args.device, body, args.timeout)
    except (StackError, OSError, KeyError) as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 2
    print(f"→ {args.device}/cmd/{args.command} {json.dumps(body, ensure_ascii=False)}")
    if ack is None:
        print(f"нет ответа cmd_ack за {args.timeout:g} с: ПЛК или эмулятор не подключён к брокеру?")
        return 2
    print(f"← {args.device}/cmd_ack/{args.command} {json.dumps(ack, ensure_ascii=False)}")
    return 0 if ack.get("result") == "accepted" else 1


if __name__ == "__main__":
    sys.exit(main())
