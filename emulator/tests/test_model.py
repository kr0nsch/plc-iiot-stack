"""Модель объекта и логика эмулятора: детерминизм, импульсные команды, защиты, отказы."""

from __future__ import annotations

import pytest

from iiot_emulator.devices import CmdResult, DeviceMode, MotorState, Ne107
from iiot_emulator.emulator import CommandError, EmulatorConfig, KnsEmulator, coerce_iec
from iiot_emulator.plant import Plant, diurnal_factor


def make(seed: int = 1, **kw: object) -> KnsEmulator:
    cfg = EmulatorConfig(seed=seed, **kw)  # type: ignore[arg-type]
    return KnsEmulator(cfg)


# --- детерминизм ----------------------------------------------------------------------------------
def _trace(emu: KnsEmulator, hours: float) -> list[tuple[float, ...]]:
    out: list[tuple[float, ...]] = []
    for _ in range(int(hours * 6)):
        emu.run_for(600)
        im = emu.image()
        out.append(
            (
                float(im["LT101.Value"]),
                float(im["FT202.Value"]),
                float(im["P101.RunTime"]),
                float(im["P102.RunTime"]),
                float(im["P103.RunTime"]),
                float(im["PT201.Value"]),
                float(im["AT401.Value"]),
            )
        )
    return out


def test_same_seed_same_trajectory() -> None:
    a, b = make(7), make(7)
    a.plant.force_storm(400.0, 1.5)
    b.plant.force_storm(400.0, 1.5)
    assert _trace(a, 4) == _trace(b, 4)
    assert a.image() == b.image()
    assert [(e.alarm.code, e.reason, e.sim_time_s) for e in a.events] == [
        (e.alarm.code, e.reason, e.sim_time_s) for e in b.events
    ]


def test_different_seed_differs() -> None:
    assert _trace(make(1), 2) != _trace(make(2), 2)


def test_inflow_is_pure_function_of_seed_and_time() -> None:
    """Приток не зависит от шага интегрирования и от истории — только от (seed, t)."""
    p1, p2 = Plant(seed=3), Plant(seed=3)
    for _ in range(100):
        p1.step(1.0)
    for _ in range(20):
        p2.step(5.0)
    assert p1.t == p2.t == 100.0
    assert p1.inflow_at(5000.0) == p2.inflow_at(5000.0) == Plant(seed=3).inflow_at(5000.0)
    assert Plant(seed=3).inflow_at(5000.0) != Plant(seed=4).inflow_at(5000.0)
    # расписание «ливней» повторяется
    assert Plant(seed=3).storms_of_day(5) == Plant(seed=3).storms_of_day(5)


def test_diurnal_curve_mean_is_one() -> None:
    n = 2400
    mean = sum(diurnal_factor(24.0 * i / n) for i in range(n)) / n
    assert mean == pytest.approx(1.0, abs=0.01)
    assert diurnal_factor(3.0) < 0.7 < 1.4 < diurnal_factor(8.0)


# --- команды: импульсная семантика (API 2.1) ------------------------------------------------------
def test_pulse_is_cleared_and_result_reported() -> None:
    emu = make(auto_faults=False)
    p = emu.devs["P101"]
    seq = p.cmd_seq
    emu.write_tag("P101.Cmd.Start", True)  # в Auto пуск с HMI запрещён
    assert emu.read_tag("P101.Cmd.Start") is True
    emu.step()
    assert emu.read_tag("P101.Cmd.Start") is False
    assert emu.read_tag("P101.CmdSeq") == seq + 1
    assert emu.read_tag("P101.CmdResult") == CmdResult.REJECTED_MODE
    emu.write_tag("P101.Cmd.Stop", True)  # «Стоп» в Auto — переход в Manual
    emu.step()
    assert emu.read_tag("P101.Mode") == DeviceMode.MANUAL
    assert emu.read_tag("P101.CmdResult") == CmdResult.ACCEPTED
    assert emu.read_tag("P101.Cmd.Stop") is False


def test_masks_are_zeroed_after_processing() -> None:
    emu = make(auto_faults=False)
    emu.write_tag("LT101.Cmd.AckReq", 0x000F)
    emu.step()
    assert emu.read_tag("LT101.Cmd.AckReq") == 0


