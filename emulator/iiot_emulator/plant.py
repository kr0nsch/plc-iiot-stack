"""Модель объекта КНС-1: приёмный резервуар, приток, насосы с ПЧ, напорный коллектор, павильон.

Модель простая и детерминированная — ровно настолько, чтобы дашборды показывали правдоподобную
картину: суточный ход притока, «ливни», чередование насосов, рост уровня до тревог.

- **Резервуар:** баланс объёма ``A·dL/dt = Qin − Qout``, площадь постоянная.
- **Приток:** суточная кривая (ночной минимум, утренний и вечерний пики) плюс медленный шум и
  «ливни» по расписанию, которое строится из зерна (seed) для каждых модельных суток. Приток —
  чистая функция ``(seed, t)``: он не зависит от шага интегрирования и от того, что делают насосы.
- **Насосы:** характеристика ``H = H0·s² − K·Qi²`` (законы подобия, s — доля номинальной
  скорости), обратный клапан (Qi ≥ 0), работа на общий коллектор ``H = Hst − L + R·Q²``; рабочая
  точка — бисекцией по напору. ПЧ — рампа и инерция разгона.
- **Давление** PT201 — статический столб от манометра до точки сброса плюс потери в трубопроводе.

Параметры условные (объект вымышленный) и записаны в ``PlantParams``; это не данные реального
насоса или объекта.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

DAY_S = 86400.0
G_BAR_PER_M = 1.0 / 10.197  # 1 м вод. ст. ≈ 0,0981 бар


@dataclass(frozen=True)
class PlantParams:
    """Условные параметры КНС-1 (выбраны так, чтобы два насоса покрывали обычный пик)."""

    well_area_m2: float = 15.0
    level_max_m: float = 5.0
    level_init_m: float = 1.4
    inflow_avg_m3h: float = 95.0  # средний сухой приток
    inflow_noise: float = 0.06  # амплитуда медленного шума притока, доля
    storm_prob_per_day: float = 0.6  # вероятность «ливня» в модельные сутки
    storm_peak_m3h: tuple[float, float] = (180.0, 430.0)
    storm_duration_h: tuple[float, float] = (1.0, 3.5)
    # насосы и сеть
    pump_h0_m: float = 40.0  # напор при нулевой подаче и номинальной скорости
    pump_k: float = 3.36e-4  # м/(м³/ч)² — крутизна характеристики
    static_head_m: float = 12.0  # от дна резервуара до точки сброса
    gauge_static_m: float = 11.5  # от манометра PT201 до точки сброса
    pipe_r: float = 1.24e-4  # м/(м³/ч)² — потери в напорном коллекторе
    vfd_accel_pctps: float = 10.0  # разгон и торможение ПЧ, %/с
    vfd_start_delay_s: float = 1.0  # от команды до реле «в работе»
    motor_i_mag_a: float = 7.5  # ток холостого хода
    motor_i_nom_a: float = 27.0  # ток в номинальной точке
    nominal_q_m3h: float = 240.0
    nominal_h_m: float = 26.5
    clog_factor: float = 0.35  # засор рабочего колеса: снижение подачи и рост тока
    # павильон
    temp_mean_c: float = 16.0
    temp_amp_c: float = 3.5
    h2s_base_mgm3: float = 1.2
    ch4_base_pct: float = 1.5


@dataclass
class PumpPlant:
    """Насос и его ПЧ в модели объекта (то, что «железо» отдаёт в ПЛК)."""

    no: int
    q_run_cmd: bool = False  # команда «работа» от ПЛК (дискретный выход)
    speed_ref_pct: float = 0.0  # задание от ПЛК
    speed_act_pct: float = 0.0
    running_relay: bool = False  # релейный выход ПЧ «в работе»
    flow_m3h: float = 0.0
    head_m: float = 0.0
    current_a: float = 0.0
    start_timer_s: float = 0.0
    # отказы (инъекция)
    vfd_trip: bool = False
    no_feedback: bool = False
    clog: bool = False
    overheat: bool = False
    leak: bool = False
    local_switch: bool = False
    local_run: bool = False  # «Пуск» по месту при переключателе в «Местное»
    comm_loss: bool = False
    fault_code: int = 0  # код последней аварии ПЧ (условный)


@dataclass
class Storm:
    start_s: float
    duration_s: float
    peak_m3h: float

    def flow(self, t: float) -> float:
        """Треугольный подъём (25 %) и экспоненциальный спад."""
        x = t - self.start_s
        if x < 0 or x > self.duration_s * 2.5:
            return 0.0
        rise = self.duration_s * 0.25
        if x <= rise:
            return self.peak_m3h * x / rise
        return self.peak_m3h * math.exp(-(x - rise) / (self.duration_s * 0.45))


def diurnal_factor(hour: float) -> float:
    """Суточный коэффициент притока (среднее за сутки ≈ 1)."""
    h = hour % 24.0

    def bump(center: float, width: float) -> float:
        # циклическое расстояние по кругу суток
        d = min(abs(h - center), 24.0 - abs(h - center))
        return math.exp(-((d / width) ** 2))

    raw = 0.42 + 1.05 * bump(8.0, 1.9) + 0.75 * bump(20.0, 2.6) + 0.35 * bump(13.5, 2.5)
    return raw / 0.776  # нормировка: среднее raw за сутки = 0,776 (численное интегрирование)


@dataclass
class Plant:
    """Состояние объекта и шаг интегрирования."""

    seed: int = 1
    params: PlantParams = field(default_factory=PlantParams)
    t0_s: float = 0.0  # модельное время старта от полуночи (для суточной кривой)

    def __post_init__(self) -> None:
        p = self.params
        self.level_m = p.level_init_m
        self.pumps = [PumpPlant(no=i + 1) for i in range(3)]
        self.inflow_m3h = 0.0
        self.outflow_m3h = 0.0
        self.header_head_m = 0.0
        self.pressure_bar = p.gauge_static_m * G_BAR_PER_M
        self.forced_storms: list[Storm] = []
        # отказы и события объекта (инъекция)
        self.power_ok = True
        self.ups_fault = False
        self.chamber_flood = False
        self.door_open_forced = False
        self.fire = False
        self.h2s_spike = False
        self.lt_wire_break = False
        self.ls_high_stuck: bool | None = None  # залипание поплавка: None — нет, иначе значение
        self.ls_dry_stuck: bool | None = None
        self.fan_running = False
        self.fan_cmd = False
        self.fan_fault = False
        self.t = 0.0
        self.h2s = p.h2s_base_mgm3
        self.ch4 = p.ch4_base_pct
        self.temp_c = p.temp_mean_c
        self._storm_cache: dict[int, tuple[Storm, ...]] = {}
        self._noise_cache: dict[int, float] = {}

    # --- приток ------------------------------------------------------------------------------------
    def storms_of_day(self, day: int) -> tuple[Storm, ...]:
        """Расписание «ливней» модельных суток: чистая функция (seed, day)."""
        cached = self._storm_cache.get(day)
        if cached is not None:
            return cached
        if len(self._storm_cache) > 256:
            self._storm_cache.clear()
        rng = random.Random(f"kns-storm:{self.seed}:{day}")
        p = self.params
        out: list[Storm] = []
        if rng.random() < p.storm_prob_per_day:
            start = day * DAY_S + rng.uniform(0.0, DAY_S) - self.t0_s
            dur = rng.uniform(*p.storm_duration_h) * 3600.0
            peak = rng.uniform(*p.storm_peak_m3h)
            out.append(Storm(start, dur, peak))
        result = tuple(out)
        self._storm_cache[day] = result
        return result

    def _noise(self, t: float) -> float:
        """Медленный шум притока: интерполяция случайных узлов раз в 10 минут."""
        step = 600.0
        k = math.floor(t / step)
        frac = t / step - k

        def node(i: int) -> float:
            v = self._noise_cache.get(i)
            if v is None:
                if len(self._noise_cache) > 4096:
                    self._noise_cache.clear()
                v = random.Random(f"kns-noise:{self.seed}:{i}").uniform(-1.0, 1.0)
                self._noise_cache[i] = v
            return v

        a, b = node(k), node(k + 1)
        w = (1 - math.cos(math.pi * frac)) / 2
        return a + (b - a) * w

    def inflow_at(self, t: float) -> float:
        """Приток в резервуар, м³/ч, в модельный момент t (с от старта)."""
        p = self.params
        hour = ((t + self.t0_s) % DAY_S) / 3600.0
        q = p.inflow_avg_m3h * diurnal_factor(hour) * (1.0 + p.inflow_noise * self._noise(t))
        day = math.floor((t + self.t0_s) / DAY_S)
        for d in (day - 1, day):
            for s in self.storms_of_day(d):
                q += s.flow(t)
        for s in self.forced_storms:
            q += s.flow(t)
        return max(0.0, q)

    def force_storm(self, peak_m3h: float = 320.0, duration_h: float = 2.0) -> None:
        self.forced_storms.append(Storm(self.t, duration_h * 3600.0, peak_m3h))

    def next_storm_after(self, t: float) -> Storm | None:
        day = math.floor((t + self.t0_s) / DAY_S)
        for d in range(day, day + 30):
            for s in self.storms_of_day(d):
                if s.start_s >= t:
                    return s
        return None

    # --- насосы и сеть -----------------------------------------------------------------------------
    def _pump_q(self, s: float, head: float, clog: bool) -> float:
        p = self.params
        h0 = p.pump_h0_m * s * s * (1.0 - (p.clog_factor * 0.5 if clog else 0.0))
        if head >= h0:
            return 0.0
        return math.sqrt((h0 - head) / p.pump_k)

    def _solve_header(self, speeds: list[tuple[float, bool]]) -> tuple[float, list[float]]:
        """Рабочая точка: напор коллектора и подачи насосов (бисекция по напору)."""
        p = self.params
        h_static = p.static_head_m - self.level_m
        active = [(s, c) for s, c in speeds if s > 0.0]
        if not active:
            return h_static, [0.0] * len(speeds)
        lo = h_static
        hi = max(p.pump_h0_m * s * s for s, _ in active)
        if hi <= lo:
            return h_static, [0.0] * len(speeds)
        for _ in range(48):
            mid = (lo + hi) / 2
            q_pumps = sum(self._pump_q(s, mid, c) for s, c in active)
            q_sys = math.sqrt(max(0.0, (mid - h_static) / p.pipe_r))
            if q_pumps > q_sys:
                lo = mid
            else:
                hi = mid
        head = (lo + hi) / 2
        return head, [self._pump_q(s, head, c) if s > 0 else 0.0 for s, c in speeds]

    def step(self, dt: float) -> None:
        """Шаг модели на dt секунд модельного времени."""
        p = self.params
        self.t += dt
        # ПЧ: разгон, реле «в работе», останов при отсутствии питания или аварии
        for pump in self.pumps:
            local = pump.local_switch
            want = (pump.local_run if local else pump.q_run_cmd) and self.power_ok and not pump.vfd_trip
            if want:
                pump.start_timer_s += dt
                target = (100.0 if local else pump.speed_ref_pct) if pump.start_timer_s >= p.vfd_start_delay_s else 0.0
            else:
                pump.start_timer_s = 0.0
                target = 0.0
            if not self.power_ok:
                pump.speed_act_pct = max(0.0, pump.speed_act_pct - 25.0 * dt)  # выбег
            elif pump.speed_act_pct < target:
                pump.speed_act_pct = min(target, pump.speed_act_pct + p.vfd_accel_pctps * dt)
            else:
                pump.speed_act_pct = max(target, pump.speed_act_pct - p.vfd_accel_pctps * dt)
            pump.running_relay = want and pump.start_timer_s >= p.vfd_start_delay_s and not pump.no_feedback
            if pump.vfd_trip and pump.fault_code == 0:
                pump.fault_code = 16 + pump.no  # условный код «перегрузка по току»
        speeds = [(pmp.speed_act_pct / 100.0, pmp.clog) for pmp in self.pumps]
        head, flows = self._solve_header(speeds)
        self.header_head_m = head
        self.outflow_m3h = 0.0
        for pump, q in zip(self.pumps, flows, strict=True):
            pump.flow_m3h = q
            pump.head_m = head if q > 0 else 0.0
            self.outflow_m3h += q
            s = pump.speed_act_pct / 100.0
            load = (q * head) / (p.nominal_q_m3h * p.nominal_h_m) if s > 0 else 0.0
            if s > 0:
                i = p.motor_i_mag_a * s + (p.motor_i_nom_a - p.motor_i_mag_a) * load
                if pump.clog:
                    i *= 1.0 + p.clog_factor
                pump.current_a = i
            else:
                pump.current_a = 0.0
        # давление: статический столб (обратные клапаны держат коллектор) + потери
        q = self.outflow_m3h
        self.pressure_bar = (p.gauge_static_m + p.pipe_r * q * q) * G_BAR_PER_M
        # резервуар
        self.inflow_m3h = self.inflow_at(self.t)
        dv = (self.inflow_m3h - self.outflow_m3h) / 3600.0 * dt
        self.level_m = min(p.level_max_m + 0.3, max(0.0, self.level_m + dv / p.well_area_m2))
        # павильон: температура — суточная синусоида; газы — фон плюс рост при высоком уровне
        hour = ((self.t + self.t0_s) % DAY_S) / 3600.0
        self.temp_c = p.temp_mean_c + p.temp_amp_c * math.sin((hour - 9.0) / 24.0 * 2 * math.pi)
        if self.fan_running:
            self.temp_c -= 1.0
        h2s_target = p.h2s_base_mgm3 * (1.0 + 0.5 * self._noise(self.t + 1e6)) + max(0.0, self.level_m - 2.5) * 1.5
        if self.h2s_spike:
            h2s_target += 9.0
        if self.fan_running:
            h2s_target *= 0.35
        self.h2s += (h2s_target - self.h2s) * min(1.0, dt / 120.0)
        ch4_target = p.ch4_base_pct * (1.0 + 0.4 * self._noise(self.t + 2e6)) * (0.4 if self.fan_running else 1.0)
        self.ch4 += (ch4_target - self.ch4) * min(1.0, dt / 180.0)
        self.fan_running = self.fan_cmd and self.power_ok and not self.fan_fault

    # --- сигналы датчиков (то, что видит ПЛК) ------------------------------------------------------
    @staticmethod
    def to_ma(value: float, lo: float, hi: float) -> float:
        return 4.0 + 16.0 * (value - lo) / (hi - lo)

    def lt101_ma(self) -> float:
        return 0.0 if self.lt_wire_break else self.to_ma(min(self.level_m, 5.25), 0.0, 5.0)

    def float_high(self) -> bool:
        """Поплавок LS102 (4,2 м): True — сработал."""
        return self.ls_high_stuck if self.ls_high_stuck is not None else self.level_m >= 4.2

    def float_dry(self) -> bool:
        """Поплавок LS103 (0,4 м): True — сработал (уровень ниже)."""
        return self.ls_dry_stuck if self.ls_dry_stuck is not None else self.level_m <= 0.4
