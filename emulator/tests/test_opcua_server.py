"""OPC UA-сервер эмулятора в процессе: обзор, чтение, запись команды и сброс импульса, политики."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from asyncua import ua
from asyncua.client.client import Client
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.ua.uaerrors import UaError, UaStatusCodeError
from conftest import free_port
from cryptography.x509.oid import ExtendedKeyUsageOID

from iiot_emulator.app import EmulatorApp
from iiot_emulator.config import MqttSettings, OpcUaSettings, Settings, SimSettings
from iiot_emulator.tagmodel import load_tags

pytestmark = pytest.mark.network

USER, PASSWORD = "operator", "test-password-123"
NS = "ns=4;s=|var|CODESYS Control Win V3.Application."


async def _with_server(pki: Path, body: Callable[[str, EmulatorApp], Awaitable[None]], **opc: Any) -> None:
    port = free_port()
    url = f"opc.tcp://127.0.0.1:{port}"
    settings = Settings(
        sim=SimSettings(time_factor=60.0, tick_s=0.05, auto_faults=False),
        opcua=OpcUaSettings(endpoint=url, user=USER, password=PASSWORD, pki_dir=pki, **opc),
        mqtt=MqttSettings(enable=False),
    )
    app = EmulatorApp(settings)
    task = asyncio.create_task(app.run())
    try:
        for _ in range(100):  # ждём, пока сервер начнёт слушать
            await asyncio.sleep(0.05)
            if app.ticks > 0:
                break
        await body(url, app)
    finally:
        app.stop()
        await asyncio.wait_for(task, 10)


def run(pki: Path, body: Callable[[str, EmulatorApp], Awaitable[None]], **opc: Any) -> None:
    asyncio.run(_with_server(pki, body, **opc))


async def user_client(url: str) -> Client:
    c = Client(url)
    c.set_user(USER)
    c.set_password(PASSWORD)
    return c


@pytest.fixture
def pki(tmp_path: Path) -> Path:
    return tmp_path / "pki"


def test_browse_read_and_types(pki: Path) -> None:
    async def body(url: str, app: EmulatorApp) -> None:
        async with await user_client(url) as c:
            # обзор: Objects → DeviceSet → устройство → Resources → Application → GVL → экземпляр
            objects = c.nodes.objects
            names = [(await n.read_browse_name()).Name for n in await objects.get_children()]
            assert "DeviceSet" in names and "Simulation" in names
            node = await objects.get_child(
                [
                    "4:DeviceSet",
                    "4:CODESYS Control Win V3",
                    "4:Resources",
                    "4:Application",
                    "4:GVL_Devices",
                    "4:fbLT101",
                ]
            )
            children = {(await n.read_browse_name()).Name for n in await node.get_children()}
            assert {"stSts", "xValid"} <= children
            # чтение и типы данных как в ПЛК
            expect = {
                "GVL_Devices.fbLT101.stSts.rValue_eu": ua.VariantType.Float,
                "GVL_Devices.fbP101.stSts.stCommon.eMode": ua.VariantType.Int16,
                "GVL_Devices.fbP101.stSts.stCommon.wStatus": ua.VariantType.UInt16,
                "GVL_Devices.fbP101.stSts.udiStarts": ua.VariantType.UInt32,
                "GVL_Devices.fbP101.xRunning": ua.VariantType.Boolean,
                "GVL_Hmi.stP101Cmd.xStart": ua.VariantType.Boolean,
                "GVL_IO.uiP101_FCODE": ua.VariantType.UInt16,
            }
            for path, vt in expect.items():
                dv = await c.get_node(NS + path).read_data_value()
                assert dv.Value is not None and dv.Value.VariantType == vt, path
            level = await c.get_node(NS + "GVL_Devices.fbLT101.stSts.rValue_eu").read_value()
            assert 0.0 < level < 5.0
            # все узлы перечня существуют
            nodes = [c.get_node(t.opcua_node_id) for t in load_tags()]
            values = await c.read_values(nodes)
            assert len(values) == 814

    run(pki, body)


def test_write_command_pulse_is_cleared(pki: Path) -> None:
    async def body(url: str, app: EmulatorApp) -> None:
        async with await user_client(url) as c:
            seq = c.get_node(NS + "GVL_Devices.fbP101.stSts.stCommon.uiCmdSeq")
            mode = c.get_node(NS + "GVL_Devices.fbP101.stSts.stCommon.eMode")
            result = c.get_node(NS + "GVL_Devices.fbP101.stSts.stCommon.eCmdResult")
            stop = c.get_node(NS + "GVL_Hmi.stP101Cmd.xStop")
            seq0 = await seq.read_value()
            assert await mode.read_value() == 1  # Auto
            await stop.write_value(ua.DataValue(ua.Variant(True, ua.VariantType.Boolean)))
            for _ in range(60):
                await asyncio.sleep(0.05)
                if not await stop.read_value():
                    break
            assert await stop.read_value() is False  # ПЛК сбросил импульс
            assert await seq.read_value() == seq0 + 1
            assert await result.read_value() == 1  # Accepted
            assert await mode.read_value() == 2  # «Стоп» в Auto → Manual
            # значение команды: задание скорости в Manual ограничивается пределами ПЧ
            sp = c.get_node(NS + "GVL_Hmi.stP101Cmd.rSpeedSp_pct")
            await sp.write_value(ua.DataValue(ua.Variant(150.0, ua.VariantType.Float)))
            await asyncio.sleep(0.4)
            assert await sp.read_value() == pytest.approx(100.0)
            # маска квитирования обнуляется
            ack = c.get_node(NS + "GVL_Hmi.stLT101Cmd.stCommon.wAckReq")
            await ack.write_value(ua.DataValue(ua.Variant(15, ua.VariantType.UInt16)))
            await asyncio.sleep(0.3)
            assert await ack.read_value() == 0

    run(pki, body)


def test_status_nodes_are_read_only_and_types_checked(pki: Path) -> None:
    async def body(url: str, app: EmulatorApp) -> None:
        async with await user_client(url) as c:
            level = c.get_node(NS + "GVL_Devices.fbLT101.stSts.rValue_eu")
            with pytest.raises(UaStatusCodeError):
                await level.write_value(ua.DataValue(ua.Variant(1.0, ua.VariantType.Float)))
            start = c.get_node(NS + "GVL_Hmi.stP101Cmd.xStart")
            with pytest.raises(UaStatusCodeError):  # INT в BOOL — BadTypeMismatch
                await start.write_value(ua.DataValue(ua.Variant(1, ua.VariantType.Int16)))

    run(pki, body)


def test_anonymous_read_only_and_bad_password(pki: Path) -> None:
    async def body(url: str, app: EmulatorApp) -> None:
        async with Client(url) as anon:
            assert await anon.get_node(NS + "GVL_Devices.fbLT101.xValid").read_value() in (True, False)
            with pytest.raises(UaStatusCodeError):
                await anon.get_node(NS + "GVL_Hmi.stP101Cmd.xStop").write_value(
                    ua.DataValue(ua.Variant(True, ua.VariantType.Boolean))
                )
        bad = Client(url)
        bad.set_user(USER)
        bad.set_password("wrong")
        with pytest.raises(UaStatusCodeError):
            await bad.connect()
        await asyncio.sleep(0)

    run(pki, body, allow_anonymous=True)


def test_anonymous_rejected_by_default(pki: Path) -> None:
    async def body(url: str, app: EmulatorApp) -> None:
        anon = Client(url)
        with pytest.raises((UaStatusCodeError, UaError)):
            await anon.connect()

    run(pki, body)


def test_basic256sha256_sign_and_encrypt(pki: Path, tmp_path: Path) -> None:
    async def body(url: str, app: EmulatorApp) -> None:
        assert (pki / "server_cert.der").is_file() and (pki / "server_key.pem").is_file()
        key, cert = tmp_path / "client_key.pem", tmp_path / "client_cert.der"
        app_uri = "urn:plc-iiot-stack:test-client"
        await setup_self_signed_certificate(
            key, cert, app_uri, "localhost", [ExtendedKeyUsageOID.CLIENT_AUTH], {"commonName": "test client"}
        )
        c = await user_client(url)
        c.application_uri = app_uri
        await c.set_security(
            SecurityPolicyBasic256Sha256,
            str(cert),
            str(key),
            server_certificate=str(pki / "server_cert.der"),
            mode=ua.MessageSecurityMode.SignAndEncrypt,
        )
        async with c:
            level = await c.get_node(NS + "GVL_Devices.fbLT101.stSts.rValue_eu").read_value()
            assert 0.0 < level < 5.0
        endpoints = await Client(url).connect_and_get_server_endpoints()
        modes = {(e.SecurityPolicyUri.rsplit("#", 1)[-1], e.SecurityMode) for e in endpoints}
        assert modes == {
            ("None", ua.MessageSecurityMode.None_),
            ("Basic256Sha256", ua.MessageSecurityMode.SignAndEncrypt),
        }

    run(pki, body)


def test_fault_injection_node(pki: Path) -> None:
    async def body(url: str, app: EmulatorApp) -> None:
        async with await user_client(url) as c:
            idx = await c.get_namespace_index("urn:plc-iiot-stack:kns-emulator:simulation")
            node = c.get_node(f"ns={idx};s=Simulation.Inject.lt101_wire_break")
            await node.write_value(ua.DataValue(ua.Variant(True, ua.VariantType.Boolean)))
            valid = c.get_node(NS + "GVL_Devices.fbLT101.xValid")
            for _ in range(80):
                await asyncio.sleep(0.05)
                if await valid.read_value() is False:
                    break
            assert await valid.read_value() is False
            assert app.emu.faults["lt101_wire_break"] is True

    run(pki, body)


def test_server_refuses_to_start_without_credentials(pki: Path) -> None:
    settings = Settings(opcua=OpcUaSettings(user="", password="", pki_dir=pki), mqtt=MqttSettings(enable=False))
    with pytest.raises(ValueError, match="EMU_OPCUA_USER"):
        EmulatorApp(settings)
