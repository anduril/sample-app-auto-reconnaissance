import argparse
import logging
from asyncio import run

import yaml

from services.arbiter import Arbiter


def validate_config(cfg):
    if "lattice-endpoint" not in cfg:
        raise ValueError("missing lattice-endpoint")
    if "environment-token" not in cfg:
        raise ValueError("missing environment-token")
    if "sandboxes-token" not in cfg or cfg["sandboxes-token"] == "<SANDBOXES_TOKEN>":
        logger.warning("sandboxes-token not set - required for connecting to Lattice Sandboxes")
        cfg["sandboxes-token"] = None


def parse_arguments():
    parser = argparse.ArgumentParser(description='Entity Recon System')
    parser.add_argument('--config', type=str, help='Path to the configuration file', required=True)
    return parser.parse_args()


def read_config(config_path):
    with open(config_path, 'r') as ymlfile:
        cfg = yaml.safe_load(ymlfile)
        validate_config(cfg)
    return cfg


async def main_async(cfg):
    logging.basicConfig()
    logger = logging.getLogger("EARS")
    logger.setLevel(logging.DEBUG)
    logger.info("starting entity auto reconnaissance system")
    try:
        # Set up the application with the config
        arbiter = Arbiter(logger, cfg["lattice-endpoint"], cfg["environment-token"], cfg["sandboxes-token"])
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
