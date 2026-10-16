// Задача InfluxDB: часовые агрегаты телеметрии для долгого хранения (docs/data_schema.md, раздел 7).
// Бакеты @RAW_BUCKET@ и @AGG_BUCKET@ подставляет influxdb/influxdb-init.sh при создании задачи.
// now() задачи — плановое время запуска (граница часа); offset только откладывает запуск, чтобы
// успели прийти точки последних секунд часа. Точка агрегата — на конце часа (_time = граница).
//
// Телеметрия MQTT публикуется по изменению (зона нечувствительности) и раз в минуту, поэтому
// простое среднее по точкам смещено к участкам, где значение быстро менялось. mean — среднее,
// взвешенное по времени: значение действует от своей точки до следующей, но не дольше hold
// (как в суточном отчёте, report/README.md); значение, пришедшее до начала часа, действует и в нём.
// min и max — по тем же значениям, что действовали в течение часа. Значения с quality = bad
// (отказ датчика, нет связи) в агрегаты не входят — как в отчёте.
import "contrib/tomhollingworth/events"
import "date"

option task = {name: "kns_downsample_1h", every: 1h, offset: 2m}

hold = 10m
stop = now()
start = date.sub(d: task.every, from: stop)

held =
    from(bucket: "@RAW_BUCKET@")
        |> range(start: date.sub(d: hold, from: start), stop: stop)
        |> filter(fn: (r) => r._measurement == "telemetry" and (r._field == "value" or r._field == "quality"))
        // значения с quality = bad не учитываются (как в отчёте); у OPC UA поля quality нет
        |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> filter(fn: (r) => exists r.value and (not exists r.quality or r.quality != "bad"))
        |> map(fn: (r) => ({r with _value: r.value}))
        |> drop(columns: ["value", "quality"])
        |> events.duration(unit: 1ns, columnName: "held_ns", stop: stop)
        |> map(
            fn: (r) => {
                t0 = int(v: r._time)
                t1 = t0 + (if r.held_ns > int(v: hold) then int(v: hold) else r.held_ns)
                a = if t0 < int(v: start) then int(v: start) else t0

                return {r with weight: if t1 > a then float(v: t1 - a) else 0.0}
            },
        )
        |> filter(fn: (r) => r.weight > 0.0)

held
    |> reduce(
        identity: {wsum: 0.0, weight: 0.0},
        fn: (r, accumulator) => ({wsum: accumulator.wsum + r._value * r.weight, weight: accumulator.weight + r.weight}),
    )
    |> map(fn: (r) => ({r with _time: stop, _value: r.wsum / r.weight}))
    |> drop(columns: ["wsum", "weight"])
    |> set(key: "_measurement", value: "telemetry_1h")
    |> set(key: "_field", value: "mean")
    |> to(bucket: "@AGG_BUCKET@")

held
    |> min()
    |> map(fn: (r) => ({r with _time: stop}))
    |> drop(columns: ["held_ns", "weight"])
    |> set(key: "_measurement", value: "telemetry_1h")
    |> set(key: "_field", value: "min")
    |> to(bucket: "@AGG_BUCKET@")

held
    |> max()
    |> map(fn: (r) => ({r with _time: stop}))
    |> drop(columns: ["held_ns", "weight"])
    |> set(key: "_measurement", value: "telemetry_1h")
    |> set(key: "_field", value: "max")
    |> to(bucket: "@AGG_BUCKET@")
