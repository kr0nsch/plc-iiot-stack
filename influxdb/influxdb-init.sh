#!/usr/bin/env bash
# Настройка InfluxDB 2 после первичной установки (сервис influxdb-init, запускается при каждом
# docker compose up и ничего не ломает при повторе):
#   1) срок хранения бакета сырых данных — из INFLUX_RETENTION;
#   2) бакет агрегатов INFLUX_BUCKET_AGG и задача прореживания kns_downsample_1h;
#   3) токены с минимальными правами: Telegraf — только запись в сырой бакет, Grafana — только
#      чтение обоих бакетов. Токены кладутся в том influx-tokens (файлы telegraf.token,
#      grafana.token); токен администратора наружу не выходит.
# Окружение: INFLUX_HOST, INFLUX_TOKEN (администратор), INFLUX_ORG, INFLUX_BUCKET,
# INFLUX_BUCKET_AGG, INFLUX_RETENTION, INFLUX_RETENTION_AGG, GRAFANA_UID. Описание — docs/ARCHITECTURE.md.
set -euo pipefail

TOKENS_DIR=/tokens
TASK_NAME=kns_downsample_1h
TASK_FILE=/init/tasks/downsample_1h.flux

log() { printf 'influxdb-init: %s\n' "$*"; }

for _ in $(seq 1 60); do
    if influx ping >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
influx ping >/dev/null

# Первый столбец вывода --hide-headers — ID (так же его читает entrypoint образа influxdb).
# Нет бакета — пустая строка: ошибка CLI при этом не должна обрывать скрипт (set -e, pipefail).
bucket_id() {
    { influx bucket list --org "$INFLUX_ORG" --name "$1" --hide-headers 2>/dev/null || true; } |
        awk -F '\t' 'NR == 1 { print $1 }'
}

raw_id="$(bucket_id "$INFLUX_BUCKET")"
if [ -z "$raw_id" ]; then
    log "нет бакета $INFLUX_BUCKET (первичная установка не прошла?)"
    exit 1
fi
influx bucket update --id "$raw_id" --retention "$INFLUX_RETENTION" >/dev/null
log "бакет $INFLUX_BUCKET: хранение $INFLUX_RETENTION"

agg_id="$(bucket_id "$INFLUX_BUCKET_AGG")"
if [ -z "$agg_id" ]; then
    influx bucket create --org "$INFLUX_ORG" --name "$INFLUX_BUCKET_AGG" --retention "$INFLUX_RETENTION_AGG" >/dev/null
    agg_id="$(bucket_id "$INFLUX_BUCKET_AGG")"
    log "создан бакет $INFLUX_BUCKET_AGG: хранение $INFLUX_RETENTION_AGG"
else
    influx bucket update --id "$agg_id" --retention "$INFLUX_RETENTION_AGG" >/dev/null
fi

# Задача прореживания: имена бакетов подставляются в текст задачи. Уже созданная задача получает
# текущий текст из репозитория (иначе исправления downsample_1h.flux не дошли бы до работающего стенда)
tmp="$(mktemp)"
sed -e "s/@RAW_BUCKET@/$INFLUX_BUCKET/g" -e "s/@AGG_BUCKET@/$INFLUX_BUCKET_AGG/g" "$TASK_FILE" >"$tmp"
task_id="$({ influx task list --org "$INFLUX_ORG" --hide-headers 2>/dev/null || true; } |
    awk -F '\t' -v name="$TASK_NAME" '$2 == name { print $1; exit }')"
if [ -n "$task_id" ]; then
    influx task update --id "$task_id" --file "$tmp" >/dev/null
    log "задача $TASK_NAME обновлена из $TASK_FILE"
else
    influx task create --org "$INFLUX_ORG" --file "$tmp" >/dev/null
    log "создана задача $TASK_NAME"
fi
rm -f "$tmp"

# Значение ключа из ответа influx auth create --json. CLI печатает объект с отступами, ключ — на
# своей строке; берётся первое вхождение: верхний уровень (id, token) идёт раньше вложенных прав.
json_value() {
    awk -v key="\"$1\":" 'index($0, key) { sub(/^[^:]*:[[:space:]]*"/, ""); sub(/".*$/, ""); print; exit }'
}

# $1 — имя (файлы <имя>.token, <имя>.id), $2 — владелец файла токена, далее — права influx auth create
ensure_token() {
    local name="$1" owner="$2"
    shift 2
    local token_file="$TOKENS_DIR/$name.token" id_file="$TOKENS_DIR/$name.id"
    if [ -s "$token_file" ] && [ -s "$id_file" ]; then
        local found
        found="$(influx auth list --id "$(cat "$id_file")" --hide-headers 2>/dev/null || true)"
        if [ -n "$found" ]; then
            log "токен $name уже есть"
            return 0
        fi
        log "токен $name из тома не найден в базе (том базы пересоздан?) — выпускается новый"
    fi
    local out token id
    out="$(influx auth create --org "$INFLUX_ORG" --description "stand-$name" "$@" --json)"
    token="$(printf '%s\n' "$out" | json_value token)"
    id="$(printf '%s\n' "$out" | json_value id)"
    if [ -z "$token" ] || [ -z "$id" ]; then
        log "не удалось разобрать ответ influx auth create для $name"
        exit 1
    fi
    umask 077
    printf '%s' "$token" >"$token_file"
    printf '%s' "$id" >"$id_file"
    chown "$owner" "$token_file"
    chmod 0400 "$token_file"
    log "выпущен токен $name"
}

mkdir -p "$TOKENS_DIR"
# Telegraf читает токен до понижения прав (скрипт входа работает от root)
ensure_token telegraf 0 --write-bucket "$raw_id"
# Grafana читает файл токена от своего пользователя (UID 472 в образе grafana/grafana)
ensure_token grafana "${GRAFANA_UID:-472}" --read-bucket "$raw_id" --read-bucket "$agg_id"

log "готово"
