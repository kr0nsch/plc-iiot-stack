#!/bin/sh
# Запуск Telegraf стенда (POSIX sh, образ telegraf на Alpine).
# Токен InfluxDB (только запись в бакет сырых данных) выпускает сервис influxdb-init и кладёт в
# том influx-tokens; здесь он читается в INFLUX_TOKEN (telegraf.conf: token = "${INFLUX_TOKEN}").
# Вход OPC UA (telegraf.d/opcua.conf) подключается, если OPCUA_ENABLED=true; с политикой не None —
# сертификат клиента в томе telegraf-pki (OPCUA_CERTIFICATE, OPCUA_PRIVATE_KEY).
#
# Штатный /entrypoint.sh образа не используется: он выдаёт бинарнику telegraf возможности
# cap_net_raw и cap_net_bind_service (setcap) для входов ping и привилегированных портов. Стенду они
# не нужны, а с no-new-privileges (docker-compose.yml) запуск бинарника с файловыми возможностями
# ядро может запретить. Права понижаются до пользователя telegraf тем же средством, что и в образе (setpriv или su-exec).
set -eu

PKI_DIR=/var/lib/telegraf/pki
token_file="${INFLUX_TOKEN_FILE:-/run/influx-tokens/telegraf.token}"
if [ ! -s "$token_file" ]; then
    echo "telegraf: нет токена InfluxDB в $token_file (его выпускает сервис influxdb-init)" >&2
    exit 1
fi
INFLUX_TOKEN="$(cat "$token_file")"
export INFLUX_TOKEN

# Подстановка ${...} из окружения — строгая (умолчание Telegraf с 1.38, задано явно — без
# предупреждения при каждом запуске): только внутри строк конфигурации, все ${...} в telegraf.conf
# и telegraf.d — строки (tests_stack/test_telegraf.py)
set -- telegraf --strict-env-handling --config /etc/telegraf/telegraf.conf
case "${OPCUA_ENABLED:-true}" in
    true | 1 | yes)
        set -- "$@" --config-directory /etc/telegraf/telegraf.d
        echo "telegraf: вход OPC UA включён: ${OPCUA_ENDPOINT:-?}"
        # Сертификат клиента нужен только с защищённой политикой. Без файлов Telegraf создаёт
        # самоподписанный по заданным путям; в томе telegraf-pki он переживает пересоздание контейнера,
        # и в доверенные сервера CODESYS его кладут один раз (docs/security.md, 4.2).
        if [ "${OPCUA_SECURITY_POLICY:-None}" != "None" ]; then
            OPCUA_CERTIFICATE="${OPCUA_CERTIFICATE:-$PKI_DIR/cert.pem}"
            OPCUA_PRIVATE_KEY="${OPCUA_PRIVATE_KEY:-$PKI_DIR/key.pem}"
            if [ "$(id -u)" = 0 ]; then
                mkdir -p "$PKI_DIR"
                chown telegraf:telegraf "$PKI_DIR"
                chmod 0700 "$PKI_DIR"
            fi
            echo "telegraf: сертификат клиента OPC UA: $OPCUA_CERTIFICATE"
        else
            OPCUA_CERTIFICATE=""
            OPCUA_PRIVATE_KEY=""
        fi
        export OPCUA_CERTIFICATE OPCUA_PRIVATE_KEY
        ;;
    *)
        echo "telegraf: вход OPC UA выключен (OPCUA_ENABLED=${OPCUA_ENABLED:-})"
        ;;
esac

# Сброс прав до пользователя telegraf: в образах telegraf до 1.2x — su-exec, в новых (1.39) — setpriv
if [ "$(id -u)" = 0 ]; then
    if command -v setpriv >/dev/null 2>&1; then
        exec setpriv --reuid telegraf --regid telegraf --init-groups "$@"
    fi
    if command -v su-exec >/dev/null 2>&1; then
        exec su-exec telegraf "$@"
    fi
    echo "telegraf: нет setpriv и su-exec — запуск от root" >&2
fi
exec "$@"
