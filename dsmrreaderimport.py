import argparse
import json
import logging
import os
from decimal import Decimal
from typing import Dict, Iterable
from urllib.request import urlopen, Request

from influxdb_client import InfluxDBClient, Point

logger = logging.getLogger(__name__)

# Mapping between DSMR-reader column names and InfluxDB telegram field names
READING_FIELD_MAP = {
    'electricity_delivered_1': 'electricity_used_tariff_1',
    'electricity_returned_1': 'electricity_delivered_tariff_1',
    'electricity_delivered_2': 'electricity_used_tariff_2',
    'electricity_returned_2': 'electricity_delivered_tariff_2',
    'electricity_currently_delivered': 'current_electricity_usage',
    'electricity_currently_returned': 'current_electricity_delivery',
    'phase_currently_delivered_l1': 'instantaneous_active_power_l1_positive',
    'phase_currently_delivered_l2': 'instantaneous_active_power_l2_positive',
    'phase_currently_delivered_l3': 'instantaneous_active_power_l3_positive',
    'phase_currently_returned_l1': 'instantaneous_active_power_l1_negative',
    'phase_currently_returned_l2': 'instantaneous_active_power_l2_negative',
    'phase_currently_returned_l3': 'instantaneous_active_power_l3_negative',
    'phase_voltage_l1': 'instantaneous_voltage_l1',
    'phase_voltage_l2': 'instantaneous_voltage_l2',
    'phase_voltage_l3': 'instantaneous_voltage_l3',
    'phase_power_current_l1': 'instantaneous_current_l1',
    'phase_power_current_l2': 'instantaneous_current_l2',
    'phase_power_current_l3': 'instantaneous_current_l3',
}


def reading2point(reading: Dict) -> Iterable[Point]:
    """Maps a DSMR reading from the API to InfluxDB Point structures.

    If a gas meter reading is present, this yields two Points, else it will
    yield one Point.
    """
    p = Point('telegram')
    p.time(reading['timestamp'])
    for col, field in READING_FIELD_MAP.items():
        value = reading[col]
        if value is not None:
            # Decimal values are given as string, convert them to Decimal
            if isinstance(value, str):
                value = Decimal(value)
            p.field(f, value)
    yield p
    # Extra device field
    if reading['extra_device_timestamp']:
        p = Point('gas_meter')
        p.time(reading['extra_device_timestamp'])
        p.field('reading', Decimal(reading['extra_device_delivered']))
        yield p


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import readings from DSMR-reader.')
    parser.add_argument('api-url', help='URL of the DSMR-reader installation, without trailing slash, '
                                        'e.g. http://localhost:8080 or https://dsmr.example.com.')
    parser.add_argument('api-key', help='Auth key set in the DSMR-reader API configuration.')
    args = parser.parse_args()

    # Number of results per API request, we could make this into an argument
    batch_size = 1000
    bucket = os.getenv('DSMR_BUCKET')

    logger.info('Starting import from %s', args.api_url)

    # Create InfluxDB client
    #
    # We use the batching write API (which is the default). Therefore we need
    # to make sure to close the client.
    with InfluxDBClient.from_env_properties() as client:
        with client.write_api() as write_api:
            imported = 0
            next_url = f'{args.api_url}/api/v2/datalogger/dsmrreading?limit={batch_size}'
            while next_url:
                # Fetch readings
                with urlopen(Request(next_url, headers={'Authorization': f'Token {args.api_key}'})) as f:
                    response = json.load(f)
                # Write to InfluxDB
                for result in response['results']:
                    write_api.write(bucket=bucket, record=reading2point(result))

                next_url = response['next']

                # Print some progress information
                imported += len(response['results'])
                logger.info("Imported %s/%s", imported, response['count'])
    logger.info('Finished import')
