<#
.SYNOPSIS
    Стенд IIoT КНС-1 для Windows: то же, что Makefile (make up, make demo, make down, make test...).

.DESCRIPTION
    Нужны Docker Desktop (docker compose v2) и Python 3.11+. Запуск из корня репозитория:

        powershell -ExecutionPolicy Bypass -File tools_project\make.ps1 demo
        powershell -File tools_project\make.ps1 up -Tls      # слушатель MQTT TLS (сначала: certs)
        powershell -File tools_project\make.ps1 up -Dev      # порт InfluxDB на 127.0.0.1 для отчёта

    Совместим с Windows PowerShell 5.1 и PowerShell 7. Файл в UTF-8 с BOM: без BOM Windows
    PowerShell 5.1 читает скрипт в кодировке ANSI и портит русский текст.
    Описание стенда — docs/ARCHITECTURE.md.

.PARAMETER Target
    help, env, up, demo, nodered, down, clean, test, test-stack, certs, gen, config, logs, ps.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'env', 'up', 'demo', 'nodered', 'down', 'clean', 'test', 'test-stack', 'certs', 'gen', 'config', 'logs', 'ps')]
    [string]$Target = 'help',
    [switch]$Tls,
    [switch]$Dev
)

$ErrorActionPreference = 'Stop'
# Вывод Python и docker в UTF-8 (русские сообщения при перенаправлении вывода)
$env:PYTHONUTF8 = '1'
$PrevOutputEncoding = [Console]::OutputEncoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ($env:PYTHON) { $Python = $env:PYTHON } else { $Python = 'python' }

$ComposeFiles = @('docker-compose.yml')
if ($Tls) { $ComposeFiles += 'docker-compose.tls.yml' }
if ($Dev) { $ComposeFiles += 'docker-compose.dev.yml' }
$ComposeArgs = @('compose')
foreach ($f in $ComposeFiles) { $ComposeArgs += @('-f', $f) }
$WaitArgs = @('tools_project/stack_wait.py')
foreach ($f in $ComposeFiles) { $WaitArgs += @('--compose-file', $f) }
$Profiles = @('--profile', 'demo', '--profile', 'nodered')

# Запуск внешней программы с остановкой при ненулевом коде возврата
function Invoke-Native {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Exe завершился с кодом $LASTEXITCODE"
    }
}

function Invoke-Compose {
    param([string[]]$Arguments)
    Invoke-Native 'docker' ($ComposeArgs + $Arguments)
}

function Invoke-Env {
    Invoke-Native $Python @('tools_project/make_env.py')
}

try {
    switch ($Target) {
        'help' {
            Write-Host 'tools_project\make.ps1 <цель> [-Tls] [-Dev]'
            Write-Host '  env        создать или пополнить .env из .env.example (случайные пароли)'
            Write-Host '  up         брокер, InfluxDB, Telegraf, Grafana; ждать готовности'
            Write-Host '  demo       то же и эмулятор ПЛК; ждать данных на дашбордах (до 5 мин)'
            Write-Host '  nodered    Node-RED (профиль nodered) на 127.0.0.1:1880'
            Write-Host '  down       остановить стенд (данные в томах сохраняются)'
            Write-Host '  clean      остановить и удалить тома (все данные стенда)'
            Write-Host '  test       pytest: схемы, конфигурация, генераторы, эмулятор, отчёт'
            Write-Host '  test-stack интеграционный тест на поднятом стенде и проверка панелей дашбордов'
            Write-Host '  certs      локальный УЦ и сертификат брокера (нужен bash и openssl из Git for Windows)'
            Write-Host '  gen        перегенерировать дашборды, узлы OPC UA и таблицы схемы данных'
            Write-Host '  config     проверить docker-compose.yml'
        }
        'env' { Invoke-Env }
        'up' {
            Invoke-Env
            Invoke-Compose @('up', '-d')
            Invoke-Native $Python $WaitArgs
        }
        'demo' {
            Invoke-Env
            Invoke-Compose @('--profile', 'demo', 'up', '-d', '--build')
            Invoke-Native $Python ($WaitArgs + @('--emulator', '--data'))
        }
        'nodered' {
            Invoke-Env
            Invoke-Compose @('--profile', 'nodered', 'up', '-d')
        }
        'down' { Invoke-Compose ($Profiles + @('down')) }
        'clean' { Invoke-Compose ($Profiles + @('down', '--volumes')) }
        'test' {
            Invoke-Native $Python @('-m', 'pytest')
            foreach ($d in @('emulator', 'report')) {
                if ((Test-Path "$d/pyproject.toml") -and (Test-Path "$d/tests")) {
                    Write-Host "== pytest $d"
                    Push-Location $d
                    try { Invoke-Native $Python @('-m', 'pytest') } finally { Pop-Location }
                }
            }
        }
        'test-stack' {
            $env:IIOT_STACK = '1'
            $env:IIOT_COMPOSE_FILES = $ComposeFiles -join ','
            try { Invoke-Native $Python @('-m', 'pytest', '-m', 'stack', 'tests_stack') }
            finally { Remove-Item Env:IIOT_STACK, Env:IIOT_COMPOSE_FILES }
            Invoke-Native $Python @('tools_project/check_dashboards.py', '--retry-for', '120', '--json', 'build/dashboards_check.json', '--markdown', 'build/dashboards_check.md')
        }
        'certs' { Invoke-Native 'bash' @('tools_project/gen_mqtt_certs.sh') }
        'gen' { Invoke-Native $Python @('tools_project/gen_config.py') }
        'config' {
            Invoke-Env
            Invoke-Compose ($Profiles + @('config', '--quiet'))
        }
        'logs' { Invoke-Compose ($Profiles + @('logs', '--tail', '100')) }
        'ps' { Invoke-Compose ($Profiles + @('ps', '--all')) }
    }
}
finally {
    [Console]::OutputEncoding = $PrevOutputEncoding
}
