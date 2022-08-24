import logging
import os
from typing import Dict, Iterable

import dsmr_parser.clients
from dsmr_parser import telegram_specifications
from dsmr_parser.clients.telegram_buffer import TelegramBuffer
from dsmr_parser.exceptions import InvalidChecksumError, ParseError
from dsmr_parser.obis_name_mapping import EN
from dsmr_parser.objects import CosemObject, ProfileGenericObject, MBusObject
from dsmr_parser.parsers import TelegramParser
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from serial import Serial

logger = logging.getLogger(__name__)


def telegram2point(telegram: Dict) -> Iterable[Point]:
    """Constructs a Point structure from a telegram dictionary."""
    # Note: we do not use the P1 timestamp as time if it is present
    p = Point('telegram')
    for k, v in telegram.items():
        obis_name = EN[k].lower()

        if isinstance(v, CosemObject):
            # All CosemObjects are converted to fields, timestamp values are converted to strings
            p.field(obis_name, v.value)
        elif isinstance(v, MBusObject):
            # The MBusObject is assumed to be a gas meter reading and yields a separate Point/measurement
            if obis_name not in ('gas_meter_reading', 'hourly_gas_meter_reading'):
                logger.warning("Got an unknown MBusObject which is not a gas meter reading, with value: %s", v)
            else:
                yield Point('gas_meter').time(v.datetime).field('reading', v.value)
        elif isinstance(v, ProfileGenericObject):
            logger.warning("The power_event_failure_log line is not yet implemented, telegram value: %s", v)
        else:
            logger.warning("Got unknown object in telegram: %s", v)
    yield p


def telegram_buffer(serial_handle) -> Iterable[str]:
    """Reads from the serial handle into a buffer and yields full telegram strings."""
    buffer = TelegramBuffer()
    while True:
        # TODO: this call blocks SIGINT interrupts until new data arrives (I think),
        #   which makes ctrl+c slow.
        data = serial_handle.readline()
        buffer.append(data.decode('ascii'))
        for telegram_str in buffer.get_all():
            yield telegram_str


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Read InfluxDB configuration
    #
    # We use the synchronous API, thus it is not necessary to close or flush.
    client = InfluxDBClient.from_env_properties()
    write_api = client.write_api(write_options=SYNCHRONOUS)
    bucket = os.getenv('DSMR_BUCKET')

    # Read DSMR configuration
    serial_settings = getattr(dsmr_parser.clients, f"SERIAL_SETTINGS_{os.getenv('DSMR_SERIAL_SETTINGS', 'V5')}")
    telegram_specification = getattr(telegram_specifications, os.getenv('DSMR_TELEGRAM_SPECIFICATION', 'V5'))
    device = os.getenv('DSMR_DEVICE', '/dev/ttyUSB0')

    # DSMR parser
    parser = TelegramParser(telegram_specification)

    logger.info('Waiting for first telegram')
    first_iteration = True

    with Serial(port=device, **serial_settings) as serial_handle:
        for telegram_string in telegram_buffer(serial_handle):
            try:
                telegram = parser.parse(telegram_string)
                if first_iteration:
                    logger.info('Received telegram:')
                    for obis, val in telegram.items():
                        logger.info('%s=%s', EN[obis].lower(), val)
                    logger.info('Startup complete, writing telegrams to InfluxDB')
                    first_iteration = False
                write_api.write(bucket=bucket, record=telegram2point(telegram))

            except (InvalidChecksumError, ParseError) as e:
                # Note: we do not catch all exceptions. This is on purpose,
                # this way we can rely on Docker to automatically restart the
                # container on failure.
                logger.error("Telegram parsing failed", exc_info=e)
