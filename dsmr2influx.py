

import logging
import os
from typing import Dict

import dsmr_parser.clients
from dsmr_parser import telegram_specifications
from dsmr_parser.clients.telegram_buffer import TelegramBuffer
from dsmr_parser.exceptions import InvalidChecksumError, ParseError
from dsmr_parser.obis_name_mapping import EN
from dsmr_parser.parsers import TelegramParser
from influxdb_client import InfluxDBClient
from serial import Serial

logger = logging.getLogger(__name__)


def map_obis_names(telegram: Dict):
    """Maps a dsmr_parser telegram with OBIS references to names.

    Additionally strips the ..
    """
    return {
        EN[k]: v
        for k, v in telegram.items()
    }


"""
Note: we do not catch all exceptions here and automatically restart when an
exception occurs. This is on purpose, this way we can rely on Docker to do this
for us.
"""

if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)

    # InfluxDB configuration
    client = InfluxDBClient.from_env_properties()
    # DSMR configuration
    serial_settings = getattr(dsmr_parser.clients, f'SERIAL_SETTINGS_{os.getenv("DSMR_SERIAL_SETTINGS", "V5")}')
    telegram_specification = getattr(telegram_specifications, os.getenv('DSMR_TELEGRAM_SPECIFICATION', 'V5'))
    device = os.getenv('DSMR_DEVICE', '/dev/ttyUSB0')


    # DSMR parsing
    buffer = TelegramBuffer()
    parser = TelegramParser(telegram_specification)

    with Serial(port=device, **serial_settings) as serial_handle:
        while True:
            data = serial_handle.readline()
            buffer.append(data.decode('ascii'))

            for telegram_str in buffer.get_all():
                try:
                    telegram = parser.parse(telegram_str)

                except (InvalidChecksumError, ParseError) as e:
                    logger.error("Telegram parsing failed", exc_info=e)

