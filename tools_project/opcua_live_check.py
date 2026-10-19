"""Сверка узлов стенда с живым OPC UA-сервером рантайма CODESYS (флагман КНС-1 в имитации).

Назначение: то, что раздел 12 docs/MANUAL_STEPS.md велит сверить при первом подключении стенда к флагману,
одной командой и без Docker:

- вход: политика Basic256Sha256, режим SignAndEncrypt, имя и пароль пользователя рантайма, сертификат
  клиента из доверенных сервера; пределы операций сервера (``OperationLimits``);
- пространство имён переменных МЭК и префикс узлов (имя устройства) — как ``OPCUA_NAMESPACE`` и
  ``OPCUA_ID_PREFIX`` в ``.env``;
- все узлы каталога с путём ПЛК (``schema/telemetry_catalog.csv``): есть, статус Good, тип значения
  совпадает с типом по снимку флагмана (перечисления — Int16);
- инверсия ``K1/general_alarm``: значение ``GVL_IO.xK1`` и ожидаемое значение метрики;
- ``GVL_Iiot.stIiotSts`` (``PRG_Iiot`` работает в задаче флагмана) и отсутствие узла пароля брокера;
- с ``--commands``: команды станции и регулятора LIC101 записью в ``GVL_Station.stStationCmd`` и
  ``stLIC101Cmd`` (как HMI или ``PRG_Iiot``) — растёт ли ``uiCmdSeq`` и какой ``eCmdResult``; режим
  возвращается обратной командой.

Учётные данные — JSON ``{"user": ..., "password": ...}`` (по умолчанию файл рантайма из
``CODESYS_RUNTIME_CREDENTIALS`` или ``~/.local/plc-tools/cds-runtime/credentials.json``); в вывод не
попадают. Сертификат клиента по умолчанию — клиента сценариев флагмана (``sim.py pki`` кладёт его в
доверенные): ``~/.local/plc-tools/opcua-client/client_cert.der`` и ``client_key.pem``.

Автор: kr0nsch. Документ: docs/MANUAL_STEPS.md, раздел 12.

Запуск (флагман в имитации: ``python tools_project/codesys/sim.py start`` в его репозитории)::

    python tools_project/opcua_live_check.py                       # opc.tcp://127.0.0.1:4840
    python tools_project/opcua_live_check.py --commands --json build/opcua_live_check.json

Код выхода: 0 — всё сошлось, 1 — есть расхождения, 2 — нет подключения или аргументы.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import flagship_symbols as fs
import stack_catalog as sc

DEFAULT_ENDPOINT = "opc.tcp://127.0.0.1:4840"
DEFAULT_CREDENTIALS = Path("~/.local/plc-tools/cds-runtime/credentials.json")
DEFAULT_CERT_DIR = Path("~/.local/plc-tools/opcua-client")
IEC_NAMESPACE_SUFFIX = "IecVarAccess"
DEVICE_SET = "DeviceSet"
NOT_DEVICES = frozenset({"DeviceFeatures"})  # служебный узел DeviceSet сервера CODESYS
# Предел узлов в запросе, пока сервер не сообщил свой (OPC UA-сервер CODESYS 3.5.17 — 100)
DEFAULT_MAX_NODES = 100
COMMAND_TIMEOUT_S = 5.0
CMD_RESULT_ACCEPTED = 1

# Тип МЭК (снимок флагмана, перечисления — их база) -> VariantType OPC UA
IEC_TO_VARIANT = {
    "BOOL": "Boolean",
    "SINT": "SByte",
    "USINT": "Byte",
    "BYTE": "Byte",
    "INT": "Int16",
    "UINT": "UInt16",
    "WORD": "UInt16",
    "DINT": "Int32",
    "UDINT": "UInt32",
    "DWORD": "UInt32",
    "LINT": "Int64",
    "ULINT": "UInt64",
    "LWORD": "UInt64",
    "REAL": "Float",
    "LREAL": "Double",
    "STRING": "String",
}
OPERATION_LIMITS = (
    "MaxNodesPerRead",
    "MaxNodesPerWrite",
    "MaxNodesPerRegisterNodes",
    "MaxNodesPerBrowse",
    "MaxMonitoredItemsPerCall",
)
IIOT_STS = ("eConnState", "eNe107", "xClockValid", "diLastError", "udiCmdAccepted")
PASSWORD_NODE = "GVL_Iiot.stIiotCfg.stBroker.sPassword"


class CheckError(Exception):
    """Нет подключения или не найдены пространство имён, устройство, файлы."""


@dataclass
class Report:
    endpoint: str
    security: str = ""
    namespace: int = -1
    namespace_uri: str = ""
    device: str = ""
    id_prefix: str = ""
    operation_limits: dict[str, int] = field(default_factory=dict)
    nodes_total: int = 0
    nodes_good: int = 0
    types: dict[str, int] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    inversion: dict[str, Any] = field(default_factory=dict)
    iiot: dict[str, Any] = field(default_factory=dict)
    commands: list[dict[str, Any]] = field(default_factory=list)


# --- чистые функции (проверяются без сервера) -----------------------------------------------------------
def expected_variant(iec_type: str) -> str | None:
    return IEC_TO_VARIANT.get(iec_type.split("(")[0].strip().upper())


def chunks(items: Sequence[Any], size: int) -> list[Sequence[Any]]:
    size = max(1, size)
    return [items[i : i + size] for i in range(0, len(items), size)]


def find_iec_namespace(namespaces: Sequence[str]) -> int:
    for index, uri in enumerate(namespaces):
        if uri.endswith(IEC_NAMESPACE_SUFFIX):
            return index
    raise CheckError(f"нет пространства имён *{IEC_NAMESPACE_SUFFIX}: это не OPC UA-сервер CODESYS?")


def id_prefix(device: str) -> str:
    """Префикс идентификатора узла, как ``OPCUA_ID_PREFIX`` в ``.env``."""
    return f"|var|{device}."


def catalog_paths(root: Path = sc.REPO) -> list[tuple[str, str, str, bool]]:
    """(устройство, метрика, путь ПЛК, инверсия) метрик каталога с путём ПЛК."""
    return [(m.device, m.metric, m.plc_path, m.invert) for m in sc.load_catalog(root) if m.plc_path]


def check_types(
    paths: Sequence[str], actual: Mapping[str, str], symbols: fs.FlagshipSymbols
) -> tuple[dict[str, int], list[str]]:
    """Сводка типов узлов и расхождения с типами по снимку флагмана."""
    counts: dict[str, int] = {}
    problems = []
    for path in paths:
        got = actual.get(path, "")
        counts[got] = counts.get(got, 0) + 1
        want = expected_variant(symbols.resolve(path).iec_type)
        if want is None or got != want:
            problems.append(f"{path}: тип {got or 'нет'}, по снимку флагмана {want or 'неизвестен'}")
    return counts, problems


def load_credentials(path: Path | None) -> tuple[str, str]:
    raw = os.environ.get("CODESYS_RUNTIME_CREDENTIALS")
    target = path or (Path(raw) if raw else DEFAULT_CREDENTIALS.expanduser())
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return str(data["user"]), str(data["password"])
    except (OSError, ValueError, KeyError) as exc:
        raise CheckError(f"учётные данные {target}: нет файла или полей user и password") from exc


# --- сервер ----------------------------------------------------------------------------------------------
def application_uri(cert_der: bytes) -> str:
    from cryptography import x509

    cert = x509.load_der_x509_certificate(cert_der)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    uris = san.get_values_for_type(x509.UniformResourceIdentifier)
    if not uris:
        raise CheckError("в сертификате клиента нет URI приложения (SubjectAltName)")
    return str(uris[0])


def connect(endpoint: str, cert_dir: Path, credentials: tuple[str, str]) -> Any:
    from asyncua.sync import Client

    cert, key = cert_dir / "client_cert.der", cert_dir / "client_key.pem"
    if not cert.is_file() or not key.is_file():
        raise CheckError(f"нет сертификата клиента в {cert_dir} (client_cert.der, client_key.pem)")
    client = Client(endpoint, timeout=10)
    client.application_uri = application_uri(cert.read_bytes())
    client.set_security_string(f"Basic256Sha256,SignAndEncrypt,{cert},{key}")
    client.set_user(credentials[0])
    client.set_password(credentials[1])
    try:
        client.connect()
    except Exception as exc:
        raise CheckError(f"{endpoint}: вход не удался ({type(exc).__name__}: {exc})") from exc
    return client


def discover_device(client: Any) -> str:
    """Имя устройства ПЛК — узел ``Objects/DeviceSet``, кроме служебных (``DeviceFeatures``)."""
    for child in client.nodes.objects.get_children():
        if child.read_browse_name().Name != DEVICE_SET:
            continue
        for dev in child.get_children():
            name = str(dev.read_browse_name().Name)
            if name not in NOT_DEVICES:
                return name
    raise CheckError(f"в {DEVICE_SET} нет устройства ПЛК")


def operation_limits(client: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    limits = client.nodes.server.get_child(["0:ServerCapabilities", "0:OperationLimits"])
    for name in OPERATION_LIMITS:
        try:
            out[name] = int(limits.get_child([f"0:{name}"]).read_value())
        except Exception:  # предел не объявлен сервером
            continue
    return out


def read_many(client: Any, node_ids: Sequence[str], max_nodes: int) -> list[Any]:
    """DataValue узлов пакетами не больше ``max_nodes`` (иначе сервер отвечает BadTooManyOperations)."""
    from asyncua import ua
    from asyncua.ua.attribute_ids import AttributeIds

    out: list[Any] = []
    for part in chunks(node_ids, max_nodes):
        params = ua.ReadParameters()
        for nid in part:
            rv = ua.ReadValueId()
            rv.NodeId = ua.NodeId.from_string(nid)
            rv.AttributeId = AttributeIds.Value
            params.NodesToRead.append(rv)
        out += client.tloop.post(client.aio_obj.uaclient.read(params))
    return out


def run_commands(client: Any, node: Callable[[str], str]) -> list[dict[str, Any]]:
    """Команда и обратная команда станции и LIC101; запись — импульс, как с HMI."""
    from asyncua import ua

    def read(path: str) -> Any:
        return client.get_node(node(path)).read_value()

    def pulse(path: str) -> None:
        client.get_node(node(path)).write_value(ua.DataValue(ua.Variant(True, ua.VariantType.Boolean)))

    def one(name: str, cmd: str, seq_path: str, res_path: str, mode_path: str) -> dict[str, Any]:
        seq0, mode0 = int(read(seq_path)), int(read(mode_path))
        pulse(cmd)
        deadline = time.monotonic() + COMMAND_TIMEOUT_S
        seq = seq0
        while time.monotonic() < deadline and seq == seq0:
            time.sleep(0.2)
            seq = int(read(seq_path))
        return {
            "command": name,
            "write": cmd,
            "uiCmdSeq": [seq0, seq],
            "eCmdResult": int(read(res_path)),
            "eMode": [mode0, int(read(mode_path))],
        }

    out = []
    st = "Application.GVL_Station."
    station = (st + "stStationSts.uiCmdSeq", st + "stStationSts.eCmdResult", st + "stStationSts.eMode")
    lic = st + "fbLIC101.stSts.stCommon."
    pid = (lic + "uiCmdSeq", lic + "eCmdResult", lic + "eMode")
    manual = 2  # E_StationMode.Manual и PL.E_DeviceMode.Manual
    for label, cmd_base, paths in (
        ("KNS1", st + "stStationCmd.", station),
        ("LIC101", st + "stLIC101Cmd.stCommon.", pid),
    ):
        to_manual = int(read(paths[2])) != manual
        first, back = ("SetManual", "SetAuto") if to_manual else ("SetAuto", "SetManual")
        for name in (first, back):
            out.append(one(f"{label} {name}", f"{cmd_base}x{name}", *paths))
    return out


def check(endpoint: str, cert_dir: Path, credentials: tuple[str, str], commands: bool) -> Report:
    report = Report(endpoint=endpoint, security="Basic256Sha256 SignAndEncrypt, UserName")
    client = connect(endpoint, cert_dir, credentials)
    try:
        namespaces = client.get_namespace_array()
        report.namespace = find_iec_namespace(namespaces)
        report.namespace_uri = namespaces[report.namespace]
        report.device = discover_device(client)
        report.id_prefix = id_prefix(report.device)
        report.operation_limits = operation_limits(client)
        max_nodes = report.operation_limits.get("MaxNodesPerRead") or DEFAULT_MAX_NODES

        def node(path: str) -> str:
            return f"ns={report.namespace};s={report.id_prefix}{path}"

        metrics = catalog_paths()
        paths = [p for _, _, p, _ in metrics]
        values = read_many(client, [node(p) for p in paths], max_nodes)
        report.nodes_total = len(paths)
        actual: dict[str, str] = {}
        for path, dv in zip(paths, values, strict=True):
            if dv.StatusCode.is_good():
                report.nodes_good += 1
            else:
                report.problems.append(f"{path}: статус {dv.StatusCode.name}")
            actual[path] = dv.Value.VariantType.name if dv.Value is not None else ""
        report.types, type_problems = check_types(paths, actual, fs.load())
        report.problems += type_problems
        for (device, metric, path, invert), dv in zip(metrics, values, strict=True):
            if invert and dv.StatusCode.is_good():
                raw = bool(dv.Value.Value)
                report.inversion[f"{device}/{metric}"] = {"plc_path": path, "plc_value": raw, "metric": int(not raw)}
        # GVL_Iiot есть в символах, только если ПЛК-часть встроена во флагман (с правилом GVL_Iiot): иначе статусы
        # BadNodeIdUnknown — это сведения, а не расхождение (путь OPC UA работает и без встраивания)
        sts = read_many(client, [node(f"Application.GVL_Iiot.stIiotSts.{f}") for f in IIOT_STS], max_nodes)
        report.iiot = {
            f: (dv.Value.Value if dv.StatusCode.is_good() else dv.StatusCode.name)
            for f, dv in zip(IIOT_STS, sts, strict=True)
        }
        pw = read_many(client, [node(f"Application.{PASSWORD_NODE}")], max_nodes)[0]
        report.iiot["sPassword_node"] = pw.StatusCode.name
        if pw.StatusCode.is_good():
            report.problems.append(f"{PASSWORD_NODE}: узел пароля брокера читается")
        if commands:
            report.commands = run_commands(client, node)
            for c in report.commands:
                if c["uiCmdSeq"][1] == c["uiCmdSeq"][0]:
                    report.problems.append(f"{c['command']}: uiCmdSeq не изменился за {COMMAND_TIMEOUT_S:.0f} с")
    finally:
        client.disconnect()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--credentials", type=Path, help="JSON с user и password (по умолчанию файл рантайма)")
    parser.add_argument("--cert-dir", type=Path, default=DEFAULT_CERT_DIR, help="client_cert.der и client_key.pem")
    parser.add_argument("--commands", action="store_true", help="проверить команды станции и LIC101 (запись)")
    parser.add_argument("--json", type=Path, help="записать отчёт в файл")
    args = parser.parse_args(argv)
    try:
        report = check(args.endpoint, args.cert_dir.expanduser(), load_credentials(args.credentials), args.commands)
    except CheckError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 2
    data = report.__dict__
    print(f"сервер {report.endpoint}: {report.security}")
    print(f"пространство имён {report.namespace} ({report.namespace_uri}); префикс узлов «{report.id_prefix}»")
    print(f"пределы операций: {report.operation_limits}")
    print(f"узлы каталога: {report.nodes_good} из {report.nodes_total} Good; типы: {report.types}")
    print(f"инверсия: {report.inversion}")
    print(f"GVL_Iiot.stIiotSts: {report.iiot}")
    for c in report.commands:
        print(f"команда {c['command']}: uiCmdSeq {c['uiCmdSeq']}, eCmdResult {c['eCmdResult']}, eMode {c['eMode']}")
    for line in report.problems:
        print(f"расхождение: {line}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    return 1 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
