# Стенд IIoT КНС-1: docker compose и проверки (Linux, macOS, WSL; Windows — tools_project/make.ps1).
#   make up | demo | down | clean | test | test-stack | certs | gen | config | logs | ps
# Флаги: TLS=1 — слушатель MQTT TLS (docker-compose.tls.yml), DEV=1 — порт InfluxDB на 127.0.0.1
# (docker-compose.dev.yml). Описание — docs/ARCHITECTURE.md.

PYTHON ?= python3
COMPOSE ?= docker compose
COMPOSE_FILES := docker-compose.yml
ifeq ($(TLS),1)
COMPOSE_FILES += docker-compose.tls.yml
endif
ifeq ($(DEV),1)
COMPOSE_FILES += docker-compose.dev.yml
endif
DC := $(COMPOSE) $(addprefix -f ,$(COMPOSE_FILES))
COMMA := ,
SPACE := $(subst ,, )
WAIT := $(PYTHON) tools_project/stack_wait.py $(addprefix --compose-file ,$(COMPOSE_FILES))
PROFILES := --profile demo --profile nodered

.DEFAULT_GOAL := help
.PHONY: help env up demo nodered down clean test test-stack certs gen config logs ps

help:
	@echo "make env        создать или пополнить .env из .env.example (случайные пароли)"
	@echo "make up         брокер, InfluxDB, Telegraf, Grafana; ждать готовности"
	@echo "make demo       то же и эмулятор ПЛК; ждать данных на дашбордах (до 5 мин)"
	@echo "make nodered    Node-RED (профиль nodered) на 127.0.0.1:1880"
	@echo "make down       остановить стенд (данные в томах сохраняются)"
	@echo "make clean      остановить и удалить тома (все данные стенда)"
	@echo "make test       pytest: схемы, конфигурация, генераторы, эмулятор, отчёт"
	@echo "make test-stack интеграционный тест на поднятом стенде и проверка панелей дашбордов"
	@echo "make certs      локальный УЦ и сертификат брокера для make up TLS=1"
	@echo "make gen        перегенерировать дашборды, узлы OPC UA и таблицы схемы данных"
	@echo "make config     проверить docker-compose.yml (docker compose config)"

env:
	$(PYTHON) tools_project/make_env.py

up: env
	$(DC) up -d
	$(WAIT)

demo: env
	$(DC) --profile demo up -d --build
	$(WAIT) --emulator --data

nodered: env
	$(DC) --profile nodered up -d

down:
	$(DC) $(PROFILES) down

clean:
	$(DC) $(PROFILES) down --volumes

test:
	$(PYTHON) -m pytest
	@for d in emulator report; do \
	if [ -f $$d/pyproject.toml ] && [ -d $$d/tests ]; then \
	echo "== pytest $$d"; (cd $$d && $(PYTHON) -m pytest) || exit 1; \
	fi; \
	done

test-stack:
	IIOT_STACK=1 IIOT_COMPOSE_FILES=$(subst $(SPACE),$(COMMA),$(strip $(COMPOSE_FILES))) $(PYTHON) -m pytest -m stack tests_stack
	$(PYTHON) tools_project/check_dashboards.py --retry-for 120 --json build/dashboards_check.json --markdown build/dashboards_check.md

certs:
	bash tools_project/gen_mqtt_certs.sh

gen:
	$(PYTHON) tools_project/gen_config.py

config: env
	$(DC) $(PROFILES) config --quiet

logs:
	$(DC) $(PROFILES) logs --tail 100

ps:
	$(DC) $(PROFILES) ps --all
