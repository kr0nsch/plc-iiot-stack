"""Станция KNS1 и регулятор уровня LIC101 эмулятора — теги ``GVL_Station`` флагмана.

Флагман публикует состояние станции в ``GVL_Station.stStationSts``, принимает команды в
``stStationCmd`` и ведёт регулятор уровня ``fbLIC101`` (``PL.FB_PID``) с командами ``stLIC101Cmd``
(DESIGN 3.1, 4.1 флагмана). Эмулятор показывает те же теги (``station_tags.csv``) поверх своей логики
станции (``station.py``):

- ``StationDevice`` (KNS1) — режим, способ, действующее управление, число насосов, ведущий насос,
  уровень, задания, слово состояния и 13 тревог станции ``KNS1.*`` (бит ``slot - 1``); команды
  ``SetAuto``, ``SetManual``, ``SetStepped``, ``SetLevelPid``, ``AckAll``, ``ResetAll``, ``Silence``,
  маски и номера тревог; каждая обработанная команда увеличивает ``uiCmdSeq``;
- ``LevelController`` (LIC101) — режим Auto/Manual, PV (уровень), задание, выход. Составляющие ПИД
  эмулятор не считает: регулирование изображается пропорциональным заданием частоты (``station.py``).

Тревога LDEV (поплавок против уровнемера) и SIM (режим имитации флагмана) в эмуляторе не возникают.
"""

from __future__ import annotations

from .alarms import AlarmPriority, EventSink
from .devices import CmdResult, Device, DeviceMode, DeviceType, Ne107, Value
from .station import (
    ACT_LEVEL_PID,
    METHOD_LEVEL_PID,
    METHOD_STEPPED,
    MODE_AUTO,
    MODE_MANUAL,
    ST_ATS,
    ST_COMMON_ALARM,
    ST_DRY_RUN,
    ST_EMERGENCY,
    ST_FLOAT,
    ST_HORN,
    ST_LACK,
    ST_NO_RESERVE,
    ST_POWER_LOST,
    ST_RESTART,
    ST_STEP_FALLBACK,
    ST_UNACK,
    Station,
)
from .tagmodel import AlarmDef, TagDef

UNDERLOAD_SUFFIX = {"P101": "UL1", "P102": "UL2", "P103": "UL3"}
LEVEL_RANGE_M = 5.0  # шкала LT101: ошибка LIC101 — в % этого диапазона
PID_SAMPLE_MS = 500.0  # tSample LIC101 флагмана


