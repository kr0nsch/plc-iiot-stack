#!/usr/bin/env bash
# Локальный удостоверяющий центр и сертификаты для слушателя MQTT TLS стенда (make certs).
# Только для стенда: на объекте сертификаты выпускает УЦ предприятия (docs/security.md).
#
#   tools_project/gen_mqtt_certs.sh [--out DIR] [--san DNS:имя|IP:адрес]... [--client ИМЯ]... [--force]
#
# Создаёт в DIR (по умолчанию mosquitto/certs):
#   ca.key, ca.crt           — УЦ стенда (RSA 3072, 10 лет); ca.crt раздаётся клиентам (ПЛК, тесты)
#   server.key, server.crt   — брокер (RSA 2048, 825 сут), SAN: mosquitto, localhost, 127.0.0.1 и --san
#   <ИМЯ>.key, <ИМЯ>.crt     — клиентские сертификаты для mTLS (--client plc)
# Ключи в git не попадают (mosquitto/certs/.gitignore). Нужен openssl (в Git for Windows он есть).
set -euo pipefail
# Git Bash иначе превращает "/CN=..." в путь Windows
export MSYS_NO_PATHCONV=1

out="mosquitto/certs"
force=0
sans=("DNS:mosquitto" "DNS:localhost" "IP:127.0.0.1")
clients=()

while [ $# -gt 0 ]; do
    case "$1" in
        --out) out="$2"; shift 2 ;;
        --san) sans+=("$2"); shift 2 ;;
        --client) clients+=("$2"); shift 2 ;;
        --force) force=1; shift ;;
        -h | --help) sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
    esac
done

command -v openssl >/dev/null || { echo "нужен openssl" >&2; exit 1; }
mkdir -p "$out"
cd "$out"
umask 077

if [ -s ca.key ] && [ "$force" = 0 ]; then
    echo "УЦ уже есть ($out/ca.crt); новый — с --force"
else
    openssl req -x509 -newkey rsa:3072 -sha256 -days 3650 -nodes \
        -keyout ca.key -out ca.crt -subj "/O=plc-iiot-stack/CN=KNS-1 stand local CA" \
        -addext "basicConstraints=critical,CA:TRUE" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null
    echo "создан УЦ: $out/ca.crt"
    force=1
fi

# $1 — имя файлов, $2 — CN, $3 — назначение (serverAuth|clientAuth), $4 — SAN или пусто
issue() {
    local name="$1" cn="$2" usage="$3" san="$4" ext
    if [ -s "$name.crt" ] && [ "$force" = 0 ]; then
        echo "сертификат $name уже есть"
        return 0
    fi
    # Файл расширений — относительный путь в каталоге вывода: openssl из Git for Windows не
    # понимает пути MSYS вида /tmp/... (MSYS_NO_PATHCONV=1 отключает их перевод)
    ext="$name.ext"
    {
        echo "basicConstraints=critical,CA:FALSE"
        echo "keyUsage=critical,digitalSignature,keyEncipherment"
        echo "extendedKeyUsage=$usage"
        if [ -n "$san" ]; then
            echo "subjectAltName=$san"
        fi
    } >"$ext"
    openssl req -newkey rsa:2048 -nodes -keyout "$name.key" -out "$name.csr" \
        -subj "/O=plc-iiot-stack/CN=$cn" 2>/dev/null
    openssl x509 -req -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
        -out "$name.crt" -days 825 -sha256 -extfile "$ext" 2>/dev/null
    rm -f "$name.csr" "$ext"
    echo "выпущен сертификат $name: CN=$cn${san:+, $san}"
}

san_list="$(IFS=,; echo "${sans[*]}")"
issue server mosquitto serverAuth "$san_list"
for c in "${clients[@]+"${clients[@]}"}"; do
    issue "$c" "$c" clientAuth ""
done

# Сертификаты открыты для чтения: контейнер копирует их себе и меняет владельца (docker-entrypoint.sh)
chmod 0644 ./*.crt
chmod 0600 ./*.key
openssl verify -CAfile ca.crt server.crt
