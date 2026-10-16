"""Эмуляция устройств plc-process-lib: то, что SCADA видит в ``stSts`` и пишет в ``GVL_Hmi``.

Это не порт библиотеки, а её поведение «снаружи» в объёме, нужном IIoT-стеку: режимы, команды с
импульсной семантикой (API 2.1), слова состояния и отказов, NE 107, тревоги по слотам, счётчики
моточасов и пусков, рампа задания ПЧ. Карты битов — по API 5.2, 11.5, 12.4, 13.9.

Время — модельное (секунды от старта эмулятора), шаг задаёт вызывающий код. Всё детерминировано:
случайности здесь нет, она только в модели объекта (``plant.py``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar

from .alarms import AlarmBlock, AlarmPriority, EventSink
from .tagmodel import AlarmDef, TagDef

Value = bool | int | float


class DeviceMode(IntEnum):
    """E_DeviceMode."""

    AUTO = 1
    MANUAL = 2
    LOCAL = 3
    OUT_OF_SERVICE = 4


class Ne107(IntEnum):
    """E_Ne107Status."""

    GOOD = 0
    MAINTENANCE_REQUIRED = 1
    OUT_OF_SPECIFICATION = 2
    CHECK_FUNCTION = 3
    FAILURE = 4


class CmdResult(IntEnum):
    """E_CmdResult."""

    NONE = 0
    ACCEPTED = 1
    REJECTED_MODE = 2
    REJECTED_INTERLOCK = 3
    REJECTED_PERMIT = 4
    REJECTED_INHIBIT = 5
    REJECTED_FAULT = 6
    REJECTED_STATE = 7
    REJECTED_NOT_SUPPORTED = 8
    REJECTED_CFG = 9
    SUBST_EXPIRED = 10


class DeviceType(IntEnum):
    """E_DeviceType."""

    NONE = 0
    ANALOG_INPUT = 1
    DIGITAL_INPUT = 2
    MOTOR = 3
    MOTOR_VFD = 4


class MotorState(IntEnum):
    """E_MotorState."""

    STOPPED = 0
    STARTING = 1
    RUNNING = 2
    STOPPING = 3
    FAULT = 4


class AiSignal(IntEnum):
    """E_AiSignalState."""

    GOOD = 0
    UNDER_RANGE = 1
    OVER_RANGE = 2
    FAIL_LOW = 3
    FAIL_HIGH = 4
    CHANNEL_FAULT = 5
    NOT_FINITE = 6


class AiInput(IntEnum):
    """E_AiInputType (используемые в КНС)."""

    MILLIAMP = 0
    ENG = 3
    RAW = 4


# Общий старший байт wStatus (API 5.2)
STS_MODE_AUTO = 0x0100
STS_MODE_MANUAL = 0x0200
STS_MODE_LOCAL = 0x0400
STS_MODE_OOS = 0x0800
STS_CFG_ERROR = 0x1000
STS_FAILURE = 0x2000
STS_WARNING = 0x4000
STS_ALARM_UNACK = 0x8000

NO_FIRST_OUT = 65535
UINT_MAX = 65535
UDINT_MAX = 2**32 - 1
SUBST_MAX_S = 8 * 3600.0  # tSubstMax по умолчанию T#8H

# Порог NE 43, мА (API 11.3; границы 3,6 и 21,0 включены в отказ — сверить с NE 43)
MA_FAIL_LOW = 3.6
MA_UNDER = 3.8
MA_OVER = 20.5
MA_FAIL_HIGH = 21.0
MA_ZERO = 4.0
MA_SPAN = 16.0


def _mode_bits(mode: DeviceMode) -> int:
    return {
        DeviceMode.AUTO: STS_MODE_AUTO,
        DeviceMode.MANUAL: STS_MODE_MANUAL,
        DeviceMode.LOCAL: STS_MODE_LOCAL,
        DeviceMode.OUT_OF_SERVICE: STS_MODE_OOS,
    }[mode]


def command_defaults(tags: list[TagDef]) -> dict[str, Value]:
    """Начальные значения полей ``st<DEV>Cmd`` по типам перечня."""
    out: dict[str, Value] = {}
    for t in tags:
        if not t.writable:
            continue
        out[t.key] = False if t.data_type == "BOOL" else (0.0 if t.data_type in ("REAL", "LREAL") else 0)
    return out


class Device:
    """База: режимы, команды, тревоги, общий заголовок Sts (ST_DeviceSts)."""

    DEV_TYPE = DeviceType.NONE
    LOCAL_SUPPORTED = False
    MANUAL_IS_CHECK = False  # AI/DI: подмена → NE 107 CheckFunction

    def __init__(self, tag: str, dev_no: int, tags: list[TagDef], alarms: list[AlarmDef], sink: EventSink) -> None:
        self.tag = tag
        self.dev_no = dev_no
        self.tags = tags
        self.cmd: dict[str, Value] = command_defaults(tags)
        self.pulse_keys = [t.key for t in tags if t.is_pulse]
        self.mask_keys = [t.key for t in tags if t.is_mask]
        self.alarms = AlarmBlock(alarms, sink)
        self.remote_mode = DeviceMode.AUTO
        self.oos = False
        self.local_sel = False
        self.cmd_result = CmdResult.NONE
        self.cmd_seq = 0
        self.w_fault = 0
        self.w_warning = 0
        self.dev_status = Ne107.GOOD
        self._sts: dict[str, Value] = {}
        self._sts_dirty = True
        self.t = 0.0

    # --- режим ---------------------------------------------------------------------------------
    @property
    def mode(self) -> DeviceMode:
        if self.oos:
            return DeviceMode.OUT_OF_SERVICE
        if self.LOCAL_SUPPORTED and self.local_sel:
            return DeviceMode.LOCAL
        return self.remote_mode

    def _result(self, res: CmdResult) -> None:
        self.cmd_result = res
        self.cmd_seq = (self.cmd_seq + 1) & 0xFFFF

    def _oos_allowed(self) -> bool:
        return True

    def _on_mode_changed(self, old: DeviceMode, new: DeviceMode) -> None:
        """Безударный переход (наследники)."""

    def _switch(self, *, oos: bool | None = None, remote: DeviceMode | None = None) -> None:
        old = self.mode
        if oos is not None:
            self.oos = oos
        if remote is not None:
            self.remote_mode = remote
        new = self.mode
        if new != old:
            self.alarms.set_oos(new == DeviceMode.OUT_OF_SERVICE, self.t)
            self._on_mode_changed(old, new)

    def _process_common(self) -> None:
        c = self.cmd
        if c.get("Cmd.Reset"):
            self._on_reset()
            self.alarms.ack_all(self.t)
        if c.get("Cmd.Ack"):
            self.alarms.ack_all(self.t)
            self._result(CmdResult.ACCEPTED)
        if c.get("Cmd.SetOos"):
            if self.oos:
                self._result(CmdResult.ACCEPTED)
            elif self._oos_allowed():
                self._switch(oos=True)
                self._on_enter_oos()
                self._result(CmdResult.ACCEPTED)
            else:
                self._result(CmdResult.REJECTED_STATE)
        elif c.get("Cmd.SetManual"):
            self._switch(oos=False, remote=DeviceMode.MANUAL)
            self._result(CmdResult.ACCEPTED)
        elif c.get("Cmd.SetAuto"):
            self._switch(oos=False, remote=DeviceMode.AUTO)
            self._result(CmdResult.ACCEPTED)

    def _process_masks(self) -> None:
        c = self.cmd
        for key, fn in (
            ("Cmd.AckReq", self.alarms.ack_mask),
            ("Cmd.ShelveReq", self.alarms.shelve_mask),
            ("Cmd.UnshelveReq", self.alarms.unshelve_mask),
        ):
            mask = int(c.get(key, 0)) & 0xFFFF
            if mask:
                fn(mask, self.t)
                self._result(CmdResult.ACCEPTED)

    def _clear_pulses(self) -> None:
        for key in self.pulse_keys:
            self.cmd[key] = False
        for key in self.mask_keys:
            self.cmd[key] = 0

    def _on_reset(self) -> None:
        self._result(CmdResult.ACCEPTED)

    def _on_enter_oos(self) -> None:
        """Вход в OOS снимает зафиксированные отказы (наследники)."""

    def _process_device_cmds(self) -> None:
        """Команды устройства (наследники)."""

    def _logic(self, dt: float) -> None:
        """Логика устройства (наследники)."""

    def _alarm_conditions(self) -> tuple[dict[int, bool], dict[int, float | None]]:
        return {}, {}

    def _type_status(self) -> int:
        return 0

    def _type_sts(self) -> dict[str, Value]:
        return {}

    # --- цикл ----------------------------------------------------------------------------------
    def scan(self, t: float, dt: float) -> None:
        """Один вызов ФБ: команды → логика → тревоги → Sts; импульсы и маски сброшены."""
        self.t = t
        self._process_common()
        self._process_device_cmds()
        self._process_masks()
        self._clear_pulses()
        self._logic(dt)
        conds, values = self._alarm_conditions()
        self.alarms.update(conds, t, values)
        self._sts_dirty = True  # Sts собирается по запросу (image), а не в каждом цикле

    @property
    def ne107(self) -> Ne107:
        mode_status = Ne107.GOOD
        if self.mode == DeviceMode.OUT_OF_SERVICE or (self.MANUAL_IS_CHECK and self.mode == DeviceMode.MANUAL):
            mode_status = Ne107.CHECK_FUNCTION
        return max(self.dev_status, mode_status)

    def _fill_sts(self) -> None:
        ne = self.ne107
        w_unack = self.alarms.w_unack
        status = self._type_status() & 0x00FF
        status |= _mode_bits(self.mode)
        if ne == Ne107.FAILURE:
            status |= STS_FAILURE
        if self.w_warning or ne in (Ne107.OUT_OF_SPECIFICATION, Ne107.MAINTENANCE_REQUIRED):
            status |= STS_WARNING
        if w_unack:
            status |= STS_ALARM_UNACK
        sts: dict[str, Value] = {
            "Mode": int(self.mode),
            "Ne107": int(ne),
            "Status": status,
            "Fault": self.w_fault & 0xFFFF,
            "Warning": self.w_warning & 0xFFFF,
            "CfgErr": 0,
            "AlmActive": self.alarms.w_active,
            "AlmUnack": w_unack,
            "AlmShelved": self.alarms.w_shelved,
            "PrioUnack": int(self.alarms.prio_unack),
            "CmdResult": int(self.cmd_result),
            "CmdSeq": self.cmd_seq,
            "DevType": int(self.DEV_TYPE),
        }
        sts.update(self._type_sts())
        self._sts = sts
        self._sts_dirty = False

    @property
    def sts(self) -> dict[str, Value]:
        """Поля ``stSts`` (и выходы экземпляра, которые видит SCADA) после последнего цикла."""
        if self._sts_dirty:
            self._fill_sts()
        return self._sts

    @property
    def fault(self) -> bool:
        return self.ne107 == Ne107.FAILURE

    def image(self) -> dict[str, Value]:
        """Значения всех тегов устройства: ``<DEV>.<key>`` → значение."""
        out: dict[str, Value] = {}
        sts = self.sts
        for t in self.tags:
            if t.writable:
                out[t.tag] = self.cmd[t.key]
            elif t.key in sts:
                out[t.tag] = sts[t.key]
        return out


# =================================================================================================
# Аналоговый вход
# =================================================================================================
@dataclass
class AiConfig:
    """Часть ST_AnalogInputCfg, которая нужна эмуляции (значения — из перечня КНС, колонка params)."""

    input_type: AiInput = AiInput.MILLIAMP
    range_lo: float = 0.0
    range_hi: float = 100.0
    raw_lo: float = 0.0
    raw_hi: float = 0.0
    filter_s: float = 0.0
    fail_delay_s: float = 2.0
    low_cut_pct: float = 0.0
    hyst: dict[str, float] = field(default_factory=dict)  # HH/H/L/LL → гистерезис, инж. ед.
    limits: dict[str, float] = field(default_factory=dict)  # включённые уставки


class AnalogInput(Device):
    """FB_AnalogInput: масштабирование, NE 43, фильтр, уставки, подмена (API 11)."""

    DEV_TYPE = DeviceType.ANALOG_INPUT
    MANUAL_IS_CHECK = True
    LIMIT_SLOTS: ClassVar[dict[str, int]] = {"HH": 0, "H": 1, "L": 2, "LL": 3}

    def __init__(
        self, tag: str, dev_no: int, tags: list[TagDef], alarms: list[AlarmDef], sink: EventSink, cfg: AiConfig
    ) -> None:
        super().__init__(tag, dev_no, tags, alarms, sink)
        self.cfg = cfg
        # входы (пишет эмулятор)
        self.r_in = 0.0
        self.channel_fault = False
        self.suppress_limit_alarms = False
        # состояние
        self.value = 0.0
        self.value_pct = 0.0
        self.valid = False
        self.signal = AiSignal.GOOD
        self.flt: float | None = None
        self.last_good = 0.0
        self.fail = False
        self.oor = False
        self._fail_t = 0.0
        self._ok_t = 0.0
        self._oor_t = 0.0
        self._oor_ok_t = 0.0
        self.flags = dict.fromkeys(self.LIMIT_SLOTS, False)
        self.low_cut = False
        self.manual_since: float | None = None

    def _on_mode_changed(self, old: DeviceMode, new: DeviceMode) -> None:
        self.manual_since = self.t if new == DeviceMode.MANUAL else None

    def _classify(self) -> AiSignal:
        x = self.r_in
        if not math.isfinite(x) or abs(x) > 1e30:
            return AiSignal.NOT_FINITE
        if self.channel_fault:
            return AiSignal.CHANNEL_FAULT
        if self.cfg.input_type != AiInput.MILLIAMP:
            return AiSignal.GOOD
        if x <= MA_FAIL_LOW:
            return AiSignal.FAIL_LOW
        if x >= MA_FAIL_HIGH:
            return AiSignal.FAIL_HIGH
        if x < MA_UNDER:
            return AiSignal.UNDER_RANGE
        if x > MA_OVER:
            return AiSignal.OVER_RANGE
        return AiSignal.GOOD

    def _normalize(self) -> float:
        c = self.cfg
        if c.input_type == AiInput.MILLIAMP:
            return (self.r_in - MA_ZERO) / MA_SPAN
        if c.input_type == AiInput.RAW:
            return (self.r_in - c.raw_lo) / (c.raw_hi - c.raw_lo)
        return (self.r_in - c.range_lo) / (c.range_hi - c.range_lo)

    def _confirm(self, raw_fail: bool, raw_oor: bool, dt: float) -> None:
        """Подтверждение отказа и выхода за диапазон с задержкой tFailDelay (вход и выход)."""
        d = self.cfg.fail_delay_s
        self._fail_t = self._fail_t + dt if raw_fail else 0.0
        self._ok_t = self._ok_t + dt if not raw_fail else 0.0
        if not self.fail and self._fail_t >= d - 1e-9:
            self.fail = True
        elif self.fail and self._ok_t >= d - 1e-9:
            self.fail = False
        oor_in = raw_oor and not raw_fail
        self._oor_t = self._oor_t + dt if oor_in else 0.0
        self._oor_ok_t = self._oor_ok_t + dt if not oor_in else 0.0
        if not self.oor and self._oor_t >= d - 1e-9:
            self.oor = True
        elif self.oor and self._oor_ok_t >= d - 1e-9:
            self.oor = False

    def _process_device_cmds(self) -> None:
        pass

    def _logic(self, dt: float) -> None:
        c = self.cfg
        self.signal = self._classify()
        raw_fail = self.signal in (AiSignal.NOT_FINITE, AiSignal.CHANNEL_FAULT, AiSignal.FAIL_LOW, AiSignal.FAIL_HIGH)
        raw_oor = self.signal in (AiSignal.UNDER_RANGE, AiSignal.OVER_RANGE)
        self._confirm(raw_fail, raw_oor, dt)

        eng = None
        self.low_cut = False
        if not raw_fail:
            x = self._normalize()
            if c.low_cut_pct > 0 and x * 100.0 < c.low_cut_pct:
                x = 0.0
                self.low_cut = True
            eng = c.range_lo + x * (c.range_hi - c.range_lo)
            if self.flt is None or c.filter_s <= 0:
                self.flt = eng
            else:
                alpha = 1.0 - math.exp(-dt / c.filter_s)
                self.flt += alpha * (eng - self.flt)
        else:
            self.flt = None  # после отказа фильтр стартует с нового значения

        mode = self.mode
        pending = False
        if mode == DeviceMode.MANUAL:
            self.value = float(self.cmd.get("Cmd.SubstValue", 0.0))
            self.valid = True
        elif mode == DeviceMode.OUT_OF_SERVICE:
            self.valid = False
        else:
            if not raw_fail and self.flt is not None:
                self.value = self.flt
                self.last_good = self.flt
                self.valid = True
            elif not self.fail:
                self.value = self.last_good
                self.valid = True
                pending = True
            else:
                self.value = self.last_good
                self.valid = False
            self.cmd["Cmd.SubstValue"] = self.value  # слежение: подмена включается без рывка
        self._pending = pending
        span = c.range_hi - c.range_lo
        self.value_pct = (self.value - c.range_lo) / span * 100.0 if span else 0.0

        # уставки с гистерезисом; принудительно сняты в OOS и при подтверждённом отказе
        force_off = mode == DeviceMode.OUT_OF_SERVICE or (mode == DeviceMode.AUTO and self.fail)
        for name in self.LIMIT_SLOTS:
            sp = c.limits.get(name)
            if sp is None or force_off:
                self.flags[name] = False
                continue
            hyst = c.hyst.get(name, 0.0)
            high = name in ("HH", "H")
            on = self.flags[name]
            if high:
                on = self.value >= sp if not on else self.value > sp - hyst
            else:
                on = self.value <= sp if not on else self.value < sp + hyst
            self.flags[name] = on

        # подмена по времени
        if mode == DeviceMode.MANUAL and self.manual_since is not None and self.t - self.manual_since >= SUBST_MAX_S:
            self._switch(remote=DeviceMode.AUTO)
            self._result(CmdResult.SUBST_EXPIRED)

        self.dev_status = Ne107.FAILURE if self.fail else (Ne107.OUT_OF_SPECIFICATION if self.oor else Ne107.GOOD)
        self.w_fault = 0
        if self.fail:
            self.w_fault = {
                AiSignal.FAIL_LOW: 0x01,
                AiSignal.FAIL_HIGH: 0x02,
                AiSignal.CHANNEL_FAULT: 0x04,
                AiSignal.NOT_FINITE: 0x08,
            }.get(self.signal, 0)
        self.w_warning = 0
        if self.signal == AiSignal.UNDER_RANGE:
            self.w_warning |= 0x01
        elif self.signal == AiSignal.OVER_RANGE:
            self.w_warning |= 0x02

    def _alarm_conditions(self) -> tuple[dict[int, bool], dict[int, float | None]]:
        suppress = self.suppress_limit_alarms or (self.fail and self.mode == DeviceMode.AUTO)
        conds = {slot: (self.flags[name] and not suppress) for name, slot in self.LIMIT_SLOTS.items()}
        conds[4] = self.fail
        conds[5] = self.oor and not self.fail
        values: dict[int, float | None] = dict.fromkeys(range(6), self.value)
        values[4] = self.r_in
        return conds, values

    def _type_status(self) -> int:
        s = 0
        for bit, name in enumerate(("HH", "H", "L", "LL")):
            if self.flags[name]:
                s |= 1 << bit
        if self.fail:
            s |= 0x10
        if self.oor:
            s |= 0x20
        if getattr(self, "_pending", False):
            s |= 0x40
        if self.low_cut:
            s |= 0x80
        return s

    def _type_sts(self) -> dict[str, Value]:
        remain = 0
        if self.mode == DeviceMode.MANUAL and self.manual_since is not None:
            remain = min(UINT_MAX, math.ceil(max(0.0, SUBST_MAX_S - (self.t - self.manual_since))))
        return {
            "Value": float(self.value),
            "ValuePct": float(self.value_pct),
            "Valid": bool(self.valid),
            "Raw": float(self.r_in) if math.isfinite(self.r_in) else 0.0,
            "Signal": int(self.signal),
            "SubstRemain": remain,
        }


# =================================================================================================
# Дискретный вход
# =================================================================================================
@dataclass
class DiConfig:
    invert: bool = False
    alarm_on_true: bool = True
    fail_value: bool | None = None  # None — удержание (HoldLast)


class DigitalInput(Device):
    """FB_DigitalInput: инверсия, отказ канала, подмена, тревога по состоянию (API 12)."""

    DEV_TYPE = DeviceType.DIGITAL_INPUT
    MANUAL_IS_CHECK = True

    def __init__(
        self, tag: str, dev_no: int, tags: list[TagDef], alarms: list[AlarmDef], sink: EventSink, cfg: DiConfig
    ) -> None:
        super().__init__(tag, dev_no, tags, alarms, sink)
        self.cfg = cfg
        self.x_in = cfg.invert  # контакт в норме: для НЗ-контакта цепь замкнута
        self.channel_fault = False
        self.value = False
        self.raw = False
        self.valid = True
        self.manual_since: float | None = None

    def _on_mode_changed(self, old: DeviceMode, new: DeviceMode) -> None:
        self.manual_since = self.t if new == DeviceMode.MANUAL else None

    def _logic(self, dt: float) -> None:
        self.raw = self.x_in != self.cfg.invert
        mode = self.mode
        if mode == DeviceMode.MANUAL:
            self.value = bool(self.cmd.get("Cmd.SubstValue", False))
            self.valid = True
        elif mode == DeviceMode.OUT_OF_SERVICE:
            self.valid = False
        else:
            if self.channel_fault:
                if self.cfg.fail_value is not None:
                    self.value = self.cfg.fail_value
                self.valid = False
            else:
                self.value = self.raw
                self.valid = True
            self.cmd["Cmd.SubstValue"] = self.value
        if mode == DeviceMode.MANUAL and self.manual_since is not None and self.t - self.manual_since >= SUBST_MAX_S:
            self._switch(remote=DeviceMode.AUTO)
            self._result(CmdResult.SUBST_EXPIRED)
        self.dev_status = Ne107.FAILURE if self.channel_fault and mode != DeviceMode.OUT_OF_SERVICE else Ne107.GOOD
        self.w_fault = 0x01 if self.channel_fault else 0

    @property
    def alarm_cond(self) -> bool:
        return self.value == self.cfg.alarm_on_true

    def _alarm_conditions(self) -> tuple[dict[int, bool], dict[int, float | None]]:
        return {0: self.alarm_cond and not self.channel_fault, 1: self.channel_fault}, {
            0: float(self.value),
            1: float(self.raw),
        }

    def _type_status(self) -> int:
        s = 0
        if self.value:
            s |= 0x01
        if self.raw:
            s |= 0x02
        if self.channel_fault:
            s |= 0x10
        if self.alarm_cond:
            s |= 0x20
        return s

    def _type_sts(self) -> dict[str, Value]:
        remain = 0
        if self.mode == DeviceMode.MANUAL and self.manual_since is not None:
            remain = min(UINT_MAX, math.ceil(max(0.0, SUBST_MAX_S - (self.t - self.manual_since))))
        return {"Value": bool(self.value), "Valid": bool(self.valid), "SubstRemain": remain}


# =================================================================================================
# Двигатель и двигатель с ПЧ
# =================================================================================================
@dataclass
class MotorConfig:
    """Часть ST_MotorCfg и ST_VfdCfg (значения флагмана — перечень КНС, колонка params)."""

    fb_start_s: float = 5.0
    fb_stop_s: float = 5.0
    fb_loss_s: float = 0.5
    ext_fault_s: float = 0.2
    min_stop_s: float = 0.0
    max_starts_per_hour: int = 0
    reset_window_s: float = 3.0
    maint_interval_h: int = 0
    maint_starts: int = 0
    # ПЧ
    speed_min: float = 0.0
    speed_max: float = 100.0
    ramp_up: float = 0.0  # %/с; 0 — без ограничения
    ramp_down: float = 0.0
    comm_loss_is_fault: bool = True
    comm_loss_s: float = 3.0
    speed_dev_pct: float = 10.0
    speed_dev_s: float = 10.0


MOT_FLT_FTS = 0x01
MOT_FLT_FBL = 0x02
MOT_FLT_FTP = 0x04
MOT_FLT_UCR = 0x08
MOT_FLT_EXT = 0x10
MOT_FLT_COMM = 0x20
MOT_LATCHED = MOT_FLT_FTS | MOT_FLT_FBL | MOT_FLT_FTP | MOT_FLT_UCR | MOT_FLT_EXT

MOT_WRN_MAINT_RUNTIME = 0x0001
MOT_WRN_MAINT_STARTS = 0x0002
MOT_WRN_SPEED_DEV = 0x0004
MOT_WRN_STARTS_LIMIT = 0x0008
MOT_WRN_POWER_LOST = 0x0010
MOT_WRN_INTERLOCK_IN_LOCAL = 0x0020
MOT_WRN_COMM_LOSS = 0x0040
MOT_WRN_FB_SUSPENDED = 0x0080


class Motor(Device):
    """FB_Motor: режимы, контроль ОС, блокировки, счётчики (API 13)."""

    DEV_TYPE = DeviceType.MOTOR
    LOCAL_SUPPORTED = True
    IS_VFD = False

    def __init__(
        self, tag: str, dev_no: int, tags: list[TagDef], alarms: list[AlarmDef], sink: EventSink, cfg: MotorConfig
    ) -> None:
        super().__init__(tag, dev_no, tags, alarms, sink)
        self.cfg = cfg
        # входы
        self.auto_run = False
        self.fb_run = False
        self.ext_fault = False
        self.power_ok = True
        self.interlock = 0
        self.permit = 0xFFFF
        self.comm_fault = False  # нефиксируемый отказ связи (наследник)
        self.start_block = False  # ПЧ не готов
        self.ext_fault_add = False  # доп. внешняя авария (наследник: авария ПЧ из слова состояния)
        # выходы и состояние
        self.state = MotorState.STOPPED
        self.manual_latch = False
        self.q_run = False
        self.running = False
        self.latched = 0
        self.first_out = NO_FIRST_OUT
        self._prev_ilk = 0
        self.state_t = 0.0  # время в текущем состоянии
        self.last_stop_t = 0.0  # момент последнего останова (для tMinStop); старт ПЛК — тоже останов
        self.fb_lost_t = 0.0
        self.fb_unc_t = 0.0
        self.ext_t = 0.0
        self.reset_until: float | None = None
        self.run_time_s = 0.0
        self.starts = 0
        self.run_time_maint_s = 0.0
        self.starts_maint = 0
        self.run_current_s = 0.0
        self.start_marks: list[float] = []
        self.entered_starting = False
        self._prev_running = False

    # --- условия ---------------------------------------------------------------------------------
    @property
    def ilk_active(self) -> int:
        return self.interlock & 0xFFFF

    @property
    def permit_missing(self) -> int:
        return (~self.permit) & 0xFFFF

    def inhibit_remain_s(self) -> float:
        remain = max(0.0, self.cfg.min_stop_s - (self.t - self.last_stop_t)) if not self.running else 0.0
        if self.cfg.max_starts_per_hour and len(self.start_marks) >= self.cfg.max_starts_per_hour:
            free_at = self.start_marks[-self.cfg.max_starts_per_hour] + 3600.0
            remain = max(remain, free_at - self.t)
        return remain

    def start_refusal(self) -> CmdResult | None:
        """Причина, по которой пуск сейчас невозможен (по старшинству API 13.5), или None."""
        if self.latched or (self.w_fault & MOT_LATCHED):
            return CmdResult.REJECTED_FAULT
        if self.ilk_active:
            return CmdResult.REJECTED_INTERLOCK
        if self.permit_missing or self.start_block:
            return CmdResult.REJECTED_PERMIT
        if not self.power_ok or self.inhibit_remain_s() > 0:
            return CmdResult.REJECTED_INHIBIT
        return None

    @property
    def available(self) -> bool:
        return (
            self.mode == DeviceMode.AUTO
            and not (self.latched or self.comm_fault)
            and not self.ilk_active
            and self.power_ok
        )

    def _oos_allowed(self) -> bool:
        return self.state not in (MotorState.STARTING, MotorState.RUNNING, MotorState.STOPPING)

    def _on_mode_changed(self, old: DeviceMode, new: DeviceMode) -> None:
        if old == DeviceMode.AUTO and new == DeviceMode.MANUAL:
            self.manual_latch = self.state in (MotorState.STARTING, MotorState.RUNNING)
        elif old in (DeviceMode.LOCAL, DeviceMode.OUT_OF_SERVICE) and new in (DeviceMode.AUTO, DeviceMode.MANUAL):
            self.manual_latch = self.fb_run

    def _on_enter_oos(self) -> None:
        self.latched = 0
        self.first_out = NO_FIRST_OUT

    def _on_reset(self) -> None:
        self.reset_until = self.t + self.cfg.reset_window_s
        self._result(CmdResult.ACCEPTED)

    def _process_device_cmds(self) -> None:
        c = self.cmd
        mode = self.mode
        if c.get("Cmd.Stop"):
            if mode == DeviceMode.AUTO:
                self._switch(remote=DeviceMode.MANUAL)
                self.manual_latch = False
                self._result(CmdResult.ACCEPTED)
            elif mode == DeviceMode.MANUAL:
                self.manual_latch = False
                self._result(CmdResult.ACCEPTED)
            else:
                self._result(CmdResult.REJECTED_MODE)
        elif c.get("Cmd.Start"):
            if mode != DeviceMode.MANUAL:
                self._result(CmdResult.REJECTED_MODE)
            else:
                refusal = self.start_refusal()
                if refusal is None:
                    self.manual_latch = True
                    self._result(CmdResult.ACCEPTED)
                else:
                    self._result(refusal)
        if c.get("Cmd.ResetMaint"):
            self.run_time_maint_s = 0.0
            self.starts_maint = 0
            self._result(CmdResult.ACCEPTED)

    # --- логика ----------------------------------------------------------------------------------
    def _set_state(self, st: MotorState) -> None:
        if st != self.state:
            if st == MotorState.STARTING:
                self.entered_starting = True
                self.start_marks.append(self.t)
            if st in (MotorState.STOPPED, MotorState.FAULT) and self.state in (
                MotorState.RUNNING,
                MotorState.STARTING,
                MotorState.STOPPING,
            ):
                self.last_stop_t = self.t
            self.state = st
            self.state_t = 0.0

    def _pre_logic(self, dt: float) -> None:
        """Точка расширения для ПЧ: до тела двигателя."""

    def _logic(self, dt: float) -> None:
        self.entered_starting = False
        self._pre_logic(dt)
        cfg = self.cfg
        mode = self.mode
        self.state_t += dt
        self.start_marks = [m for m in self.start_marks if self.t - m < 3600.0]

        # блокировка: первопричина
        ilk = self.ilk_active
        new_bits = ilk & ~self._prev_ilk
        if self._prev_ilk == 0 and ilk:
            self.first_out = (new_bits & -new_bits).bit_length() - 1
        self._prev_ilk = ilk

        # внешняя авария (кроме OOS) — фиксируется
        ext = self.ext_fault or self.ext_fault_add
        if ext and mode != DeviceMode.OUT_OF_SERVICE:
            self.ext_t += dt
            if self.ext_t >= cfg.ext_fault_s - 1e-9:
                self.latched |= MOT_FLT_EXT
        else:
            self.ext_t = 0.0

        # Reset: в окне снимаются отказы, причина которых ушла
        if self.reset_until is not None:
            if not ext:
                self.latched &= ~MOT_FLT_EXT
            if not self.fb_run:
                self.latched &= ~(MOT_FLT_FTP | MOT_FLT_UCR)
            self.latched &= ~(MOT_FLT_FTS | MOT_FLT_FBL)
            if self.t >= self.reset_until:
                self.reset_until = None
                if self.latched:
                    self._result(CmdResult.REJECTED_FAULT)

        # запрос работы
        if mode == DeviceMode.AUTO:
            request = self.auto_run
        elif mode == DeviceMode.MANUAL:
            request = self.manual_latch
        else:
            request = False
        if ilk and mode in (DeviceMode.AUTO, DeviceMode.MANUAL):
            request = False
            self.manual_latch = False
        if not self.power_ok:
            self.manual_latch = False

        fb = self.fb_run
        fault_now = bool(self.latched) or self.comm_fault
        st = self.state

        if mode in (DeviceMode.LOCAL, DeviceMode.OUT_OF_SERVICE):
            # ПЛК выходами не управляет, состояние следует ОС
            self.q_run = False
            if self.latched & MOT_FLT_EXT and mode == DeviceMode.LOCAL:
                self._set_state(MotorState.FAULT)
            else:
                self._set_state(MotorState.RUNNING if fb else MotorState.STOPPED)
        elif not self.power_ok:
            if st in (MotorState.RUNNING, MotorState.STARTING, MotorState.STOPPING):
                self._set_state(MotorState.STOPPED)
                self.last_stop_t = self.t
            elif st == MotorState.FAULT and not fault_now:
                self._set_state(MotorState.STOPPED)
            self.q_run = False
        elif fault_now:
            if st != MotorState.FAULT:
                self.manual_latch = False
                self._set_state(MotorState.FAULT)
            self.q_run = False
        else:
            if st == MotorState.FAULT:
                # отказы сняты (Reset) или связь восстановлена: состояние по ОС
                if fb:
                    self._set_state(MotorState.RUNNING if request else MotorState.STOPPING)
                else:
                    self._set_state(MotorState.STOPPED)
                st = self.state
            if st == MotorState.STOPPED:
                if request and self.start_refusal() is None:
                    self._set_state(MotorState.STARTING)
                elif fb and not request:
                    self.fb_unc_t += dt
                    if self.fb_unc_t >= cfg.fb_start_s:
                        self.latched |= MOT_FLT_UCR
                if not fb:
                    self.fb_unc_t = 0.0
            elif st == MotorState.STARTING:
                if not request:
                    self._set_state(MotorState.STOPPING)
                elif fb:
                    self._set_state(MotorState.RUNNING)
                elif self.state_t >= cfg.fb_start_s:
                    self.latched |= MOT_FLT_FTS
            elif st == MotorState.RUNNING:
                if not request:
                    self._set_state(MotorState.STOPPING)
                elif not fb:
                    self.fb_lost_t += dt
                    if self.fb_lost_t >= cfg.fb_loss_s:
                        self.latched |= MOT_FLT_FBL
                else:
                    self.fb_lost_t = 0.0
            elif st == MotorState.STOPPING:
                if not fb:
                    self._set_state(MotorState.STOPPED)
                elif request:
                    self._set_state(MotorState.RUNNING)
                elif self.state_t >= cfg.fb_stop_s:
                    self.latched |= MOT_FLT_FTP
            if self.latched:
                self.manual_latch = False
                self._set_state(MotorState.FAULT)
            self.q_run = self.state in (MotorState.STARTING, MotorState.RUNNING)

        # счётчики: по ОС в любом режиме
        self.running = fb
        if self.running:
            if not self._prev_running:
                self.starts += 1
                self.starts_maint += 1
                self.run_current_s = 0.0
                if self.state != MotorState.STARTING and mode in (DeviceMode.LOCAL, DeviceMode.OUT_OF_SERVICE):
                    self.start_marks.append(self.t)  # пуск по месту тоже даёт пусковой ток
            self.run_time_s += dt
            self.run_time_maint_s += dt
            self.run_current_s += dt
        else:
            self.run_current_s = 0.0
        self._prev_running = self.running
        self._post_logic(dt)
        self._status_words()

    def _post_logic(self, dt: float) -> None:
        """Точка расширения для ПЧ: после тела двигателя."""

    def _status_words(self) -> None:
        cfg = self.cfg
        self.w_fault = self.latched | (MOT_FLT_COMM if self.comm_fault else 0)
        w = getattr(self, "w_warning_add", 0)
        if cfg.maint_interval_h and self.run_time_maint_s >= cfg.maint_interval_h * 3600:
            w |= MOT_WRN_MAINT_RUNTIME
        if cfg.maint_starts and self.starts_maint >= cfg.maint_starts:
            w |= MOT_WRN_MAINT_STARTS
        if cfg.max_starts_per_hour and len(self.start_marks) >= cfg.max_starts_per_hour:
            w |= MOT_WRN_STARTS_LIMIT
        if not self.power_ok:
            w |= MOT_WRN_POWER_LOST
        if self.mode == DeviceMode.LOCAL and self.ilk_active:
            w |= MOT_WRN_INTERLOCK_IN_LOCAL
        self.w_warning = w
        dev = Ne107.GOOD
        if w & (MOT_WRN_MAINT_RUNTIME | MOT_WRN_MAINT_STARTS):
            dev = Ne107.MAINTENANCE_REQUIRED
        dev = max(dev, getattr(self, "dev_status_add", Ne107.GOOD))
        if self.w_fault:
            dev = Ne107.FAILURE
        self.dev_status = dev

    def _alarm_conditions(self) -> tuple[dict[int, bool], dict[int, float | None]]:
        f = self.w_fault
        return {
            0: bool(f & MOT_FLT_FTS),
            1: bool(f & MOT_FLT_FBL),
            2: bool(f & MOT_FLT_FTP),
            3: bool(f & MOT_FLT_UCR),
            4: bool(f & MOT_FLT_EXT),
        }, {}

    def _type_status(self) -> int:
        s = 0
        if self.running:
            s |= 0x01
        if self.state in (MotorState.STARTING, MotorState.RUNNING):
            s |= 0x02
        if self.state == MotorState.STARTING:
            s |= 0x04
        if self.state == MotorState.STOPPING:
            s |= 0x08
        if self.ilk_active:
            s |= 0x10
        if self.permit_missing or self.start_block:
            s |= 0x20
        if not self.running and (self.inhibit_remain_s() > 0 or not self.power_ok):
            s |= 0x40
        if self.available:
            s |= 0x80
        return s

    def _type_sts(self) -> dict[str, Value]:
        return {
            "Running": bool(self.running),
            "State": int(self.state),
            "Interlock": self.ilk_active,
            "PermitMissing": self.permit_missing,
            "FirstOut": self.first_out,
            "InhibitRemain": min(UINT_MAX, math.ceil(self.inhibit_remain_s())),
            "StartsLastHour": min(UINT_MAX, len(self.start_marks)),
            "RunTime": self.run_time_s / 3600.0,
            "Starts": min(UDINT_MAX, self.starts),
            "RunTimeMaint": self.run_time_maint_s / 3600.0,
            "StartsMaint": min(UDINT_MAX, self.starts_maint),
            "RunCurrent": min(UDINT_MAX, int(self.run_current_s)),
        }


class MotorVfd(Motor):
    """FB_MotorVfd: задание скорости с рампой, связь с ПЧ, рассогласование (API 14)."""

    DEV_TYPE = DeviceType.MOTOR_VFD
    IS_VFD = True

    def __init__(
        self, tag: str, dev_no: int, tags: list[TagDef], alarms: list[AlarmDef], sink: EventSink, cfg: MotorConfig
    ) -> None:
        super().__init__(tag, dev_no, tags, alarms, sink, cfg)
        self.speed_sp_auto = 0.0
        self.comm_ok = True
        self.vfd_ready = True
        self.vfd_fault = False
        self.speed_act = 0.0
        self.speed_ref = 0.0
        self.fault_code = 0  # GVL_IO.uiP10n_FCODE: код последней аварии ПЧ
        self.comm_loss_t = 0.0
        self.comm_loss = False
        self.speed_dev_t = 0.0
        self.speed_dev = False
        self.w_warning_add = 0
        self.dev_status_add = Ne107.GOOD
        self.cmd.setdefault("Cmd.SpeedSp", 0.0)

    @property
    def speed_auto_active(self) -> bool:
        return self.mode == DeviceMode.AUTO and self.state == MotorState.RUNNING and self.w_fault == 0

    def _pre_logic(self, dt: float) -> None:
        cfg = self.cfg
        comm_valid = self.comm_ok and math.isfinite(self.speed_act)
        self.comm_loss_t = self.comm_loss_t + dt if not comm_valid else 0.0
        self.comm_loss = self.comm_loss_t >= cfg.comm_loss_s - 1e-9
        self.comm_fault = self.comm_loss and cfg.comm_loss_is_fault
        self.start_block = comm_valid and not self.vfd_ready
        # авария ПЧ: релейный выход заведён в xExtFault; слово состояния — только при связи
        self.ext_fault_add = self.vfd_fault and comm_valid
        w = 0
        if self.comm_loss and not cfg.comm_loss_is_fault:
            w |= MOT_WRN_COMM_LOSS
        if self.speed_dev:
            w |= MOT_WRN_SPEED_DEV
        self.w_warning_add = w
        dev = Ne107.GOOD
        if w & (MOT_WRN_COMM_LOSS | MOT_WRN_SPEED_DEV):
            dev = Ne107.OUT_OF_SPECIFICATION
        self.dev_status_add = dev

    def _post_logic(self, dt: float) -> None:
        cfg = self.cfg
        mode = self.mode
        lo, hi = cfg.speed_min, cfg.speed_max
        if mode == DeviceMode.AUTO:
            target = self.speed_sp_auto
            if math.isfinite(target):
                self.cmd["Cmd.SpeedSp"] = min(hi, max(lo, target))
        elif mode == DeviceMode.MANUAL:
            sp = float(self.cmd.get("Cmd.SpeedSp", lo))
            target = min(hi, max(lo, sp)) if math.isfinite(sp) else self.speed_ref
            self.cmd["Cmd.SpeedSp"] = target
        else:
            target = self.speed_act
            self.cmd["Cmd.SpeedSp"] = float(self.speed_act)
        if self.state in (MotorState.STARTING, MotorState.RUNNING):
            goal = min(hi, max(lo, target)) if math.isfinite(target) else self.speed_ref
            if self.entered_starting:
                self.speed_ref = lo
            if self.comm_loss:
                pass  # связь потеряна: задание удерживается
            elif goal > self.speed_ref:
                step = cfg.ramp_up * dt if cfg.ramp_up > 0 else goal - self.speed_ref
                self.speed_ref = min(goal, self.speed_ref + step)
            else:
                step = cfg.ramp_down * dt if cfg.ramp_down > 0 else self.speed_ref - goal
                self.speed_ref = max(goal, self.speed_ref - step)
            ramp_done = abs(self.speed_ref - goal) < 1e-6
        else:
            self.speed_ref = 0.0
            ramp_done = True
        dev_cond = (
            cfg.speed_dev_pct > 0
            and self.state == MotorState.RUNNING
            and ramp_done
            and not self.comm_loss
            and abs(self.speed_ref - self.speed_act) > cfg.speed_dev_pct
        )
        self.speed_dev_t = self.speed_dev_t + dt if dev_cond else 0.0
        self.speed_dev = self.speed_dev_t >= cfg.speed_dev_s

    def _alarm_conditions(self) -> tuple[dict[int, bool], dict[int, float | None]]:
        conds, values = super()._alarm_conditions()
        conds[6] = self.comm_loss
        conds[7] = self.speed_dev
        values[7] = self.speed_act
        return conds, values

    def _type_sts(self) -> dict[str, Value]:
        sts = super()._type_sts()
        sts.update(
            {
                "SpeedRef": float(self.speed_ref),
                "SpeedAct": float(self.speed_act) if math.isfinite(self.speed_act) else 0.0,
                "SpeedAutoActive": bool(self.speed_auto_active),
                f"{self.tag}_FCODE": int(self.fault_code) & 0xFFFF,
            }
        )
        return sts


def any_unack(devs: list[Device], min_priority: AlarmPriority = AlarmPriority.LOW) -> bool:
    return any(s.unack and s.priority >= min_priority for d in devs for s in d.alarms.slots.values())
