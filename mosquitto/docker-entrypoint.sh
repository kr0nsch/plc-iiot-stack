#!/bin/sh
# Запуск Mosquitto стенда КНС-1 (POSIX sh, образ eclipse-mosquitto на Alpine).
# 1. Файл паролей из .env: четыре роли (ПЛК, Telegraf, оператор, мониторинг), хэши — mosquitto_passwd.
# 2. ACL из mosquitto/config/acl.template с именами пользователей и корнем топиков из .env.
# 3. Итоговый конфиг: mosquitto.conf и, если MQTT_TLS=true, слушатель TLS из tls.conf.
# Всё генерируется при каждом старте в /mosquitto/run/ — в томах и в git паролей нет.
set -eu

CONF=/mosquitto/config
RUN=/mosquitto/run
CERTS=/mosquitto/certs

fail() {
    echo "mosquitto: $*" >&2
    exit 1
}

# Значение переменной окружения по имени
env_value() {
    eval "printf '%s' \"\${$1:-}\""
}

check_name() {
    case "$2" in
        '' | *[!A-Za-z0-9_-]*) fail "$1='$2': допустимы латинские буквы, цифры, _ и -" ;;
    esac
}

mkdir -p "$RUN"
umask 077
rm -f "$RUN/passwd" "$RUN/acl" "$RUN/mosquitto.conf"

root="${MQTT_TOPIC_ROOT:-vodokanal}"
check_name MQTT_TOPIC_ROOT "$root"

first=1
for role in PLC TELEGRAF OPERATOR MONITOR; do
    user="$(env_value "MQTT_${role}_USER")"
    pass="$(env_value "MQTT_${role}_PASSWORD")"
    check_name "MQTT_${role}_USER" "$user"
    [ -n "$pass" ] || fail "не задан MQTT_${role}_PASSWORD (.env)"
    case "$pass" in
        change-me*) fail "MQTT_${role}_PASSWORD не изменён: make env создаёт .env со случайными паролями" ;;
    esac
    if [ "$first" = 1 ]; then
        mosquitto_passwd -c -b "$RUN/passwd" "$user" "$pass"
        first=0
    else
        mosquitto_passwd -b "$RUN/passwd" "$user" "$pass"
    fi
done

sed -e "s/@ROOT@/$root/g" \
    -e "s/@PLC_USER@/$(env_value MQTT_PLC_USER)/g" \
    -e "s/@TELEGRAF_USER@/$(env_value MQTT_TELEGRAF_USER)/g" \
    -e "s/@OPERATOR_USER@/$(env_value MQTT_OPERATOR_USER)/g" \
    -e "s/@MONITOR_USER@/$(env_value MQTT_MONITOR_USER)/g" \
    "$CONF/acl.template" >"$RUN/acl"

cp "$CONF/mosquitto.conf" "$RUN/mosquitto.conf"
case "${MQTT_TLS:-false}" in
    true | 1 | yes)
        for f in ca.crt server.crt server.key; do
            [ -s "$CERTS/$f" ] || fail "нет $CERTS/$f: выполните make certs (tools_project/gen_mqtt_certs.sh)"
        done
        mkdir -p "$RUN/certs"
        cp "$CERTS/ca.crt" "$CERTS/server.crt" "$CERTS/server.key" "$RUN/certs/"
        { echo; cat "$CONF/tls.conf"; } >>"$RUN/mosquitto.conf"
        echo "mosquitto: слушатель TLS 8883 включён"
        ;;
esac

chown -R mosquitto:mosquitto "$RUN"
chmod 0700 "$RUN"
exec /usr/sbin/mosquitto -c "$RUN/mosquitto.conf"
