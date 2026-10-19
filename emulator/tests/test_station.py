"""Станция KNS1 и регулятор LIC101 эмулятора — теги GVL_Station флагмана: режим, способ, команды, тревоги."""

from __future__ import annotations

from iiot_emulator.emulator import EmulatorConfig, KnsEmulator
from iiot_emulator.schema import default_topics, telemetry_catalog
from iiot_emulator.station import (
    ACT_FLOAT,
    ACT_LEVEL_PID,
    ACT_MANUAL,
    ACT_POWER_LOST,
    ST_COMMON_ALARM,
    ST_FLOAT,
    ST_POWER_LOST,
)
from iiot_emulator.telemetry import NodeDiag, TelemetryTracker


def emulator() -> KnsEmulator:
    return KnsEmulator(EmulatorConfig(auto_faults=False, auto_ack_s=0, noise=False))


def bit(emu: KnsEmulator, suffix: str) -> int:
    return 1 << emu.station_dev.bit_of[suffix]


def test_station_starts_in_auto_with_level_pid() -> None:
    emu = emulator()
    emu.run_for(600)
    im = emu.image()
    assert (im["KNS1.Mode"], im["KNS1.Method"], im["KNS1.ControlAct"]) == (1, 2, ACT_LEVEL_PID)
    assert im["KNS1.PumpsAvailable"] == 3 and 1 <= im["KNS1.LeadPump"] <= 3
    # станция работает по выходам устройств прошлого цикла (как PRG_Station флагмана до PRG_Devices)
    assert abs(im["KNS1.Level"] - im["LT101.Value"]) < 0.01 and im["KNS1.LevelSp"] == 1.4
    assert im["LIC101.Mode"] == 1 and im["LIC101.Pv"] == im["LT101.Value"]
    assert im["KNS1.AlmActive"] == 0 and im["KNS1.Ne107"] == 0


def test_mode_and_method_commands_count_and_act() -> None:
    emu = emulator()
    emu.run_for(60)
    seq = emu.image()["KNS1.CmdSeq"]
    emu.write_tag("KNS1.Cmd.SetStepped", True)
    emu.run_for(30)
    im = emu.image()
    assert im["KNS1.Method"] == 1 and im["KNS1.CmdSeq"] == seq + 1 and im["KNS1.CmdResult"] == 1
    assert im["KNS1.Cmd.SetStepped"] is False  # импульс сброшен
    if im["KNS1.PumpsRequired"]:
        assert im["KNS1.SpeedSp"] == 100.0  # ступенчатое: rStepSpeed_pct
    emu.write_tag("KNS1.Cmd.SetManual", True)
    emu.run_for(30)
    im = emu.image()
    assert (im["KNS1.Mode"], im["KNS1.ControlAct"], im["KNS1.PumpsRequired"]) == (2, ACT_MANUAL, 0)
    assert im["KNS1.Ne107"] == 3  # C — станция в «Ручном»
    assert not int(im["KNS1.AlmActive"]) & bit(emu, "NOAUTO")  # задержка тревоги 600 с
    emu.run_for(600)
    assert int(emu.image()["KNS1.AlmActive"]) & bit(emu, "NOAUTO")
    emu.write_tag("KNS1.Cmd.SetAuto", True)
    emu.write_tag("KNS1.Cmd.SetLevelPid", True)
    emu.run_for(5)
    im = emu.image()
    assert (im["KNS1.Mode"], im["KNS1.Method"]) == (1, 2)
    assert im["KNS1.CmdSeq"] == seq + 4


def test_float_mode_alarm_ack_and_shelve_by_number() -> None:
    emu = emulator()
    emu.run_for(60)
    emu.inject("lt101_wire_break")
    emu.run_for(60)
    im = emu.image()
    assert im["KNS1.ControlAct"] == ACT_FLOAT and int(im["KNS1.State"]) & ST_FLOAT
    assert int(im["KNS1.AlmActive"]) & bit(emu, "FLOAT") and int(im["KNS1.AlmUnack"]) & bit(emu, "FLOAT")
    assert im["KNS1.Ne107"] == 2 and im["LIC101.Ne107"] == 4  # S — по поплавкам; PV LIC101 недостоверен
    emu.write_tag("KNS1.Cmd.AckAll", True)
    emu.step(1)
    im = emu.image()
    assert not im["KNS1.AlmUnack"] and not im["LT101.AlmUnack"]  # квитированы станция и устройства
    emu.write_tag("KNS1.Cmd.ShelveId", 100006)  # KNS1.FLOAT
    emu.step(1)
    im = emu.image()
    assert int(im["KNS1.AlmShelved"]) & bit(emu, "FLOAT") and im["KNS1.Cmd.ShelveId"] == 0
    emu.write_tag("KNS1.Cmd.UnshelveId", 999999)  # нет такой тревоги
    emu.step(1)
    assert emu.image()["KNS1.CmdResult"] == 7  # RejectedState


def test_power_loss_bits_and_general_alarm_relay() -> None:
    emu = emulator()
    emu.run_for(60)
    im = emu.image()
    assert im["K1"] is True  # реле «Общая авария» под напряжением в норме
    emu.inject("power_loss")
    emu.run_for(30)
    im = emu.image()
    assert im["KNS1.ControlAct"] == ACT_POWER_LOST and int(im["KNS1.State"]) & ST_POWER_LOST
    emu.inject("p1_vfd_trip")
    emu.inject("power_loss", False)
    emu.run_for(120)
    im = emu.image()
    if int(im["KNS1.State"]) & ST_COMMON_ALARM:
        assert im["K1"] is False  # обесточено — общая авария


def test_general_alarm_metric_is_inverse_of_relay() -> None:
    emu = emulator()
    emu.run_for(10)
    tracker = TelemetryTracker(default_topics())
    m = next(x for x in telemetry_catalog() if (x.device, x.metric) == ("K1", "general_alarm"))
    assert m.invert
    value = tracker.value(emu, emu.image(), m, NodeDiag(), 0.0)
    assert value == (0 if emu.image()["K1"] else 1)


def test_lic101_manual_output_drives_speed() -> None:
    emu = emulator()
    emu.run_for(60)
    emu.write_tag("LIC101.Cmd.SetManual", True)
    emu.step(1)
    emu.write_tag("LIC101.Cmd.ManualOut", 77.0)
    emu.run_for(5)
    im = emu.image()
    assert im["LIC101.Mode"] == 2 and im["LIC101.Cmd.ManualOut"] == 77.0
    assert im["KNS1.SpeedSp"] == 77.0
    emu.write_tag("LIC101.Cmd.SetAuto", True)
    emu.run_for(5)
    im = emu.image()
    assert im["LIC101.Mode"] == 1 and im["LIC101.Cmd.ManualOut"] == im["KNS1.SpeedSp"]  # слежение