def test_manual_start_and_speed_setpoint_clamped() -> None:
    emu = make(auto_faults=False)
    emu.write_tag("P103.Cmd.SetManual", True)
    emu.write_tag("P103.Cmd.Start", True)  # tMinStop отсчитывается от старта ПЛК: пуск запрещён
    emu.step()
    assert emu.read_tag("P103.CmdResult") == CmdResult.REJECTED_INHIBIT
    assert int(emu.read_tag("P103.InhibitRemain")) > 0
    emu.run_for(30)
    emu.write_tag("P103.Cmd.SpeedSp", 30.0)  # ниже минимума ПЧ — ФБ ограничит до 60 %
    emu.write_tag("P103.Cmd.Start", True)
    emu.run_for(60)
    assert emu.read_tag("P103.CmdResult") == CmdResult.ACCEPTED
    assert emu.read_tag("P103.State") == MotorState.RUNNING
    assert emu.read_tag("P103.Cmd.SpeedSp") == pytest.approx(60.0)
    assert emu.read_tag("P103.SpeedRef") == pytest.approx(60.0)
    emu.write_tag("P103.Cmd.SpeedSp", 90.0)
    emu.run_for(20)  # рампа 5 %/с
    assert emu.read_tag("P103.SpeedRef") == pytest.approx(90.0)
    assert float(emu.read_tag("P103.SpeedAct")) == pytest.approx(90.0, abs=0.5)


def test_value_command_tracks_in_auto() -> None:
    emu = make(auto_faults=False)
    emu.run_for(30)
    assert emu.read_tag("LT101.Cmd.SubstValue") == emu.read_tag("LT101.Value")


def test_write_tag_rejects_status_and_bad_types() -> None:
    emu = make(auto_faults=False)
    with pytest.raises(CommandError):
        emu.write_tag("LT101.Value", 1.0)  # состояние, не команда
    with pytest.raises(CommandError):
        emu.write_tag("P101.Cmd.Start", "yes")
    with pytest.raises(CommandError):
        emu.write_tag("P101.Cmd.AckReq", 70000)
    assert coerce_iec("WORD", 65535.0) == 65535
    with pytest.raises(CommandError):
        coerce_iec("REAL", float("nan"))


# --- станция и защиты -----------------------------------------------------------------------------
def test_storm_raises_level_and_starts_more_pumps() -> None:
    emu = make(3, auto_faults=False)
    emu.plant.force_storm(450.0, 2.0)
    seen_two = False
    max_level = 0.0
    for _ in range(int(2.5 * 3600 / 60)):
        emu.run_for(60)
        running = sum(bool(emu.read_tag(f"{p}.Running")) for p in ("P101", "P102", "P103"))
        seen_two |= running >= 2
        max_level = max(max_level, float(emu.read_tag("LT101.Value")))
    assert seen_two
    assert max_level >= 3.5
    codes = {e.alarm.code for e in emu.events if e.reason.name == "ACTIVATED"}
    assert "LT101.H" in codes


def test_duty_rotation_by_run_hours() -> None:
    emu = make(5, auto_faults=False, step_s=2.0)
    emu.run_for(20 * 3600)
    hours = [float(emu.read_tag(f"{p}.RunTime")) for p in ("P101", "P102", "P103")]
    starts = [int(emu.read_tag(f"{p}.Starts")) for p in ("P101", "P102", "P103")]
    assert all(s > 0 for s in starts), starts
    assert max(hours) - min(hours) < 6.5, hours  # наработка выравнивается
    assert set(emu.station.state.roles.values()) >= {"duty", "assist"}


def test_vfd_trip_triggers_transfer_and_reset() -> None:
    emu = make(1, auto_faults=False)
    emu.run_for(1800)  # утро: ведущий насос в работе
    duty = next(p for p in emu.pumps if p.state == MotorState.RUNNING)
    n = duty.tag[-1]
    emu.inject(f"p{n}_vfd_trip")
    emu.run_for(60)
    assert duty.state == MotorState.FAULT
    assert emu.read_tag(f"{duty.tag}.Ne107") == Ne107.FAILURE
    assert emu.read_tag(f"{duty.tag}_FCODE") != 0
    assert emu.station.state.transfers >= 1
    others = [p for p in emu.pumps if p is not duty]
    assert any(p.state in (MotorState.STARTING, MotorState.RUNNING) for p in others)
    assert any(e.alarm.code == f"{duty.tag}.EXT" and e.reason.name == "ACTIVATED" for e in emu.events)
    # сброс не снимает отказ, пока причина есть
    emu.write_tag(f"{duty.tag}.Cmd.Reset", True)
    emu.run_for(10)
    assert duty.state == MotorState.FAULT
    emu.inject(f"p{n}_vfd_trip", False)
    emu.write_tag(f"{duty.tag}.Cmd.Reset", True)
    emu.run_for(10)
    assert emu.read_tag(f"{duty.tag}.State") != MotorState.FAULT
    assert emu.read_tag(f"{duty.tag}.Fault") == 0


