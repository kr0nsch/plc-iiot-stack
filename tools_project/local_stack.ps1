<#
.SYNOPSIS
    Локальный стенд КНС-1 без Docker и без прав администратора: брокер MQTT, InfluxDB 2, Telegraf,
    Grafana и эмулятор ПЛК как обычные процессы Windows с конфигурацией репозитория.

.DESCRIPTION
    Для проверки и демонстрации на компьютере, где нет Docker. Основной способ запуска стенда —
    docker compose (make demo); различия — docs/ARCHITECTURE.md, раздел «Локальный стенд без Docker».

        powershell -ExecutionPolicy Bypass -File tools_project\local_stack.ps1 install
        powershell -ExecutionPolicy Bypass -File tools_project\local_stack.ps1 start -Emulator
        powershell -ExecutionPolicy Bypass -File tools_project\local_stack.ps1 status
        powershell -ExecutionPolicy Bypass -File tools_project\local_stack.ps1 stop

    install  — официальные сборки для Windows тех же версий, что образы docker-compose.yml
               (InfluxDB 2 и Telegraf — dl.influxdata.com, Grafana OSS — dl.grafana.com; SHA-256
               сверяется), каждая в свой каталог %USERPROFILE%\.local\plc-tools\iiot\<компонент>;
               брокер MQTT — amqtt (Python) в своём venv: Mosquitto для Windows ставится только
               установщиком с правами администратора.
    start    — брокер (пользователи и ACL из .env и mosquitto/config/acl.template), InfluxDB
               (первичная установка, бакет агрегатов, задача прореживания, токены Telegraf и Grafana —
               как influxdb/influxdb-init.sh), Telegraf (telegraf/telegraf.conf и telegraf.d,
               окружение из docker-compose.yml с адресами 127.0.0.1), Grafana (провиженинг
               grafana/provisioning с путями хоста, дашборды grafana/dashboards). С -Emulator —
               ещё эмулятор ПЛК (OPC UA на 127.0.0.1:4841, MQTT) и ожидание данных на дашбордах.
    stop     — остановить процессы (данные в build\local-stack сохраняются; -Clean — удалить их).
    status   — PID, проверка здоровья и адрес каждого сервиса.
    logs     — последние строки журналов build\local-stack\logs.

    Секреты — из .env (создаётся из .env.example со случайными паролями, если его нет).
    Совместим с Windows PowerShell 5.1 и PowerShell 7. Файл в UTF-8 с BOM (иначе Windows
    PowerShell 5.1 портит русский текст).

.PARAMETER Action
    install, start, stop, status, logs.

.PARAMETER Emulator
    start: запустить эмулятор ПЛК и дождаться данных на дашбордах (аналог make demo).

.PARAMETER AnonymousViewer
    start: Grafana на 127.0.0.1 открывает дашборды без входа, только для чтения — для снимков
    экрана безголовым браузером. В docker compose анонимный доступ выключен.

.PARAMETER Clean
    stop: удалить и состояние стенда (база, токены, журналы) в build\local-stack.

.PARAMETER Timeout
    start -Emulator: предел ожидания данных на дашбордах, с (по умолчанию 300).
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('install', 'start', 'stop', 'status', 'logs')]
    [string]$Action = 'status',
    [switch]$Emulator,
    [switch]$AnonymousViewer,
    [switch]$Clean,
    [int]$Timeout = 300
)

$ErrorActionPreference = 'Stop'
# Вывод Python в UTF-8 (русские сообщения при перенаправлении вывода)
$env:PYTHONUTF8 = '1'
$PrevOutputEncoding = [Console]::OutputEncoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ($env:PYTHON) { $Python = $env:PYTHON } else { $Python = 'python' }
$Helper = Join-Path $PSScriptRoot 'local_stack.py'
if ($env:LOCAL_STACK_STATE) { $State = $env:LOCAL_STACK_STATE } else { $State = Join-Path $Root 'build\local-stack' }
if ($env:IIOT_TOOLS_DIR) { $Tools = $env:IIOT_TOOLS_DIR } else { $Tools = Join-Path $env:USERPROFILE '.local\plc-tools\iiot' }
$LogDir = Join-Path $State 'logs'
# Порядок запуска; остановка — в обратном порядке
$Services = @('broker', 'influxdb', 'telegraf', 'grafana', 'emulator')

function Invoke-Helper {
    param([string[]]$Arguments, [string]$Interpreter = $Python)
    & $Interpreter $Helper @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "local_stack.py $($Arguments -join ' ') завершился с кодом $LASTEXITCODE"
    }
}

# Запуск — local_stack.py launch: процесс без консоли, вне задания (job) оболочки и без
# унаследованных дескрипторов (иначе канал вывода PowerShell или CI оставался бы открытым)
function Start-StackService {
    param([string]$Name)
    Invoke-Helper @('launch', $Name)
    Invoke-Helper @('wait', $Name, '--timeout', '120')
    Write-Host "$Name готов"
}

try {
    switch ($Action) {
        'install' {
            Invoke-Helper @('install')
        }
        'start' {
            # Как make env: создаёт .env или дописывает ключи, появившиеся в .env.example
            & $Python tools_project/make_env.py
            if ($LASTEXITCODE -ne 0) { throw 'make_env.py завершился с ошибкой' }
            if ($AnonymousViewer) { $env:LOCAL_GRAFANA_ANONYMOUS = '1' }
            $amqttPython = Join-Path $Tools 'amqtt\venv\Scripts\python.exe'
            if (-not (Test-Path $amqttPython)) { throw "нет $amqttPython — сначала: local_stack.ps1 install" }
            Invoke-Helper @('broker-config') $amqttPython
            Invoke-Helper @('grafana-provisioning')
            Start-StackService 'broker'
            Start-StackService 'influxdb'
            Invoke-Helper @('influx-init')
            Start-StackService 'telegraf'
            Start-StackService 'grafana'
            if ($Emulator) {
                Start-StackService 'emulator'
                Invoke-Helper @('wait-data', '--timeout', "$Timeout")
            }
            Invoke-Helper @('status')
        }
        'stop' {
            [array]::Reverse($Services)
            # вместе с дочерними процессами (amqtt.exe запускает python.exe)
            foreach ($s in $Services) { Invoke-Helper @('stop', $s) }
            if ($Clean -and (Test-Path $State)) {
                Remove-Item -Recurse -Force $State
                Write-Host "удалено состояние стенда: $State"
            }
        }
        'status' {
            & $Python $Helper status
        }
        'logs' {
            Get-ChildItem $LogDir -Filter '*.log' -ErrorAction SilentlyContinue | ForEach-Object {
                Write-Host "== $($_.Name)"
                Get-Content $_.FullName -Tail 20
            }
        }
    }
}
finally {
    [Console]::OutputEncoding = $PrevOutputEncoding
}