class StationDevice(Device):
    """KNS1: ``GVL_Station.stStationSts`` и ``stStationCmd``."""

    def __init__(
        self, tags: list[TagDef], alarms: list[AlarmDef], sink: EventSink, station: Station, devs: dict[str, Device]
    ) -> None:
        super().__init__("KNS1", 0, tags, alarms, sink)
        self.station = station
        self.devs = devs  # все источники тревог (устройства, LIC101, станция) — для AckAll, ResetAll и номеров
        self.bit_of = {a.code.split(".", 1)[1]: a.bit for a in alarms}
        self.id_keys = [t.key for t in tags if t.writable and t.data_type == "UDINT"]

    def _accept(self) -> None:
        self._result(CmdResult.ACCEPTED)

    def _process_common(self) -> None:
        c, st = self.cmd, self.station
        if c.get("Cmd.SetManual"):  # «Ручной» старше «Автомата»
            st.mode = MODE_MANUAL
            self._accept()
        elif c.get("Cmd.SetAuto"):
            st.mode = MODE_AUTO
            self._accept()
        if c.get("Cmd.SetStepped"):  # «ступенчатое» старше «ПИД уровня»
            st.method = METHOD_STEPPED
            self._accept()
        elif c.get("Cmd.SetLevelPid"):
            st.method = METHOD_LEVEL_PID
            self._accept()
        if c.get("Cmd.ResetAll"):  # как кнопка HS501: сброс всех устройств и квитирование станции
            for dev in self.devs.values():
                if dev is not self and "Cmd.Reset" in dev.cmd:
                    dev.cmd["Cmd.Reset"] = True
            self.alarms.ack_all(self.t)
            self._accept()
        if c.get("Cmd.AckAll"):
            for dev in self.devs.values():
                dev.alarms.ack_all(self.t)
            self._accept()
        if c.get("Cmd.Silence"):
            st.silence_req = True
            self._accept()
        if c.get("Cmd.ExportLog") or c.get("Cmd.RevertCfg"):
            self._result(CmdResult.REJECTED_NOT_SUPPORTED)  # журнала и уставок станции в эмуляторе нет
        for key, action in (("Cmd.AckId", "ack"), ("Cmd.ShelveId", "shelve"), ("Cmd.UnshelveId", "unshelve")):
            alarm_id = int(c.get(key, 0))
            if alarm_id:
                self._by_id(alarm_id, action)
        for key in self.id_keys:  # номера сбрасываются в 0 (DESIGN 3.1 флагмана)
            c[key] = 0

    def _by_id(self, alarm_id: int, action: str) -> None:
        if any(dev.alarms.by_id(alarm_id, action, self.t) for dev in self.devs.values()):
            self._accept()
        else:
            self._result(CmdResult.REJECTED_STATE)  # нет тревоги с таким номером

    def _alarm_conditions(self) -> tuple[dict[int, bool], dict[int, float | None]]:
        st = self.station
        s = st.state
        conds = {
            "EHL": s.emergency,
            "DRY": s.dry_run,
            "LACK": st.lack,
            "NORES": st.no_reserve,
            "ATS": bool(st.ats_pumps),
            "FLOAT": s.degraded,
            "STEP": st.step_fallback,
            "NOAUTO": st.mode == MODE_MANUAL,
        }
        for pump, suffix in UNDERLOAD_SUFFIX.items():
            conds[suffix] = st.underload.get(pump, False)
        return {self.bit_of[k]: v for k, v in conds.items() if k in self.bit_of}, {}

    @property
    def state_word(self) -> int:
        st = self.station
        s = st.state
        flags = (
            (s.dry_run, ST_DRY_RUN),
            (s.emergency, ST_EMERGENCY),
            (s.degraded, ST_FLOAT),
            (st.step_fallback, ST_STEP_FALLBACK),
            (not s.power_ok, ST_POWER_LOST),
            (st.restart, ST_RESTART),
            (bool(st.ats_pumps), ST_ATS),
            (st.no_reserve, ST_NO_RESERVE),
            (st.lack, ST_LACK),
            (st.horn, ST_HORN),
            (st.general_alarm, ST_COMMON_ALARM),
            (st.any_unack, ST_UNACK),
        )
        return sum(bit for on, bit in flags if on)

    @property
    def ne107(self) -> Ne107:
        """Станция: F — LACK; S — FLOAT, STEP, NORES; C — «Ручной» (04 §19.3 флагмана)."""
        st = self.station
        if st.lack:
            return Ne107.FAILURE
        if st.state.degraded or st.step_fallback or st.no_reserve:
            return Ne107.OUT_OF_SPECIFICATION
        if st.mode == MODE_MANUAL:
            return Ne107.CHECK_FUNCTION
        return Ne107.GOOD

    @property
    def fault(self) -> bool:
        return False  # отказ станции — тревоги KNS1.*, а не общий отказ устройства

    def _lead(self) -> int:
        for idx, pump in enumerate(self.station.pumps, start=1):
            if self.station.state.roles.get(pump.tag) == "duty":
                return idx
        return 0

    def _fill_sts(self) -> None:
        st = self.station
        pumps = st.pumps
        prio = max((d.alarms.prio_unack for d in self.devs.values()), default=AlarmPriority.NONE)
        self._sts = {
            "Mode": st.mode,
            "Method": st.method,
            "ControlAct": st.control_act,
            "Ne107": int(self.ne107),
            "State": self.state_word,
            "CfgErr": 0,
            "PumpsRequired": st.state.n_required,
            "PumpsRunning": sum(1 for p in pumps if p.running),
            "PumpsAvailable": sum(1 for p in pumps if p.available and not p.fault and p.mode == DeviceMode.AUTO),
            "LeadPump": self._lead(),
            "SeqRemain": st.seq_remain_s,
            "CmdResult": int(self.cmd_result),
            "CmdSeq": self.cmd_seq,
            "AlmActive": self.alarms.w_active,
            "AlmUnack": self.alarms.w_unack,
            "AlmShelved": self.alarms.w_shelved,
            "PrioUnack": int(prio),
            "LogExport": 0,
            "Level": float(st.level_m),
            "LevelSp": float(st.p.level_sp_m),
            "SpeedSp": float(st.speed_sp),
            "EventSeq": 0,
            "LogOverwritten": 0,
        }
        self._sts_dirty = False


class LevelController(Device):
    """LIC101: ``GVL_Station.fbLIC101.stSts`` и ``stLIC101Cmd`` (режим Auto/Manual, PV, задание, выход)."""

    DEV_TYPE = DeviceType.PID

    def __init__(self, tags: list[TagDef], sink: EventSink, station: Station, level: Device) -> None:
        super().__init__("LIC101", 0, tags, [], sink)
        self.station = station
        self.level = level
        self.pv = 0.0

    def _logic(self, dt: float) -> None:
        st = self.station
        self.pv = float(getattr(self.level, "value", 0.0))
        self.dev_status = Ne107.GOOD if getattr(self.level, "valid", True) else Ne107.FAILURE
        if self.mode == DeviceMode.MANUAL:
            out = float(self.cmd.get("Cmd.ManualOut", 0.0))
            st.lic_manual_out = min(100.0, max(0.0, out))
        else:
            st.lic_manual_out = None
            self.cmd["Cmd.ManualOut"] = float(st.speed_sp)  # слежение: переход в Manual без рывка
        self.cmd["Cmd.Sp"] = float(st.p.level_sp_m)  # внешнее задание станции (xSpExt)

    def _type_sts(self) -> dict[str, Value]:
        st = self.station
        sp = float(st.p.level_sp_m)
        active = st.control_act == ACT_LEVEL_PID
        return {
            "SpTarget": sp,
            "Sp": sp,
            "Pv": self.pv,
            "Err": (self.pv - sp) / LEVEL_RANGE_M * 100.0,  # прямое действие: уровень выше задания — больше выход
            "Out": float(st.speed_sp),
            "P": 0.0,
            "I": 0.0,
            "D": 0.0,
            "Dt": PID_SAMPLE_MS if active else 0.0,
        }
