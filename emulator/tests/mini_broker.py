"""Минимальный брокер MQTT 3.1.1 для тестов эмулятора (asyncio, 127.0.0.1).

Только для тестов: на машине разработки нет Docker и Mosquitto, а проверять настоящий клиент
paho (завещание, retain, QoS 1, подписки с ``+``) без брокера нельзя. Поддержано подмножество
протокола, которое использует эмулятор: CONNECT (логин и пароль, завещание), PUBLISH QoS 0/1,
PUBACK, SUBSCRIBE (фильтры ``+`` и ``#``), retain, PINGREQ, DISCONNECT. Интеграция с
настоящим Mosquitto проверяется в CI стенда (docker compose).
"""

from __future__ import annotations

import asyncio
import contextlib
import struct
import threading
from dataclasses import dataclass, field


def topic_matches(flt: str, topic: str) -> bool:
    f_parts = flt.split("/")
    t_parts = topic.split("/")
    for i, fp in enumerate(f_parts):
        if fp == "#":
            return True
        if i >= len(t_parts):
            return False
        if fp != "+" and fp != t_parts[i]:
            return False
    return len(f_parts) == len(t_parts)


def _enc_str(s: str | bytes) -> bytes:
    b = s.encode("utf-8") if isinstance(s, str) else s
    return struct.pack("!H", len(b)) + b


def _enc_len(n: int) -> bytes:
    out = bytearray()
    while True:
        byte = n % 128
        n //= 128
        if n:
            byte |= 0x80
        out.append(byte)
        if not n:
            return bytes(out)


@dataclass
class Message:
    topic: str
    payload: bytes
    qos: int
    retain: bool
    sender: str = ""


@dataclass
class Session:
    client_id: str
    writer: asyncio.StreamWriter
    subs: dict[str, int] = field(default_factory=dict)
    will: Message | None = None
    next_mid: int = 1


