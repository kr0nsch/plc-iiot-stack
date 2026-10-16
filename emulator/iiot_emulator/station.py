"""Логика станции КНС-1 в эмуляторе: то, что в проекте 02 делает ручной код поверх устройств.

Упрощённо, но по алгоритмам флагмана (02-flagship-pump-station.md, «Алгоритмы»):

- **Регулирование уровня:** ведущий насос пускается на уровне пуска и останавливается на уровне
  останова; частота работающих насосов растёт с уровнем (пропорционально, от ``speed_min`` до
  100 %); второй насос подключается, когда первый на максимуме и уровень выше уровня подключения,
  и отключается с гистерезисом.
- **Роли:** ведущий (duty), второй (assist) и резервный (standby). При каждом новом пуске
  выбирается доступный насос с наименьшими моточасами; ограничение непрерывной работы ведущего —
  смена насоса без остановки откачки.
- **АВР:** отказ запрошенного насоса (Fault, потеря доступности) — запрос переходит к следующему
  доступному насосу.
- **Защиты:** сухой ход (поплавок LS103 или LL уровнемера) — блокировка всех насосов;
  аварийно высокий уровень (HH или поплавок LS102) — пуск всех исправных; отказ уровнемера
  (NE 43) — деградированный режим по поплавкам; перегрев обмотки — блокировка насоса.
- **Питание:** пропадание — насосы стоят без отказа; восстановление — последовательный пуск с
  задержкой.
- Вентилятор павильона, сирена, лампа и реле общей аварии.

Уставки станции — допущения эмулятора (флагман задаст свои в ``04_algorithms.md``); уставки
тревог устройств — из перечня сигналов.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .alarms import AlarmPriority
from .devices import AnalogInput, Device, DeviceMode, DigitalInput, Motor, MotorState, MotorVfd


@dataclass(frozen=True)
class StationParams:
    lead_start_m: float = 1.8
    stop_all_m: float = 0.9
    assist_start_m: float = 2.6
    assist_stop_m: float = 1.5
    assist_delay_s: float = 20.0
    speed_lo_level_m: float = 0.9  # на этом уровне — минимальная скорость
    speed_hi_level_m: float = 2.4  # на этом уровне — 100 %
    emergency_release_m: float = 3.2  # выход из «пуска всех» после HH
    max_continuous_run_h: float = 6.0
    restart_delay_s: float = 10.0
    fan_period_s: float = 3600.0  # плановое проветривание: каждый час
    fan_on_s: float = 600.0  # на 10 минут
    fan_hold_s: float = 900.0  # по газу или температуре — не меньше 15 минут


ROLE_DUTY = "duty"
ROLE_ASSIST = "assist"
ROLE_STANDBY = "standby"


@dataclass
class StationState:
    """Состояние станции для телеметрии (в адресном пространстве ПЛК этих тегов нет)."""

    n_required: int = 0
    emergency: bool = False
    degraded: bool = False
    dry_run: bool = False
    power_ok: bool = True
    roles: dict[str, str] = field(default_factory=dict)  # P101 → duty/assist/standby
    requested: list[str] = field(default_factory=list)
    transfers: int = 0  # переходов АВР с начала работы
    rotations: int = 0


class Station:
    def __init__(self, devs: dict[str, Device], params: StationParams | None = None) -> None:
        self.p = params or StationParams()
        self.devs = devs
        self.pumps: list[MotorVfd] = [d for d in devs.values() if isinstance(d, MotorVfd)]
        fan = devs.get("V1")
        self.fan: Motor | None = fan if isinstance(fan, Motor) else None
        self.state = StationState()
        self._requested: list[MotorVfd] = []
        self._assist_t = 0.0
        self._release_t: float | None = None
        self._released = len(self.pumps)
        self._prev_power = True
        self._rotating: MotorVfd | None = None
        self.horn = False
        self.lamp = False
        self.general_alarm = False
        self._prev_unack_ids: set[int] = set()
        self._fan_hold_until = -1.0

    def _ai(self, tag: str) -> AnalogInput:
        dev = self.devs[tag]
        assert isinstance(dev, AnalogInput)
        return dev

    def _di(self, tag: str) -> DigitalInput:
        dev = self.devs[tag]
        assert isinstance(dev, DigitalInput)
        return dev

    @staticmethod
    def _hours(p: MotorVfd) -> float:
        return p.run_time_s

    def _usable(self, p: MotorVfd) -> bool:
        return p.available and p.state != MotorState.FAULT

    def step(self, t: float, dt: float) -> None:
        p = self.p
        lt = self._ai("LT101")
        ls_high = self._di("LS102").value
        ls_dry = self._di("LS103").value
        power = self._di("ES301").value
        st = self.state

        # --- питание: последовательный пуск после восстановления (окончание — ниже) -----------------
        restored = power and not self._prev_power
        if not power:
            self._released = 0
            self._release_t = None
        elif restored:
            self._released = 1  # первый насос — сразу (с учётом tMinStop в ФБ)
            self._release_t = None
        self._prev_power = power
        st.power_ok = power

        # --- защиты --------------------------------------------------------------------------------
        level_valid = lt.valid
        level = lt.value
        st.degraded = not level_valid
        st.dry_run = bool(ls_dry or (level_valid and lt.flags["LL"]))
        for idx, pump in enumerate(self.pumps):
            ilk = 0
            if st.dry_run:
                ilk |= 0x0001  # wInterlock.0 — сухой ход
            ts = self.devs.get(f"TS1{idx + 1}2")
            if isinstance(ts, DigitalInput) and ts.value:
                ilk |= 0x0002  # wInterlock.1 — перегрев обмотки
            pump.interlock = ilk
            pump.power_ok = power

        # --- требуемое число насосов -------------------------------------------------------------
        n = st.n_required
        if st.degraded:
            if ls_high:
                n = len(self.pumps)
                st.emergency = True
            elif ls_dry:
                n = 0
                st.emergency = False
            elif n == 0 and not ls_dry:
                n = 0
        else:
            if lt.flags["HH"] or ls_high:
                st.emergency = True
            elif st.emergency and level < p.emergency_release_m:
                st.emergency = False
                n = min(n, 2)
            if st.emergency:
                n = len(self.pumps)
            else:
                if n == 0 and level >= p.lead_start_m:
                    n = 1
                elif n >= 1 and level <= p.stop_all_m:
                    n = 0
                lead_at_max = (
                    bool(self._requested) and self._requested[0].speed_ref >= self._requested[0].cfg.speed_max - 0.5
                )
                if n == 1 and lead_at_max and level >= p.assist_start_m:
                    self._assist_t += dt
                    if self._assist_t >= p.assist_delay_s:
                        n = 2
                else:
                    self._assist_t = 0.0
                if n >= 2 and level <= p.assist_stop_m:
                    n = 1
        if st.dry_run:
            n = 0
        st.n_required = n

        # --- выбор насосов: АВР, чередование по моточасам, ограничение непрерывной работы -----------
        failed = [q for q in self._requested if q.state == MotorState.FAULT]
        self._requested = [q for q in self._requested if self._usable(q)]
        if failed and n > 0:
            st.transfers += len(failed)  # АВР: запрос отказавшего насоса переходит к следующему
        if self._rotating is not None and self._rotating not in self._requested:
            self._rotating = None
        keep = n + (1 if self._rotating is not None else 0)
        while len(self._requested) > keep:
            # первым останавливается последний подключённый (но не насос, принимающий смену)
            victim = next(q for q in reversed(self._requested) if q is not self._rotating)
            self._requested.remove(victim)
        candidates = sorted((q for q in self.pumps if self._usable(q) and q not in self._requested), key=self._hours)
        while len(self._requested) < n and candidates:
            self._requested.append(candidates.pop(0))
        # смена ведущего по ограничению непрерывной работы
        if self._requested and n < len(self.pumps):
            lead = self._requested[0]
            if self._rotating is None and lead.run_current_s >= p.max_continuous_run_h * 3600 and candidates:
                self._rotating = candidates[0]
                self._requested.append(self._rotating)
            elif self._rotating is not None:
                if self._rotating.state == MotorState.RUNNING:
                    # новый ведущий в работе: старый останавливается, откачка не прерывается
                    self._requested.remove(lead)
                    self._requested.remove(self._rotating)
                    self._requested.insert(0, self._rotating)
                    self._rotating = None
                    st.rotations += 1
                elif not self._usable(self._rotating):
                    self._requested.remove(self._rotating)
                    self._rotating = None
        elif self._rotating is not None:
            self._rotating = None

        # следующий насос — через restart_delay_s после того, как предыдущие вышли в работу
        if power and self._released < len(self.pumps):
            head = self._requested[: self._released]
            if all(q.state == MotorState.RUNNING for q in head):
                if len(self._requested) <= self._released:
                    self._released = len(self.pumps)  # спрос покрыт — последовательность закончена
                elif self._release_t is None:
                    self._release_t = t
                elif t - self._release_t >= p.restart_delay_s:
                    self._released += 1
                    self._release_t = None

        # --- задание скорости и запросы ----------------------------------------------------------
        if st.degraded or st.emergency:
            speed = 100.0
        else:
            span = max(1e-6, p.speed_hi_level_m - p.speed_lo_level_m)
            frac = min(1.0, max(0.0, (level - p.speed_lo_level_m) / span))
            lo = self.pumps[0].cfg.speed_min if self.pumps else 0.0
            speed = lo + (100.0 - lo) * frac
        allowed = set(self._requested[: self._released])
        for pump in self.pumps:
            pump.auto_run = pump in allowed
            pump.speed_sp_auto = speed

        # роли для дашборда
        ordered = list(self._requested) + sorted(
            (q for q in self.pumps if q not in self._requested and self._usable(q)), key=self._hours
        )
        roles: dict[str, str] = {}
        for i, q in enumerate(ordered):
            roles[q.tag] = ROLE_DUTY if i == 0 else (ROLE_ASSIST if i == 1 else ROLE_STANDBY)
        for q in self.pumps:
            roles.setdefault(q.tag, "unavailable")
        st.roles = roles
        st.requested = [q.tag for q in self._requested]

        # --- давление: тревоги уставок подавлены, пока насосы стоят (API 21.1) ---------------------
        pt = self.devs.get("PT201")
        if isinstance(pt, AnalogInput):
            pt.suppress_limit_alarms = not any(q.running for q in self.pumps)
        ft = self.devs.get("FT202")
        if isinstance(ft, AnalogInput):
            ft.suppress_limit_alarms = not any(q.running for q in self.pumps)

        # --- вентилятор павильона ----------------------------------------------------------------
        if self.fan is not None:
            gas = self._ai("AT401").flags["H"] or self._ai("AT402").flags["H"]
            hot = self._ai("TT403").flags["H"]
            door = self._di("ZS404").value
            fire = self._di("YS405").value
            periodic = (t % p.fan_period_s) < p.fan_on_s
            if gas or hot:
                self._fan_hold_until = t + p.fan_hold_s  # проветривание не короче fan_hold_s
            hold = t < self._fan_hold_until
            self.fan.auto_run = (hold or door or periodic) and not fire
            self.fan.power_ok = power

    def annunciate(self, devs: list[Device], silence: bool) -> None:
        """Сирена HA1, лампа HL1, реле общей аварии K1 (сигналы без ФБ, код приложения)."""
        unack_ids = {
            s.alarm.id for d in devs for s in d.alarms.slots.values() if s.unack and s.priority >= AlarmPriority.MEDIUM
        }
        if unack_ids - self._prev_unack_ids:
            self.horn = True  # новая неквитированная тревога
        if silence or not unack_ids:
            self.horn = False
        self._prev_unack_ids = unack_ids
        self.lamp = any(s.unack or s.active for d in devs for s in d.alarms.slots.values())
        self.general_alarm = any(d.alarms.any_active(AlarmPriority.HIGH) for d in devs) or any(
            d.mode != DeviceMode.OUT_OF_SERVICE and d.fault for d in self.pumps
        )
