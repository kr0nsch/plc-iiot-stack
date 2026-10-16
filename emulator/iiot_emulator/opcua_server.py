"""OPC UA-сервер эмулятора: адресное пространство как у символьной конфигурации CODESYS.

- Узлы переменных — с идентификаторами из ``scada_tags.csv`` (колонка opcua_node_id):
  ``ns=4;s=|var|CODESYS Control Win V3.Application.GVL_Devices.fbLT101.stSts.rValue_eu``. Клиент,
  настроенный на эмулятор, без правок работает с рантаймом CODESYS (и наоборот).
- Типы — как в ПЛК: BOOL → Boolean, INT → Int16, WORD и UINT → UInt16, UDINT → UInt32,
  REAL → Float. Запись — только в команды ``GVL_Hmi.st<DEV>Cmd.*`` (AccessLevel CurrentWrite).
- Импульсные биты и маски эмулятор сбрасывает после обработки в ближайшем цикле — как ФБ
  plc-process-lib (API 2.1): клиент видит TRUE → FALSE и рост ``CmdSeq``.
- Безопасность: конечные точки None и Basic256Sha256 Sign&Encrypt, самоподписанный сертификат
  (``pki.py``), пользователь и пароль из окружения. Без пароля сервер не стартует, если не
  разрешён анонимный доступ; анонимный клиент только читает.
- Пространства имён: 0 — OPC UA, 1 — сервер, 2–3 — резерв (у CODESYS там модели DI и PLCopen),
  4 — символы приложения, 5 — узлы эмулятора ``Simulation`` (отказы, время модели). Номер 4
  совпадает с тем, что генератор iolistgen записал в перечень; сверять по обзору сервера.
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Callable
from typing import Any

from asyncua import ua
from asyncua.crypto.permission_rules import USER_TYPES, SimpleRoleRuleset, User, UserRole
from asyncua.server.address_space import NodeData
from asyncua.server.server import Server
from asyncua.server.user_managers import UserManager
from asyncua.ua.attribute_ids import AttributeIds
from asyncua.ua.object_ids import ObjectIds

from .config import OpcUaSettings
from .emulator import CommandError, KnsEmulator
from .faults import ACTIONS, FAULTS
from .pki import ensure_server_certificate
from .tagmodel import TagDef

log = logging.getLogger(__name__)

APP_URI = "urn:plc-iiot-stack:kns-emulator"
SYMBOL_NS_URI = "urn:plc-iiot-stack:kns-emulator:symbols"
SIM_NS_URI = "urn:plc-iiot-stack:kns-emulator:simulation"

VARIANT: dict[str, ua.VariantType] = {
    "BOOL": ua.VariantType.Boolean,
    "INT": ua.VariantType.Int16,
    "UINT": ua.VariantType.UInt16,
    "WORD": ua.VariantType.UInt16,
    "DINT": ua.VariantType.Int32,
    "UDINT": ua.VariantType.UInt32,
    "DWORD": ua.VariantType.UInt32,
    "REAL": ua.VariantType.Float,
    "LREAL": ua.VariantType.Double,
}

_WRITTEN = object()  # метка «узел записан клиентом»

# Анонимный клиент: сессия, чтение, обзор, подписки — без записи и вызова методов
_READ_ONLY_TYPES = [
    t
    for t in USER_TYPES
    if t
    not in (
        ObjectIds.WriteRequest_Encoding_DefaultBinary,
        ObjectIds.CallRequest_Encoding_DefaultBinary,
        ObjectIds.HistoryReadRequest_Encoding_DefaultBinary,
    )
]


class RoleRuleset(SimpleRoleRuleset):
    """Права: пользователь — чтение и запись (что разрешено AccessLevel узла), аноним — чтение."""

    def __init__(self) -> None:  # базовый словарь прав SimpleRoleRuleset не нужен
        self._allowed = {
            UserRole.Admin: {ua.NodeId(ua.Int32(t)) for t in USER_TYPES},
            UserRole.User: {ua.NodeId(ua.Int32(t)) for t in USER_TYPES},
            UserRole.Anonymous: {ua.NodeId(ua.Int32(t)) for t in _READ_ONLY_TYPES},
        }

    def check_validity(self, user: User, action_type_id: ua.NodeId, body: Any) -> bool:
        return action_type_id in self._allowed.get(user.role, set())


class EnvUserManager(UserManager):
    """Один пользователь из окружения; сравнение пароля за постоянное время."""

    def __init__(self, user: str, password: str, allow_anonymous: bool) -> None:
        self._user = user
        self._password = password
        self._anon = allow_anonymous

    def get_user(
        self, iserver: Any, username: str | None = None, password: str | None = None, certificate: Any = None
    ) -> User | None:
        if username is None:
            return User(role=UserRole.Anonymous) if self._anon else None
        if not self._user or not self._password:
            return None
        ok_user = hmac.compare_digest(username.encode("utf-8"), self._user.encode("utf-8"))
        ok_pass = hmac.compare_digest((password or "").encode("utf-8"), self._password.encode("utf-8"))
        return User(role=UserRole.User, name=username) if ok_user and ok_pass else None


def sid(identifier: str, ns: int) -> ua.NodeId:
    """Строковый NodeId ``ns=<ns>;s=<identifier>``."""
    return ua.NodeId(ua.String(identifier), ua.Int16(ns))


def _py_value(data_type: str, value: Any) -> Any:
    if data_type == "BOOL":
        return bool(value)
    if data_type in ("REAL", "LREAL"):
        return float(value)
    return int(value)


class OpcUaMirror:
    """Сервер OPC UA поверх ``KnsEmulator``; синхронизация — вызовами ``apply_writes``/``publish``."""

    def __init__(self, emu: KnsEmulator, settings: OpcUaSettings) -> None:
        if not settings.allow_anonymous and not (settings.user and settings.password):
            raise ValueError(
                "OPC UA: задайте EMU_OPCUA_USER и EMU_OPCUA_PASSWORD (или EMU_OPCUA_ALLOW_ANONYMOUS=1 — только чтение)"
            )
        self.emu = emu
        self.s = settings
        self.server = Server(user_manager=EnvUserManager(settings.user, settings.password, settings.allow_anonymous))
        self._nodes: dict[str, ua.NodeId] = {}  # тег → узел
        self._types: dict[str, str] = {}
        self._last: dict[str, Any] = {}
        self._pending: dict[str, Any] = {}  # записи клиентов: тег → значение
        self._internal = False
        self._sim_nodes: dict[str, ua.NodeId] = {}
        self._inject_nodes: dict[ua.NodeId, str] = {}
        self._pending_inject: dict[str, bool] = {}
        self.rejected_writes = 0
        self.ns = settings.namespace_index

    # --- запуск -------------------------------------------------------------------------------------
    async def start(self) -> None:
        srv = self.server
        await srv.init()
        srv.set_endpoint(self.s.endpoint)
        srv.set_server_name("KNS-1 PLC emulator (plc-iiot-stack)")
        await srv.set_application_uri(APP_URI)
        srv.product_uri = "urn:plc-iiot-stack:kns-emulator"
        srv.manufacturer_name = "plc-iiot-stack"
        cert, key = await ensure_server_certificate(self.s.pki_dir, APP_URI, self.s.hostname)
        await srv.load_certificate(str(cert))
        await srv.load_private_key(str(key))
        srv.set_security_policy(
            [ua.SecurityPolicyType.NoSecurity, ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt],
            permission_ruleset=RoleRuleset(),
        )
        tokens: list[type] = [ua.UserNameIdentityToken]
        if self.s.allow_anonymous:
            tokens.append(ua.AnonymousIdentityToken)
        srv.set_identity_tokens(tokens)
        srv.allow_remote_admin(False)
        # пространства имён: символы приложения должны получить номер ns (4, как у CODESYS)
        idx = len(await srv.get_namespace_array())
        while idx < self.ns:
            await srv.register_namespace(f"urn:plc-iiot-stack:kns-emulator:reserved-ns{idx}")
            idx += 1
        sym_idx = await srv.register_namespace(SYMBOL_NS_URI)
        if sym_idx != self.ns:
            raise RuntimeError(f"пространство имён символов получило номер {sym_idx}, ожидался {self.ns}")
        self.sim_ns = await srv.register_namespace(SIM_NS_URI)
        await self._build_symbols()
        await self._build_simulation()
        await srv.start()
        log.info("OPC UA: %s, узлов переменных: %d", self.s.endpoint, len(self._nodes))

    async def stop(self) -> None:
        await self.server.stop()

    # --- адресное пространство ----------------------------------------------------------------------
    def _sid(self, path: str) -> ua.NodeId:
        return sid(f"|var|{self.s.device_name}.{path}", self.ns)

    async def _build_symbols(self) -> None:
        srv = self.server
        objects = srv.nodes.objects
        device_set = await objects.add_folder(sid("DeviceSet", self.ns), ua.QualifiedName("DeviceSet", self.ns))
        device = await device_set.add_object(
            sid(self.s.device_name, self.ns), ua.QualifiedName(self.s.device_name, self.ns)
        )
        resources = await device.add_folder(
            sid(f"{self.s.device_name}.Resources", self.ns), ua.QualifiedName("Resources", self.ns)
        )
        app = await resources.add_object(self._sid("Application"), ua.QualifiedName("Application", self.ns))
        containers: dict[str, Any] = {"Application": app}

        for tag in self.emu.tags:
            parts = tag.plc_path.split(".")
            parent = app
            for i in range(1, len(parts) - 1):
                path = ".".join(parts[: i + 1])
                node = containers.get(path)
                if node is None:
                    node = await parent.add_object(self._sid(path), ua.QualifiedName(parts[i], self.ns))
                    containers[path] = node
                parent = node
            await self._add_variable(parent, tag)

    async def _add_variable(self, parent: Any, tag: TagDef) -> None:
        nodeid = self._sid(tag.plc_path)
        if nodeid.to_string() != tag.opcua_node_id and self.ns == 4 and self.s.device_name == "CODESYS Control Win V3":
            raise RuntimeError(f"{tag.tag}: узел {nodeid.to_string()} не совпадает с {tag.opcua_node_id}")
        value = self.emu.read_tag(tag.tag)
        vtype = VARIANT[tag.data_type]
        var = await parent.add_variable(
            nodeid, ua.QualifiedName(tag.plc_path.split(".")[-1], self.ns), ua.Variant(value, vtype), varianttype=vtype
        )
        await var.write_attribute(AttributeIds.Description, ua.DataValue(ua.Variant(ua.LocalizedText(tag.description))))
        if tag.writable:
            await var.set_writable(True)
            self.server.set_attribute_value_setter(nodeid, self._make_setter(tag))
        self._nodes[tag.tag] = nodeid
        self._types[tag.tag] = tag.data_type
        self._last[tag.tag] = value

    def _make_setter(self, tag: TagDef) -> Callable[[NodeData, AttributeIds, ua.DataValue], None]:
        def setter(node: NodeData, attr: AttributeIds, dv: ua.DataValue) -> None:
            node.attributes[attr].value = dv
            node.attributes[attr].value_callback = None
            if not self._internal and dv.Value is not None:
                self._pending[tag.tag] = dv.Value.Value
                self._last[tag.tag] = _WRITTEN  # следующая публикация перезапишет узел значением ПЛК

        return setter

    async def _build_simulation(self) -> None:
        srv = self.server
        ns = self.sim_ns
        sim = await srv.nodes.objects.add_folder(sid("Simulation", ns), ua.QualifiedName("Simulation", ns))
        info = {
            "SimTime_s": (ua.VariantType.Double, 0.0),
            "SimHour": (ua.VariantType.Double, 0.0),
            "TimeFactor": (ua.VariantType.Double, 0.0),
            "Seed": (ua.VariantType.Int32, self.emu.cfg.seed),
            "Inflow_m3h": (ua.VariantType.Double, 0.0),
            "PumpsRequired": (ua.VariantType.Int16, 0),
            "DutyPump": (ua.VariantType.String, ""),
            "Emergency": (ua.VariantType.Boolean, False),
            "Degraded": (ua.VariantType.Boolean, False),
        }
        for name, (vt, val) in info.items():
            nid = sid(f"Simulation.{name}", ns)
            await sim.add_variable(nid, ua.QualifiedName(name, ns), ua.Variant(val, vt), varianttype=vt)
            self._sim_nodes[name] = nid
        inject = await sim.add_folder(sid("Simulation.Inject", ns), ua.QualifiedName("Inject", ns))
        for name, text in {**FAULTS, **ACTIONS}.items():
            nid = sid(f"Simulation.Inject.{name}", ns)
            var = await inject.add_variable(
                nid,
                ua.QualifiedName(name, ns),
                ua.Variant(False, ua.VariantType.Boolean),
                varianttype=ua.VariantType.Boolean,
            )
            await var.write_attribute(AttributeIds.Description, ua.DataValue(ua.Variant(ua.LocalizedText(text))))
            await var.set_writable(True)
            self._inject_nodes[nid] = name
            self.server.set_attribute_value_setter(nid, self._make_inject_setter(name))

    def _make_inject_setter(self, name: str) -> Callable[[NodeData, AttributeIds, ua.DataValue], None]:
        def setter(node: NodeData, attr: AttributeIds, dv: ua.DataValue) -> None:
            node.attributes[attr].value = dv
            node.attributes[attr].value_callback = None
            if not self._internal and dv.Value is not None:
                self._pending_inject[name] = bool(dv.Value.Value)
                self._last[f"inj:{name}"] = _WRITTEN

        return setter

    # --- синхронизация с эмулятором -----------------------------------------------------------------
    def apply_writes(self) -> int:
        """Передать записи клиентов в эмулятор (команды и отказы). Возвращает число записей."""
        n = 0
        pending, self._pending = self._pending, {}
        for tag, value in pending.items():
            try:
                self.emu.write_tag(tag, value)
                n += 1
            except CommandError as exc:
                self.rejected_writes += 1
                log.warning("OPC UA: запись %s отклонена: %s", tag, exc)
        injects, self._pending_inject = self._pending_inject, {}
        for name, on in injects.items():
            self.emu.inject(name, on)
            n += 1
        return n

    async def publish(self, time_factor: float = 0.0) -> int:
        """Записать в узлы изменившиеся значения образа ПЛК. Возвращает число записанных узлов."""
        image = self.emu.image()
        changed = 0
        self._internal = True
        try:
            for tag, value in image.items():
                if self._last.get(tag) == value:
                    continue
                nodeid = self._nodes.get(tag)
                if nodeid is None:
                    continue
                dtype = self._types[tag]
                dv = ua.DataValue(ua.Variant(_py_value(dtype, value), VARIANT[dtype]))
                await self.server.write_attribute_value(nodeid, dv)
                self._last[tag] = value
                changed += 1
            st = self.emu.station.state
            sim_vals: dict[str, Any] = {
                "SimTime_s": float(self.emu.t),
                "SimHour": float(self.emu.sim_hour),
                "TimeFactor": float(time_factor),
                "Inflow_m3h": float(self.emu.plant.inflow_m3h),
                "PumpsRequired": int(st.n_required),
                "DutyPump": next((k for k, v in st.roles.items() if v == "duty"), ""),
                "Emergency": bool(st.emergency),
                "Degraded": bool(st.degraded),
            }
            for name, val in sim_vals.items():
                if self._last.get(f"sim:{name}") == val:
                    continue
                nid = self._sim_nodes[name]
                vt = (
                    ua.VariantType.Double
                    if isinstance(val, float)
                    else ua.VariantType.Boolean
                    if isinstance(val, bool)
                    else ua.VariantType.String
                    if isinstance(val, str)
                    else ua.VariantType.Int16
                )
                await self.server.write_attribute_value(nid, ua.DataValue(ua.Variant(val, vt)))
                self._last[f"sim:{name}"] = val
            for nid, name in self._inject_nodes.items():
                cur = self.emu.faults.get(name, False)
                if self._last.get(f"inj:{name}") != cur:
                    await self.server.write_attribute_value(nid, ua.DataValue(ua.Variant(cur, ua.VariantType.Boolean)))
                    self._last[f"inj:{name}"] = cur
        finally:
            self._internal = False
        return changed

    def node_id(self, tag: str) -> ua.NodeId:
        return self._nodes[tag]
