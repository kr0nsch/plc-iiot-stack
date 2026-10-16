# Образ эмулятора ПЛК КНС-1 для docker compose (профиль demo): пакет emulator/ (kns-emulator).
# Контекст сборки — корень репозитория; в образ попадают только emulator/ и файл версий
# зависимостей (emulator.Dockerfile.dockerignore). Зависимости — прямые и транзитивные — закреплены в
# emulator-constraints.txt, чтобы образ собирался одинаково в CI и у пользователя.
FROM python:3.12.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY docker/emulator-constraints.txt /tmp/constraints.txt
COPY emulator/ /src/
# pyproject.toml эмулятора ссылается на README.md: без файла сборка пакета остановится
RUN test -f /src/README.md || echo "kns-emulator" > /src/README.md; \
    pip install --constraint /tmp/constraints.txt /src \
    && rm -rf /src /tmp/constraints.txt \
    && useradd --system --uid 10001 --home-dir /var/lib/emulator --create-home emulator

USER emulator
WORKDIR /var/lib/emulator
# OPC UA (opc.tcp); сертификаты сервера — в EMU_OPCUA_PKI_DIR (по умолчанию ./pki)
EXPOSE 4840
ENTRYPOINT ["kns-emulator"]
CMD ["run"]
