import argparse
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta

import entities_api as anduril_entities
import yaml

EXPIRY_OFFSET = 15
REFRESH_INTERVAL = 5


def validate_config(cfg):
    if "lattice-ip" not in cfg:
        raise ValueError("missing lattice-ip")
    if "lattice-bearer-token" not in cfg:
        raise ValueError("missing lattice-bearer-token")
    if "latitude" not in cfg:
        raise ValueError("missing latitude")
    if "longitude" not in cfg:
        raise ValueError("missing longitude")


def parse_arguments():
    parser = argparse.ArgumentParser(description='Simulated Track')
    parser.add_argument('--config', type=str, help='Path to the configuration file', required=True)
    return parser.parse_args()


def read_config(config_path):
    with open(config_path, 'r') as config_file:
        cfg = yaml.safe_load(config_file)
        validate_config(cfg)
    return cfg


def generate_track_entity(entity_id: str, latitude: float, longitude: float) -> anduril_entities.Entity:
    return anduril_entities.Entity(
        entity_id=entity_id,
        is_live=True,
        expiry_time=datetime.now(timezone.utc) + timedelta(seconds=EXPIRY_OFFSET),
        aliases=anduril_entities.Aliases(
            name="Simulated Track",
        ),
        location=anduril_entities.Location(
            position=anduril_entities.Position(
                latitude_degrees=latitude,
                longitude_degrees=longitude
            )
        ),
        mil_view=anduril_entities.MilView(
            disposition="DISPOSITION_UNKNOWN",
            environment="ENVIRONMENT_SURFACE",
        ),
        provenance=anduril_entities.Provenance(
            data_type="Simulated Track",
            integration_name="auto-reconnaissance-sample-app",
            source_update_time=datetime.now(timezone.utc),
        ),
        ontology=anduril_entities.Ontology(
            template="TEMPLATE_TRACK",
        )
    )


def start_track_publishing():
    logging.basicConfig()
    logger = logging.getLogger("SIMTRACK")
    logger.setLevel(logging.DEBUG)
    logger.info("starting simulated track")

    args = parse_arguments()
    cfg = read_config(args.config)

    latitude = cfg['latitude']
    longitude = cfg['longitude']

    entities_configuration = anduril_entities.Configuration(host=f"https://{cfg['lattice-ip']}/api/v1")
    entities_api_client = anduril_entities.ApiClient(configuration=entities_configuration,
                                                     header_name="Authorization",
                                                     header_value=f"Bearer {cfg['lattice-bearer-token']}")
    entities_api = anduril_entities.EntityApi(api_client=entities_api_client)

    entity_id = str(uuid.uuid4())

    while True:
        try:
            entities_api.publish_entity_rest(entity=generate_track_entity(entity_id, latitude, longitude))
        except Exception as error:
            logger.error(f"error publishing simulated track {error}")
        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    start_track_publishing()
