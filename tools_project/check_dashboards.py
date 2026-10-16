"""Проверка дашбордов на поднятом стенде: каждый запрос каждой панели возвращает данные.

Назначение: критерий «данные на дашбордах» по панелям, а не по наличию дашбордов (stack_wait.py).
Запросы панелей выполняет сама Grafana (HTTP API ``POST /api/ds/query``) с источником
``influx-kns`` и диапазоном времени дашборда; переменные дашборда (``${source}``,
``${priority:regex}``, ``${tz}``) подставляются значениями по умолчанию — как при открытии.
Автор: <ИМЯ ФАМИЛИЯ>. Версия: 1.0. Описание стенда — docs/ARCHITECTURE.md.

    python tools_project/check_dashboards.py                       # Grafana на 127.0.0.1:GRAFANA_PORT
    python tools_project/check_dashboards.py --json build/dashboards_check.json

Код выхода: 0 — у всех панелей есть строки данных (списки отклонений из MAY_BE_EMPTY могут быть
пустыми, когда всё в норме), 1 — есть пустые панели или ошибки запросов.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from make_env import parse_keys

ROOT = Path(__file__).resolve().parent.parent
DASHBOARDS = ROOT / "grafana" / "dashboards"
DATASOURCE = {"uid": "influx-kns", "type": "influxdb"}
# Панели-списки отклонений: пусто, когда всё в норме (нет активных тревог, все устройства Good,
# за период не было срабатываний).
# Ошибка запроса в них — всё равно ошибка.
MAY_BE_EMPTY = frozenset(
    {
        ("kns1-overview", "Активные тревоги"),
        ("kns1-overview", "Диагностика NE 107: устройства не в норме"),
        ("kns1-alarms", "Текущее состояние тревог"),
        ("kns1-alarms", "Топ-10 тревог за период"),
    }
)


@dataclass
class PanelResult:
    dashboard: str
    panel_id: int
    title: str
    panel_type: str
    rows: int
    error: str

    @property
    def may_be_empty(self) -> bool:
        return (self.dashboard, self.title) in MAY_BE_EMPTY

    @property
    def ok(self) -> bool:
        return not self.error and (self.rows > 0 or self.may_be_empty)


def variable_values(dashboard: Mapping[str, Any]) -> dict[str, list[str]]:
    """Значения переменных по умолчанию: текущее значение custom, запрос constant; All — все варианты."""
    out: dict[str, list[str]] = {}
    for var in dashboard.get("templating", {}).get("list", []):
        name = var["name"]
        if var.get("type") == "constant":
            out[name] = [str(var.get("query", ""))]
            continue
        current = var.get("current", {}).get("value")
        values = current if isinstance(current, list) else [current]
        if "$__all" in values:
            values = [o["value"] for o in var.get("options", [])] or [
                part.split(":")[-1].strip() for part in str(var.get("query", "")).split(",") if part.strip()
            ]
        out[name] = [str(v) for v in values]
    return out


_VAR_RE = re.compile(r"\$\{(\w+)(?::(\w+))?\}|\$(\w+)")


def substitute(query: str, values: Mapping[str, list[str]]) -> str:
    """Подстановка как во фронтенде Grafana: ``${x}``, ``$x`` — значение, ``${x:regex}`` — (a|b)."""

    def repl(m: re.Match[str]) -> str:
        name = m.group(1) or m.group(3)
        if name not in values:
            return m.group(0)
        vals = values[name]
        if m.group(2) == "regex":
            return "(" + "|".join(re.escape(v) for v in vals) + ")" if len(vals) > 1 else re.escape(vals[0])
        return ",".join(vals)

    return _VAR_RE.sub(repl, query)


def panels(dashboard: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in dashboard.get("panels", []):
        if p.get("type") == "row":
            out.extend(p.get("panels", []))
        else:
            out.append(p)
    return out


def frame_rows(result: Mapping[str, Any]) -> int:
    rows = 0
    for frame in result.get("frames", []):
        values = frame.get("data", {}).get("values", [])
        if values:
            rows += len(values[0])
    return rows


def query_panel(url: str, auth: str, dashboard: Mapping[str, Any], panel: Mapping[str, Any]) -> PanelResult:
    values = variable_values(dashboard)
    time_range = dashboard.get("time", {"from": "now-6h", "to": "now"})
    queries = [
        {
            "refId": t.get("refId", "A"),
            "datasource": DATASOURCE,
            "query": substitute(t.get("query", ""), values),
            "intervalMs": 60000,
            "maxDataPoints": 1000,
        }
        for t in panel.get("targets", [])
    ]
    body = json.dumps({"queries": queries, "from": time_range["from"], "to": time_range["to"]}).encode("utf-8")
    req = urllib.request.Request(url + "/api/ds/query", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", auth)
    rows, errors = 0, []
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        data = json.loads(exc.read().decode("utf-8") or "{}")
        if "results" not in data:
            errors.append(f"HTTP {exc.code}: {data.get('message', '')}")
    for ref, result in (data.get("results") or {}).items():
        if result.get("error"):
            errors.append(f"{ref}: {result['error']}")
        rows += frame_rows(result)
    return PanelResult(
        dashboard=str(dashboard.get("uid")),
        panel_id=int(panel.get("id", 0)),
        title=str(panel.get("title", "")),
        panel_type=str(panel.get("type", "")),
        rows=rows,
        error="; ".join(errors),
    )


def check(url: str, user: str, password: str, files: Sequence[Path]) -> list[PanelResult]:
    auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
    results: list[PanelResult] = []
    for path in files:
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        results.extend(query_panel(url, auth, dashboard, p) for p in panels(dashboard))
    return results


def markdown(results: Sequence[PanelResult]) -> str:
    """Таблица панелей для сводки CI."""
    state = {True: "данные", False: "нет данных"}
    lines = [
        f"Панели дашбордов: {len(results)}, без данных или с ошибкой: {sum(1 for r in results if not r.ok)}",
        "",
        "| Дашборд | Панель | Строк | Итог |",
        "|---|---|---|---|",
    ]
    for r in results:
        verdict = state[r.ok] if r.rows or not r.ok else "пусто — всё в норме"
        if r.error:
            verdict = f"ошибка: {r.error}"
        lines.append(f"| {r.dashboard} | {r.title} | {r.rows} | {verdict} |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Проверка: у каждой панели дашбордов КНС-1 есть данные")
    ap.add_argument("--url", help="адрес Grafana (по умолчанию http://127.0.0.1:GRAFANA_PORT из .env)")
    ap.add_argument("--json", type=Path, help="записать результат в JSON")
    ap.add_argument("--markdown", type=Path, help="записать таблицу панелей в Markdown (сводка CI)")
    ap.add_argument("--retry-for", type=float, default=0.0, help="повторять, пока есть пустые панели, до N с")
    ap.add_argument("dashboards", nargs="*", type=Path, help="файлы дашбордов (по умолчанию grafana/dashboards/*.json)")
    args = ap.parse_args(argv)
    env_path = ROOT / ".env"
    env = parse_keys(env_path.read_text(encoding="utf-8")) if env_path.exists() else {}
    url = args.url or f"http://127.0.0.1:{env.get('GRAFANA_PORT', '3000')}"
    files = args.dashboards or sorted(DASHBOARDS.glob("*.json"))
    deadline = time.monotonic() + args.retry_for
    while True:
        try:
            results = check(url, env.get("GRAFANA_ADMIN_USER", "admin"), env.get("GRAFANA_ADMIN_PASSWORD", ""), files)
        except (urllib.error.URLError, OSError) as exc:
            print(f"Grafana недоступна ({url}): {exc}", file=sys.stderr)
            return 1
        bad = [r for r in results if not r.ok]
        if not bad or time.monotonic() > deadline:
            break
        print(f"пустых панелей: {len(bad)} — повтор через 10 с", flush=True)
        time.sleep(10)
    for r in results:
        mark = ("ok " if r.rows else "-- ") if r.ok else "НЕТ"
        detail = f"  {r.error}" if r.error else ""
        print(f"{mark} {r.dashboard:<14} #{r.panel_id:<3} {r.panel_type:<15} строк {r.rows:>5}  {r.title}{detail}")
    empty_ok = sum(1 for r in results if r.ok and not r.rows)
    print(
        f"панелей: {len(results)}, с данными: {len(results) - len(bad) - empty_ok},"
        f" пусто в норме (списки отклонений): {empty_ok}, пустых или с ошибкой: {len(bad)}"
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        rows = [asdict(r) | {"ok": r.ok, "may_be_empty": r.may_be_empty} for r in results]
        args.json.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(results), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
