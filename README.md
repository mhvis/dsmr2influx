# DSMR2InfluxDB

Stores P1 port data in a InfluxDB NoSQL database, to visualize with Grafana.

Inspired by [psy0rz/p1_dsmr_to_influxdb](https://github.com/psy0rz/p1_dsmr_to_influxdb).
Uses [ndokter/dsmr_parser](https://github.com/ndokter/dsmr_parser) to read the P1 port data.


## Getting started

An easy way to deploy is via Docker Compose:

1. Copy or download `compose.yaml` to a desired location.
2. Modify the configuration as required.
3. Run `docker compose up -d`.
4. To see if the containers have started correctly, use `docker compose logs -f`.

Note: if you have the old version of Docker Compose installed, replace `docker compose` with `docker-compose`.

## Importing from DSMR-reader

This command imports data from DSMR-reader into your InfluxDB instance.
It requires that the DSMR-reader API is enabled and accessible via the container.

```shell
docker compose run app python dsmrreaderimport.py <api-url> <api-key>
```

When the InfluxDB instance already contains measurements,
existing measurements with the same timestamp get overridden.
So it is safe to import multiple times.

## Backups


## A note on the InfluxDB schema

Each telegram is stored as a `telegram` measurement in InfluxDB, and each field
in the telegram is a field on the measurement.
Field keys are the same as [OBIS names](https://github.com/ndokter/dsmr_parser/blob/master/dsmr_parser/telegram_specifications.py),
but in lowercase, for instance `electricity_used_tariff_1` and `instantaneous_voltage_l1`.

Gas meter readings are stored in a separate measurement named `gas_meter`,
because they update less frequent, often every 5 minutes or every hour.
The measurement time is taken from the telegram.
The field `reading` contains the value.

