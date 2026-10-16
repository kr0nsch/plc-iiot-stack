"""Командная строка ``kns-emulator``.

Примеры::

    kns-emulator run --env-file ../.env              # OPC UA + MQTT по настройкам EMU_*
    kns-emulator run --no-mqtt --time-factor 600     # только OPC UA, сутки за 2,4 минуты
    kns-emulator simulate --hours 48 --csv day.csv   # без сети: прогон модели и сводка
    kns-emulator tags                                # узлы OPC UA и топики телеметрии
    kns-emulator faults                              # отказы для узлов Simulation.Inject
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import csv
import dataclasses
import logging
import signal
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from .config import Settings, load_env_file
from .emulator import EmulatorConfig, KnsEmulator
from .faults import ACTIONS, FAULTS
from .schema import default_topics, telemetry_catalog


def _settings(args: argparse.Namespace) -> Settings:
    if args.env_file:
        load_env_file(Path(args.env_file))
    s = Settings.from_env()
    sim = s.sim
    if args.seed is not None:
        sim = dataclasses.replace(sim, seed=args.seed)
    if args.time_factor is not None:
        sim = dataclasses.replace(sim, time_factor=args.time_factor)
    if args.no_auto_faults:
        sim = dataclasses.replace(sim, auto_faults=False)
    opcua = dataclasses.replace(s.opcua, enable=False) if args.no_opcua else s.opcua
    mqtt = dataclasses.replace(s.mqtt, enable=False) if args.no_mqtt else s.mqtt
    return dataclasses.replace(s, sim=sim, opcua=opcua, mqtt=mqtt)


def cmd_run(args: argparse.Namespace) -> int:
    from .app import EmulatorApp

    settings = _settings(args)
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    app = EmulatorApp(settings)

    async def main() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError, RuntimeError):
                loop.add_signal_handler(sig, app.stop)
        await app.run(duration_s=args.duration)

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    emu = KnsEmulator(
        EmulatorConfig(seed=args.seed if args.seed is not None else 1, auto_faults=not args.no_auto_faults)
    )
    rows: list[dict[str, object]] = []
    step_h = args.sample_min / 60.0
    n = round(args.hours / step_h)
    for _ in range(n):
        emu.run_for(step_h * 3600)
        im = emu.image()
        rows.append(
            {
                "sim_h": round(emu.t / 3600, 3),
                "hour": round(emu.sim_hour, 2),
                "inflow_m3h": round(emu.plant.inflow_m3h, 1),
                "level_m": round(float(im["LT101.Value"]), 3),
                "flow_m3h": round(float(im["FT202.Value"]), 1),
                "pressure_bar": round(float(im["PT201.Value"]), 2),
                **{f"{p}_speed": round(float(im[f"{p}.SpeedAct"]), 1) for p in ("P101", "P102", "P103")},
                **{f"{p}_hours": round(float(im[f"{p}.RunTime"]), 2) for p in ("P101", "P102", "P103")},
                **{f"{p}_starts": im[f"{p}.Starts"] for p in ("P101", "P102", "P103")},
            }
        )
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
            w.writeheader()
            w.writerows(rows)
    act = Counter(ev.alarm.code for ev in emu.events if ev.reason.name == "ACTIVATED")
    levels = [float(r["level_m"]) for r in rows]  # type: ignore[arg-type]
    print(f"seed={emu.cfg.seed}, модельных часов: {args.hours}, точек: {len(rows)}")
    print(f"уровень: мин {min(levels):.2f} м, макс {max(levels):.2f} м")
    im = emu.image()
    for p in ("P101", "P102", "P103"):
        print(f"{p}: наработка {float(im[p + '.RunTime']):.1f} ч, пусков {im[p + '.Starts']}")
    print(f"АВР: {emu.station.state.transfers}, смен ведущего: {emu.station.state.rotations}")
    print("тревоги (появления): " + (", ".join(f"{k}×{v}" for k, v in act.most_common()) or "нет"))
    return 0


def cmd_tags(args: argparse.Namespace) -> int:
    emu = KnsEmulator(EmulatorConfig(auto_faults=False))
    if args.what in ("opcua", "all"):
        for t in emu.tags:
            print(f"{t.opcua_node_id}\t{t.data_type}\t{'RW' if t.writable else 'R'}")
    if args.what in ("mqtt", "all"):
        topics = default_topics()
        for m in telemetry_catalog():
            print(f"{topics.telemetry(m.device, m.metric)}\t{m.kind}\t{m.unit}")
    return 0


def cmd_faults(args: argparse.Namespace) -> int:
    for name, text in {**FAULTS, **ACTIONS}.items():
        print(f"{name:20s} {text}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kns-emulator", description="Эмулятор ПЛК КНС-1: OPC UA, MQTT, модель объекта")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--seed", type=int, help="зерно модели (по умолчанию EMU_SEED или 1)")
        sp.add_argument("--no-auto-faults", action="store_true", help="без автоматического сценария отказов")

    run = sub.add_parser("run", help="запустить OPC UA-сервер и MQTT")
    common(run)
    run.add_argument("--env-file", help="файл .env с переменными EMU_*")
    run.add_argument("--time-factor", type=float, help="ускорение модельного времени (EMU_TIME_FACTOR)")
    run.add_argument("--no-opcua", action="store_true")
    run.add_argument("--no-mqtt", action="store_true")
    run.add_argument("--duration", type=float, help="остановиться через столько секунд")
    run.set_defaults(func=cmd_run)

    sim = sub.add_parser("simulate", help="прогон модели без сети и сводка")
    common(sim)
    sim.add_argument("--hours", type=float, default=24.0)
    sim.add_argument("--sample-min", type=float, default=5.0, help="шаг выборки, модельные минуты")
    sim.add_argument("--csv", help="записать выборку в CSV")
    sim.set_defaults(func=cmd_simulate)

    tags = sub.add_parser("tags", help="узлы OPC UA и топики телеметрии")
    tags.add_argument("what", nargs="?", choices=("opcua", "mqtt", "all"), default="all")
    tags.set_defaults(func=cmd_tags)

    faults = sub.add_parser("faults", help="список отказов для инъекции")
    faults.set_defaults(func=cmd_faults)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(ValueError, OSError):
            sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    rc: int = args.func(args)
    return rc


if __name__ == "__main__":
    sys.exit(main())