def test_level_sensor_wire_break_degraded_mode() -> None:
    emu = make(1, auto_faults=False)
    emu.run_for(600)
    before = float(emu.read_tag("LT101.Value"))
    emu.inject("lt101_wire_break")
    emu.step()  # отказ ещё не подтверждён: значение удерживается, ложного LL нет
    assert emu.read_tag("LT101.Valid") is True
    assert float(emu.read_tag("LT101.Value")) == pytest.approx(before, abs=0.05)
    emu.run_for(5)
    assert emu.read_tag("LT101.Valid") is False
    assert emu.read_tag("LT101.Ne107") == Ne107.FAILURE
    assert emu.read_tag("LT101.Signal") == 3  # FailLow
    assert emu.station.state.degraded
    assert not emu.devs["LT101"].alarms.slots[3].active  # LL подавлен при отказе


def test_dry_run_float_interlocks_pumps() -> None:
    emu = make(1, auto_faults=False)
    emu.run_for(1800)
    emu.inject("ls103_stuck")
    emu.run_for(30)
    for p in emu.pumps:
        assert p.interlock & 1
        assert not p.q_run
    assert any(e.alarm.code == "LS103.ALM" for e in emu.events)


def test_power_loss_and_sequential_restart() -> None:
    emu = make(2, auto_faults=False)
    emu.plant.force_storm(420.0, 3.0)
    emu.run_for(3600)
    assert sum(p.running for p in emu.pumps) >= 2
    emu.inject("power_loss")
    emu.run_for(60)
    assert not any(p.running for p in emu.pumps)
    assert all(p.state != MotorState.FAULT for p in emu.pumps)  # пропадание питания — не отказ
    assert emu.read_tag("ES301.Value") is False and emu.read_tag("YS302.Value") is True
    emu.inject("power_loss", False)
    emu.run_for(5)  # tMinStop 30 с от пропадания уже прошёл: первый насос пускается сразу
    assert sum(p.q_run for p in emu.pumps) == 1
    emu.run_for(8)
    assert sum(p.q_run for p in emu.pumps) == 1  # второй — через 10 с после выхода первого в работу
    emu.run_for(10)
    assert sum(p.q_run for p in emu.pumps) >= 2


def test_comm_loss_is_warning_not_fault() -> None:
    """Флагман: xCommLossIsFault = FALSE — потеря связи с ПЧ даёт предупреждение и тревогу COM."""
    emu = make(1, auto_faults=False)
    emu.run_for(1800)
    emu.inject("p1_comm_loss")
    emu.run_for(10)
    p1 = emu.devs["P101"]
    assert p1.alarms.slots[6].active
    assert emu.read_tag("P101.Ne107") == Ne107.OUT_OF_SPECIFICATION
    assert emu.read_tag("IT111.Valid") is False


def test_oos_requires_stopped_motor() -> None:
    emu = make(1, auto_faults=False)
    emu.run_for(1800)
    running = next(p for p in emu.pumps if p.running)
    emu.write_tag(f"{running.tag}.Cmd.SetOos", True)
    emu.step()
    assert emu.read_tag(f"{running.tag}.CmdResult") == CmdResult.REJECTED_STATE
    idle = next(p for p in emu.pumps if not p.running and p.state == MotorState.STOPPED)
    emu.write_tag(f"{idle.tag}.Cmd.SetOos", True)
    emu.step(2)  # роли станция пересчитывает в следующем цикле
    assert emu.read_tag(f"{idle.tag}.Mode") == DeviceMode.OUT_OF_SERVICE
    assert emu.read_tag(f"{idle.tag}.Ne107") == Ne107.CHECK_FUNCTION
    assert emu.station.state.roles[idle.tag] == "unavailable"


def test_auto_scenario_is_reproducible() -> None:
    a = make(11, step_s=5.0)
    b = make(11, step_s=5.0)
    a.run_for(26 * 3600)
    b.run_for(26 * 3600)
    assert list(a.scenario_log) == list(b.scenario_log)
    assert a.scenario_log, "за сутки сценарий должен что-то сделать"
