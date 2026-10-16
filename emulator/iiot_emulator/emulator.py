"""Эмулятор ПЛК КНС-1: модель объекта + устройства + логика станции за один цикл.

Порядок цикла как у приложения CODESYS флагмана: входы (из модели объекта) → логика станции →
вызовы устройств (``PRG_Devices``) → выходы → шаг модели объекта (``PRG_PlantModel``).
Состояние ПЛК для внешнего мира — «образ» ``image()``: тег перечня → значение. Команды HMI и
SCADA пишутся в ``st<DEV>Cmd`` через ``write_tag()`` и обрабатываются в ближайшем цикле: импульсы
и маски сбрасываются (API 2.1).

Детерминизм: при одинаковых seed, шаге и последовательности команд результат один и тот же —
шум измерений берётся из собственного ГПСЧ, приток и сценарий — чистые функции (seed, t).
"""

from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from .alarms import AlarmEvent
from .devices import (
    AiConfig,
    AiInput,
    AnalogInput,
    Device,
    DiConfig,
    DigitalInput,
    Motor,
    MotorConfig,
    MotorVfd,
    Value,
)
from .faults import ACTIONS, FAULTS, AutoScenario, ScenarioEvent
from .plant import Plant, PlantParams
from .station import Station, StationParams
from .tagmodel import IEC_INT_RANGES, TagDef, alarms_of, devices, load_tags

# --- конфигурация устройств флагмана (перечень КНС, колонка params; см. iolistgen/examples/kns) ---
AI_CFG: dict[str, AiConfig] = {
    "LT101": AiConfig(AiInput.MILLIAMP, 0.0, 5.0, filter_s=2.0, hyst=dict.fromkeys(("HH", "H", "L", "LL"), 0.05)),
    "PT201": AiConfig(AiInput.MILLIAMP, 0.0, 10.0, filter_s=1.0, hyst={"HH": 0.1, "H": 0.1, "L": 0.1, "LL": 0.1}),
    "FT202": AiConfig(AiInput.MILLIAMP, 0.0, 500.0, filter_s=3.0, low_cut_pct=1.0, hyst={"L": 5.0}),
    "AT401": AiConfig(AiInput.MILLIAMP, 0.0, 40.0, hyst={"HH": 0.5, "H": 0.5}),
    "AT402": AiConfig(AiInput.MILLIAMP, 0.0, 100.0, hyst={"HH": 1.0, "H": 1.0}),
    "TT403": AiConfig(AiInput.ENG, -40.0, 60.0, hyst={"H": 1.0, "L": 1.0}),
    **{
        f"IT1{n}1": AiConfig(AiInput.RAW, 0.0, 60.0, raw_lo=0.0, raw_hi=600.0, filter_s=1.0, hyst={"HH": 0.5, "H": 0.5})
        for n in (1, 2, 3)
    },
}
DI_CFG: dict[str, DiConfig] = {
    "LS102": DiConfig(invert=True),
    "LS103": DiConfig(invert=True, fail_value=True),
    "ES301": DiConfig(alarm_on_true=False),
    **{f"TS1{n}2": DiConfig(invert=True) for n in (1, 2, 3)},
}
PUMP_CFG = MotorConfig(
    fb_start_s=10.0,
    fb_stop_s=15.0,
    min_stop_s=30.0,
    max_starts_per_hour=10,
    speed_min=60.0,
    speed_max=100.0,
    ramp_up=5.0,
    ramp_down=5.0,
    comm_loss_is_fault=False,
)
FAN_CFG = MotorConfig(fb_start_s=5.0, fb_stop_s=5.0, min_stop_s=10.0)

AUX_TAGS = ("HA1", "HL1", "K1")


class CommandError(ValueError):
    """Запись команды отклонена: тег не команда, тип или диапазон не подходят."""


@dataclass(frozen=True)
class EmulatorConfig:
    seed: int = 1
    step_s: float = 1.0  # модельный шаг цикла ПЛК
    start_hour: float = 6.0  # модельное время суток при старте
    auto_faults: bool = True
    auto_ack_s: float = 900.0  # «оператор» квитирует тревоги через столько модельных секунд; 0 — нет
    noise: bool = True


