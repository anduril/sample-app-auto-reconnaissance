import argparse
import logging
from asyncio import run

import yaml
from services.arbiter import Arbiter


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


def parse_arguments():
    parser = argparse.ArgumentParser(description="Entity Recon System")
    parser.add_argument(
        "--config", type=str, help="Path to the configuration file", required=True
    )
    return parser.parse_args()


def read_config(config_path):
    with open(config_path, "r") as ymlfile:
        cfg = yaml.safe_load(ymlfile)
        validate_config(cfg)
    return cfg


async def main_async(cfg):
    logging.basicConfig()
    logger = logging.getLogger("EARS")
    logger.setLevel(logging.DEBUG)
    logger.info("starting entity auto reconnaissance system")
    try:
        # Orbit task parameters used when tasking an asset to investigate a track.
        orbit_params = {
            "orbit_radius": cfg["orbit-radius-meters"],
            "orbit_height": cfg["orbit-height-meters"],
            "orbit_direction": cfg["orbit-direction"],
        }
        # Set up the application with the config
        arbiter = Arbiter(
            logger,
            cfg["lattice-endpoint"],
            cfg.get("lattice-client-id"),
            cfg.get("lattice-client-secret"),
            cfg["sandboxes-token"],
            orbit_params,
            environment_token=cfg.get("environment-token"),
        )
        await arbiter.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("shutting down entity auto reconnaissance system")


def main():
    args = parse_arguments()
    cfg = read_config(args.config)
    try:
        run(main_async(cfg))
    except KeyboardInterrupt:
        print("shutting down entity auto reconnaissance system")


if __name__ == "__main__":
    main()
