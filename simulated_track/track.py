import argparse
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

import yaml
from anduril import (
    Aliases,
    Lattice,
    Location,
    MilView,
    Ontology,
    Position,
    Provenance,
)
from anduril.core import ApiError

EXPIRY_OFFSET = 15
REFRESH_INTERVAL = 5


def validate_config(cfg):
    if "lattice-endpoint" not in cfg:
        raise ValueError("missing lattice-endpoint")
    if not cfg.get("environment-token") and not (
        cfg.get("lattice-client-id") and cfg.get("lattice-client-secret")
    ):
        raise ValueError(
            "missing environment-token, or lattice-client-id and lattice-client-secret"
        )
    if not cfg.get("sandboxes-token"):
        raise ValueError("missing sandboxes-token")
    if "track-latitude" not in cfg:
        raise ValueError("missing track-latitude")
    if "track-longitude" not in cfg:
        raise ValueError("missing track-longitude")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Simulated Track")
    parser.add_argument(
        "--config", type=str, help="Path to the configuration file", required=True
    )
    return parser.parse_args()


def read_config(config_path):
    with open(config_path, "r") as config_file:
        cfg = yaml.safe_load(config_file)
        validate_config(cfg)
    return cfg


def start_track_publishing():
    logging.basicConfig()
    logger = logging.getLogger("SIMTRACK")
    logger.setLevel(logging.DEBUG)
    logger.info("starting simulated track")

    args = parse_arguments()
    cfg = read_config(args.config)

    latitude = cfg["track-latitude"]
    longitude = cfg["track-longitude"]
    sandboxes_token = cfg["sandboxes-token"]

    client = Lattice(
        base_url=f"https://{cfg['lattice-endpoint']}",
        token=cfg.get("environment-token") or None,
        client_id=cfg.get("lattice-client-id"),
        client_secret=cfg.get("lattice-client-secret"),
        headers={"anduril-sandbox-authorization": f"Bearer {sandboxes_token}"},
    )

    entity_id = str(uuid.uuid4())

    while True:
        try:
            client.entities.publish_entity(
                entity_id=entity_id,
                is_live=True,
                expiry_time=datetime.now(UTC)
                + timedelta(seconds=EXPIRY_OFFSET),
                aliases=Aliases(
                    name="Simulated Track",
                ),
                location=Location(
                    position=Position(
                        latitude_degrees=latitude, longitude_degrees=longitude
                    )
                ),
                mil_view=MilView(
                    disposition="DISPOSITION_UNKNOWN",
                    environment="ENVIRONMENT_SURFACE",
                ),
                provenance=Provenance(
                    data_type="Simulated Track",
                    integration_name="auto-reconnaissance-sample-app",
                    source_update_time=datetime.now(UTC),
                ),
                ontology=Ontology(
                    template="TEMPLATE_TRACK",
                ),
            )
        except ApiError as error:
            logger.error(f"error publishing simulated track {error}")
        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    start_track_publishing()