class KnsEmulator:
    def __init__(self, cfg: EmulatorConfig | None = None, plant_params: PlantParams | None = None) -> None:
        self.cfg = cfg or EmulatorConfig()
        self.t = 0.0
        self.rng = random.Random(self.cfg.seed)
        self.events: deque[AlarmEvent] = deque(maxlen=2000)
        self.listeners: list[Callable[[AlarmEvent], None]] = []
        self.tags: tuple[TagDef, ...] = load_tags()
        self.tag_map: dict[str, TagDef] = {t.tag: t for t in self.tags}
        self.devs: dict[str, Device] = {}
        tags_by_dev: dict[str, list[TagDef]] = {}
        for t in self.tags:
            if t.device:
                tags_by_dev.setdefault(t.device, []).append(t)
        for name, (dtype, dev_no, _group) in devices().items():
            dtags = tags_by_dev[name]
            alarms = alarms_of(name)
            dev: Device
            if dtype == "AnalogInput":
                base = AI_CFG.get(name, AiConfig())
                vtag = self.tag_map[f"{name}.Value"]
                limits = {
                    k: v
                    for k, v in (("HH", vtag.alarm_hh), ("H", vtag.alarm_h), ("L", vtag.alarm_l), ("LL", vtag.alarm_ll))
                    if v is not None
                }
                ai_cfg = AiConfig(
                    base.input_type,
                    vtag.eng_min if vtag.eng_min is not None else base.range_lo,
                    vtag.eng_max if vtag.eng_max is not None else base.range_hi,
                    raw_lo=base.raw_lo,
                    raw_hi=base.raw_hi,
                    filter_s=base.filter_s,
                    low_cut_pct=base.low_cut_pct,
                    hyst=base.hyst,
                    limits=limits,
                )
                dev = AnalogInput(name, dev_no, dtags, alarms, self._sink, ai_cfg)
            elif dtype == "DigitalInput":
                dev = DigitalInput(name, dev_no, dtags, alarms, self._sink, DI_CFG.get(name, DiConfig()))
            elif dtype == "MotorVfd":
                dev = MotorVfd(name, dev_no, dtags, alarms, self._sink, PUMP_CFG)
            elif dtype == "Motor":
                dev = Motor(name, dev_no, dtags, alarms, self._sink, FAN_CFG)
            else:
                raise ValueError(f"тип устройства {dtype} не поддерживается эмулятором")
            self.devs[name] = dev
        self.pumps: list[MotorVfd] = [d for d in self.devs.values() if isinstance(d, MotorVfd)]
        self.plant = Plant(seed=self.cfg.seed, params=plant_params or PlantParams(), t0_s=self.cfg.start_hour * 3600)
        self.station = Station(self.devs, StationParams())
        self.scenario = AutoScenario(self.cfg.seed, self.cfg.start_hour * 3600) if self.cfg.auto_faults else None
        self.faults: dict[str, bool] = dict.fromkeys(FAULTS, False)
        self._last_ack_sweep = 0.0
        self._speed_act_hold = [0.0] * len(self.pumps)
        self._speed_ref_hold = [0.0] * len(self.pumps)
        self.scenario_log: deque[ScenarioEvent] = deque(maxlen=200)
        # первый цикл без шага модели: Sts заполнены до первого чтения
        self._apply_inputs()
        self.station.step(0.0, 0.0)
        for d in self.devs.values():
            d.scan(0.0, 0.0)

    # --- события тревог ---------------------------------------------------------------------------
    def _sink(self, ev: AlarmEvent) -> None:
        self.events.append(ev)
        for cb in self.listeners:
            cb(ev)

    # --- отказы -------------------------------------------------------------------------------------
    def inject(self, name: str, on: bool = True) -> None:
        if name in ACTIONS:
            if on and name == "storm":
                self.plant.force_storm()
            return
        if name not in self.faults:
            raise KeyError(f"неизвестный отказ {name!r}")
        self.faults[name] = bool(on)

    def _apply_faults(self) -> None:
        f = self.faults
        pl = self.plant
        for i, pump in enumerate(pl.pumps, start=1):
            pump.vfd_trip = f[f"p{i}_vfd_trip"]
            pump.no_feedback = f[f"p{i}_no_feedback"]
            pump.comm_loss = f[f"p{i}_comm_loss"]
            pump.clog = f[f"p{i}_clog"]
            pump.overheat = f[f"p{i}_overheat"]
            pump.leak = f[f"p{i}_leak"]
            pump.local_switch = f[f"p{i}_local"]
            pump.local_run = f[f"p{i}_local"]
        pl.lt_wire_break = f["lt101_wire_break"]
        pl.ls_high_stuck = True if f["ls102_stuck"] else None
        pl.ls_dry_stuck = True if f["ls103_stuck"] else None
        pl.power_ok = not f["power_loss"]
        pl.ups_fault = f["ups_fault"]
        pl.chamber_flood = f["chamber_flood"]
        pl.door_open_forced = f["door_open"]
        pl.fire = f["fire"]
        pl.h2s_spike = f["h2s_spike"]
        pl.fan_fault = f["fan_fault"]

    # --- входы и выходы -----------------------------------------------------------------------------
    def _n(self, sigma: float) -> float:
        return self.rng.gauss(0.0, sigma) if self.cfg.noise else 0.0

    def _ai(self, tag: str) -> AnalogInput:
        d = self.devs[tag]
        assert isinstance(d, AnalogInput)
        return d

    def _di(self, tag: str) -> DigitalInput:
        d = self.devs[tag]
        assert isinstance(d, DigitalInput)
        return d

    def _apply_inputs(self) -> None:
        pl = self.plant
        self._apply_faults()
        lt = self._ai("LT101")
        lt.r_in = pl.lt101_ma() + (self._n(0.006) if not pl.lt_wire_break else 0.0)
        self._ai("PT201").r_in = pl.to_ma(pl.pressure_bar, 0.0, 10.0) + self._n(0.01)
        self._ai("FT202").r_in = pl.to_ma(pl.outflow_m3h, 0.0, 500.0) + self._n(0.01)
        self._ai("AT401").r_in = pl.to_ma(max(0.0, pl.h2s), 0.0, 40.0) + self._n(0.004)
        self._ai("AT402").r_in = pl.to_ma(max(0.0, pl.ch4), 0.0, 100.0) + self._n(0.004)
        self._ai("TT403").r_in = pl.temp_c + self._n(0.03)
        self._di("LS102").x_in = not pl.float_high()  # НЗ-контакт: сработал — цепь разомкнута
        self._di("LS103").x_in = not pl.float_dry()
        self._di("LS203").x_in = pl.chamber_flood
        self._di("ES301").x_in = pl.power_ok
        self._di("YS302").x_in = not pl.power_ok
        self._di("YS303").x_in = pl.ups_fault
        self._di("ZS404").x_in = pl.door_open_forced
        self._di("YS405").x_in = pl.fire
        self._di("HS501").x_in = False
        self._di("HS502").x_in = False
        for i, (dev, pp) in enumerate(zip(self.pumps, pl.pumps, strict=True)):
            n = i + 1
            it = self._ai(f"IT1{n}1")
            # ток читается по Modbus из ПЧ: при потере связи значение замирает, канал недостоверен
            if not pp.comm_loss:
                it.r_in = round(max(0.0, pp.current_a + self._n(0.08)) * 10.0)
            it.channel_fault = pp.comm_loss
            self._di(f"TS1{n}2").x_in = not pp.overheat
            self._di(f"MS1{n}3").x_in = pp.leak
            dev.fb_run = pp.running_relay
            dev.ext_fault = pp.vfd_trip  # релейный выход «авария ПЧ» (xP10n_FLT)
            dev.local_sel = pp.local_switch
            dev.comm_ok = not pp.comm_loss
            dev.vfd_ready = not pp.vfd_trip
            dev.vfd_fault = pp.vfd_trip
            if not pp.comm_loss:
                self._speed_act_hold[i] = pp.speed_act_pct
                dev.fault_code = pp.fault_code
            dev.speed_act = self._speed_act_hold[i]
        fan = self.devs["V1"]
        assert isinstance(fan, Motor)
        fan.fb_run = pl.fan_running
        fan.ext_fault = pl.fan_fault

    def _apply_outputs(self) -> None:
        pl = self.plant
        for i, (dev, pp) in enumerate(zip(self.pumps, pl.pumps, strict=True)):
            pp.q_run_cmd = dev.q_run
            if not pp.comm_loss:  # задание идёт по Modbus: без связи ПЧ держит последнее
                self._speed_ref_hold[i] = dev.speed_ref
            pp.speed_ref_pct = self._speed_ref_hold[i]
        fan = self.devs["V1"]
        assert isinstance(fan, Motor)
        pl.fan_cmd = fan.q_run

    # --- цикл ---------------------------------------------------------------------------------------
    def step(self, n: int = 1) -> None:
        """n циклов ПЛК по ``cfg.step_s`` модельных секунд."""
        dt = self.cfg.step_s
        for _ in range(n):
            t_prev = self.t
            self.t = round(self.t + dt, 6)
            if self.scenario is not None:
                for ev in self.scenario.due(t_prev, self.t):
                    self._run_event(ev)
            self._apply_inputs()
            self.station.step(self.t, dt)
            for d in self.devs.values():
                d.scan(self.t, dt)
            silence = self._di("HS502").value
            self.station.annunciate(list(self.devs.values()), silence)
            self._apply_outputs()
            self.plant.step(dt)
            if self.cfg.auto_ack_s > 0 and self.t - self._last_ack_sweep >= 60.0:
                self._last_ack_sweep = self.t
                self._auto_ack()

    def run_for(self, seconds: float) -> None:
        self.step(max(1, round(seconds / self.cfg.step_s)))

    def _run_event(self, ev: ScenarioEvent) -> None:
        self.scenario_log.append(ev)
        if ev.kind == "inject":
            self.inject(ev.target, True)
        elif ev.kind == "clear":
            self.inject(ev.target, False)
        elif ev.kind == "command":
            self.write_tag(ev.target, ev.value)

    def _auto_ack(self) -> None:
        """«Диспетчер» квитирует давние тревоги — чтобы на дашборде было видно и квитирование."""
        for dev in self.devs.values():
            mask = 0
            for slot_no, slot in dev.alarms.slots.items():
                if slot.unack:
                    since = next(
                        (
                            e.sim_time_s
                            for e in reversed(self.events)
                            if e.alarm.id == slot.alarm.id and e.reason.name == "ACTIVATED"
                        ),
                        0.0,
                    )
                    if self.t - since >= self.cfg.auto_ack_s:
                        mask |= 1 << slot_no
            if mask and "Cmd.AckReq" in dev.cmd:
                dev.cmd["Cmd.AckReq"] = int(dev.cmd["Cmd.AckReq"]) | mask

    # --- образ и команды ----------------------------------------------------------------------------
    def image(self) -> dict[str, Value]:
        """Текущие значения всех тегов перечня."""
        out: dict[str, Value] = {}
        for dev in self.devs.values():
            out.update(dev.image())
        out["HA1"] = self.station.horn
        out["HL1"] = self.station.lamp
        out["K1"] = self.station.general_alarm
        return out

    def read_tag(self, tag: str) -> Value:
        t = self.tag_map[tag]
        if not t.device:
            return self.image()[tag]
        return self.devs[t.device].image()[tag]

    def write_tag(self, tag: str, value: object) -> Value:
        """Запись в ``GVL_Hmi.st<DEV>Cmd`` (как запись OPC UA или WebVisu).

        Проверяются только тип и диапазон типа IEC: ограничения по смыслу (задание скорости в
        пределах ПЧ, допустимость команды в режиме) применяет «ФБ» в цикле, как в ПЛК.
        """
        t = self.tag_map.get(tag)
        if t is None or not t.writable or not t.device:
            raise CommandError(f"{tag}: не команда (нет в GVL_Hmi или только чтение)")
        coerced = coerce_iec(t.data_type, value)
        self.devs[t.device].cmd[t.key] = coerced
        return coerced

    # --- сводки ------------------------------------------------------------------------------------
    @property
    def sim_hour(self) -> float:
        return ((self.t + self.cfg.start_hour * 3600) % 86400.0) / 3600.0


def coerce_iec(data_type: str, value: object) -> Value:
    """Привести значение к типу IEC с проверкой диапазона; иначе ``CommandError``."""
    if data_type == "BOOL":
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        raise CommandError(f"ожидался BOOL, получено {value!r}")
    if data_type in ("REAL", "LREAL"):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise CommandError(f"ожидалось число, получено {value!r}")
        f = float(value)
        if not math.isfinite(f) or abs(f) > 3.4e38:
            raise CommandError(f"значение {value!r} вне диапазона REAL")
        return f
    if data_type in IEC_INT_RANGES:
        if isinstance(value, bool):
            raise CommandError(f"ожидалось целое, получено {value!r}")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if not isinstance(value, int):
            raise CommandError(f"ожидалось целое, получено {value!r}")
        lo, hi = IEC_INT_RANGES[data_type]
        if not lo <= value <= hi:
            raise CommandError(f"{value} вне диапазона {data_type} [{lo}; {hi}]")
        return value
    raise CommandError(f"тип {data_type} не поддерживается")