class MiniBroker:
    def __init__(self, users: dict[str, str] | None = None) -> None:
        self.users = users  # None — без авторизации
        self.retained: dict[str, Message] = {}
        self.log: list[Message] = []  # все принятые публикации
        self.sessions: dict[str, Session] = {}
        self.port = 0
        self._server: asyncio.base_events.Server | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self.connects = 0
        self.rejected_logins = 0

    # --- запуск в отдельном потоке ------------------------------------------------------------------
    def start(self) -> MiniBroker:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(5):
            raise RuntimeError("брокер не стартовал")
        return self

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._server = self._loop.run_until_complete(asyncio.start_server(self._handle, "127.0.0.1", 0))
        self.port = self._server.sockets[0].getsockname()[1]
        self._ready.set()
        self._loop.run_forever()

    def stop(self) -> None:
        if self._loop is None:
            return

        async def _close() -> None:
            assert self._server is not None
            self._server.close()
            for s in list(self.sessions.values()):
                s.writer.close()

        fut = asyncio.run_coroutine_threadsafe(_close(), self._loop)
        fut.result(5)
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(5)

    def kill_client(self, client_id: str) -> None:
        """Оборвать соединение клиента (как при потере сети): брокер публикует завещание."""
        assert self._loop is not None
        s = self.sessions.get(client_id)
        if s is not None:
            self._loop.call_soon_threadsafe(s.writer.transport.abort)

    def publish_from_test(self, topic: str, payload: bytes, *, retain: bool = False, qos: int = 1) -> None:
        assert self._loop is not None
        msg = Message(topic, payload, qos, retain, sender="test")
        asyncio.run_coroutine_threadsafe(self._route(msg), self._loop).result(5)

    def messages(self, prefix: str = "") -> list[Message]:
        return [m for m in list(self.log) if m.topic.startswith(prefix)]

    # --- протокол -----------------------------------------------------------------------------------
    async def _read_packet(self, reader: asyncio.StreamReader) -> tuple[int, int, bytes]:
        hdr = await reader.readexactly(1)
        mult, length = 1, 0
        while True:
            b = (await reader.readexactly(1))[0]
            length += (b & 0x7F) * mult
            if not b & 0x80:
                break
            mult *= 128
        body = await reader.readexactly(length) if length else b""
        return hdr[0] >> 4, hdr[0] & 0x0F, body

    async def _send(self, s: Session, data: bytes) -> None:
        s.writer.write(data)
        await s.writer.drain()

    async def _deliver(self, s: Session, msg: Message, qos: int, retain_flag: bool) -> None:
        q = min(qos, msg.qos)
        flags = (q << 1) | (1 if retain_flag else 0)
        var = _enc_str(msg.topic)
        if q > 0:
            var += struct.pack("!H", s.next_mid)
            s.next_mid = s.next_mid % 65535 + 1
        body = var + msg.payload
        await self._send(s, bytes([0x30 | flags]) + _enc_len(len(body)) + body)

    async def _route(self, msg: Message) -> None:
        self.log.append(msg)
        if msg.retain:
            if msg.payload:
                self.retained[msg.topic] = msg
            else:
                self.retained.pop(msg.topic, None)
        for s in list(self.sessions.values()):
            for flt, qos in s.subs.items():
                if topic_matches(flt, msg.topic):
                    with contextlib.suppress(ConnectionError, OSError):
                        await self._deliver(s, msg, qos, False)
                    break

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        session: Session | None = None
        clean = False
        try:
            ptype, _, body = await self._read_packet(reader)
            if ptype != 1:
                writer.close()
                return
            session = self._parse_connect(body, writer)
            if session is None:
                writer.write(b"\x20\x02\x00\x05")  # CONNACK: не авторизован
                await writer.drain()
                writer.close()
                return
            old = self.sessions.get(session.client_id)
            if old is not None:
                old.will = None
                old.writer.close()
            self.sessions[session.client_id] = session
            self.connects += 1
            await self._send(session, b"\x20\x02\x00\x00")
            while True:
                ptype, flags, body = await self._read_packet(reader)
                if ptype == 3:  # PUBLISH
                    qos = (flags >> 1) & 3
                    retain = bool(flags & 1)
                    tlen = struct.unpack("!H", body[:2])[0]
                    topic = body[2 : 2 + tlen].decode("utf-8")
                    pos = 2 + tlen
                    if qos > 0:
                        mid = struct.unpack("!H", body[pos : pos + 2])[0]
                        pos += 2
                        await self._send(session, b"\x40\x02" + struct.pack("!H", mid))
                    await self._route(Message(topic, body[pos:], qos, retain, session.client_id))
                elif ptype == 8:  # SUBSCRIBE
                    mid = body[:2]
                    pos, granted = 2, []
                    new_filters = []
                    while pos < len(body):
                        flen = struct.unpack("!H", body[pos : pos + 2])[0]
                        flt = body[pos + 2 : pos + 2 + flen].decode("utf-8")
                        qos = body[pos + 2 + flen] & 3
                        pos += 3 + flen
                        session.subs[flt] = min(qos, 1)
                        granted.append(min(qos, 1))
                        new_filters.append(flt)
                    await self._send(session, bytes([0x90]) + _enc_len(2 + len(granted)) + mid + bytes(granted))
                    for flt in new_filters:
                        for m in list(self.retained.values()):
                            if topic_matches(flt, m.topic):
                                await self._deliver(session, m, session.subs[flt], True)
                elif ptype == 10:  # UNSUBSCRIBE
                    await self._send(session, b"\xb0\x02" + body[:2])
                elif ptype == 12:  # PINGREQ
                    await self._send(session, b"\xd0\x00")
                elif ptype == 14:  # DISCONNECT
                    clean = True
                    break
                # PUBACK (4) от клиента и прочее — игнорируем
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass
        finally:
            if session is not None and self.sessions.get(session.client_id) is session:
                del self.sessions[session.client_id]
                if not clean and session.will is not None:
                    await self._route(session.will)
            writer.close()

    def _parse_connect(self, body: bytes, writer: asyncio.StreamWriter) -> Session | None:
        plen = struct.unpack("!H", body[:2])[0]
        pos = 2 + plen + 1  # имя протокола и уровень
        flags = body[pos]
        pos += 1 + 2  # флаги и keepalive

        def read_str() -> bytes:
            nonlocal pos
            n = struct.unpack("!H", body[pos : pos + 2])[0]
            v = body[pos + 2 : pos + 2 + n]
            pos += 2 + n
            return v

        client_id = read_str().decode("utf-8")
        will = None
        if flags & 0x04:
            wtopic = read_str().decode("utf-8")
            wpayload = read_str()
            will = Message(wtopic, wpayload, (flags >> 3) & 3, bool(flags & 0x20), client_id)
        user = read_str().decode("utf-8") if flags & 0x80 else None
        password = read_str().decode("utf-8") if flags & 0x40 else None
        if self.users is not None and (user is None or self.users.get(user) != password):
            self.rejected_logins += 1
            return None
        return Session(client_id=client_id, writer=writer, will=will)
