import argparse
import asyncio
import logging
import httpx

from datetime import datetime, timezone, timedelta

from anduril import AsyncLattice
from anduril import (
    AgentRequest,
    Aliases,
    Entity,
    EntityIdsSelector,
    Enu,
    Location,
    MilView,
    Ontology,
    Position,
    Principal,
    Provenance,
    System,
    TaskCatalog,
    TaskDefinition,
    TaskStatus,
)

import yaml

EXPIRY_OFFSET = 15
REFRESH_INTERVAL = 5
STATUS_VERSION_COUNTER = 1


class SimulatedAsset:
    def __init__(self,
                 logger: logging.Logger,
                 client: AsyncLattice,
                 entity_id: str,
                 location: dict):
        self.logger = logger
        self.client = client
        self.entity_id = entity_id
        self.location = location

    async def run(self):
        tasks = [
            asyncio.create_task(self.publish_asset()),
            asyncio.create_task(self.listen_for_tasks())
        ]
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt caught: cancelling tasks...")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self.logger.info(f"Shutting down Simulated Asset {self.entity_id}")
        pass

    async def publish_asset(self):
        self.logger.info(f"starting publish task for simulated asset {self.entity_id}")
        while True:
            try:
                await self.client.entities.publish_entity(
                    **(self.generate_asset_entity().model_dump())
                )
            except Exception as error:
                self.logger.error(f"lattice api stream entities error {error}")

            await asyncio.sleep(REFRESH_INTERVAL)

    def generate_asset_entity(self):
        return Entity(
            entity_id=self.entity_id,
            is_live=True,
            expiry_time=datetime.now(timezone.utc) + timedelta(seconds=EXPIRY_OFFSET),
            aliases=Aliases(
                name=f"Simulated Asset {self.entity_id}",
            ),
            location=Location(
                position=Position(
                    latitude_degrees=self.location["latitude"],
                    longitude_degrees=self.location["longitude"],
                    altitude_hae_meters=55 # arbitrary value so asset is above mean sea level
                ),
                speed_mps=1,
                velocity_enu=Enu(
                    e=1,
                    n=1,
                    u=0
                )
            ),
            mil_view=MilView(
                disposition="DISPOSITION_FRIENDLY",
                environment="ENVIRONMENT_SURFACE",
            ),
            provenance=Provenance(
                data_type="Simulated Asset",
                integration_name="auto-reconnaissance-sample-app",
                source_update_time=datetime.now(timezone.utc),
            ),
            ontology=Ontology(
                template="TEMPLATE_ASSET",
                platform_type="USV"
            ),
            task_catalog=TaskCatalog(
                task_definitions=[
                    TaskDefinition(
                        task_specification_url="type.googleapis.com/anduril.tasks.v2.Investigate"
                    )
                ]
            )
        )

    async def listen_for_tasks(self):
        self.logger.info(f"starting listen task for tasking simulated asset {self.entity_id}")
        while True:
            try:
                agent_request = await self.client.tasks.listen_as_agent(
                    agent_selector=EntityIdsSelector(entity_ids=[self.entity_id])
                )
                if agent_request:
                    self.logger.info(f"received task request for simulated asset {self.entity_id}")
                    await self.process_task_event(agent_request)
            except httpx.ReadTimeout:
                continue # Long polling expects re-initiating the request after 5 minutes. 
            except Exception as error:
                self.logger.error(f"simulated asset task processing error {error}")

    async def process_task_event(self, agent_request: AgentRequest):
        global STATUS_VERSION_COUNTER
        STATUS_VERSION_COUNTER += 1
        self.logger.info(f"Received task request: {'Execute' if agent_request.execute_request else 'Cancel'}")
        if agent_request.execute_request:
            self.logger.info(f"received execute request, sending execute confirmation")
            try:
                await self.client.tasks.update_task_status(
                    # For an extenesive list of supported task status values, reference 
                    # https://developer.anduril.com/reference/rest/tasks/update-task-status#request.body.newStatus.status
                    new_status=TaskStatus(status="STATUS_EXECUTING"),
                    author=Principal(system=System(entity_id=self.entity_id)),
                    status_version=STATUS_VERSION_COUNTER,  # Integration is to track its own status version. This version number 
                    # increments to indicate the task's current stage in its status lifecycle. Whenever a task's status updates, 
                    # the status version increments by one. Any status updates received with a lower status version number than 
                    # what is known are considered stale and ignored.
                    task_id=agent_request.execute_request.task.version.task_id,
                )
            except Exception as error:
                self.logger.error(f"simulated asset listening agent error {error}")
        elif agent_request.cancel_request:
            self.logger.info(f"received cancel request, sending cancel confirmation")
            try:
                await self.client.tasks.update_task_status(
                    # For an extenesive list of supported task status values, reference 
                    # https://developer.anduril.com/reference/rest/tasks/update-task-status#request.body.newStatus.status
                    new_status=TaskStatus(status="STATUS_DONE_NOT_OK"),
                    author=Principal(system=System(entity_id=self.entity_id)),
                    status_version=STATUS_VERSION_COUNTER,  # Integration is to track its own status version. This version number 
                    # increments to indicate the task's current stage in its status lifecycle. Whenever a task's status updates, 
                    # the status version increments by one. Any status updates received with a lower status version number than 
                    # what is known are considered stale and ignored.
                    task_id=agent_request.cancel_request.task_id,
                )
            except Exception as error:
                self.logger.error(f"simulated asset listening agent error {error}")


def validate_config(cfg):
    if "lattice-endpoint" not in cfg:
        raise ValueError("missing lattice-endpoint")
    if "lattice-client-id" not in cfg:
        raise ValueError("missing lattice-client-id")
    if "lattice-client-secret" not in cfg:
        raise ValueError("missing lattice-client-secret")
    if "asset-latitude" not in cfg:
        raise ValueError("missing asset-latitude")
    if "asset-longitude" not in cfg:
        raise ValueError("missing asset-longitude")


def parse_arguments():
    parser = argparse.ArgumentParser(description='Simulated Asset')
    parser.add_argument('--config', type=str, help='Path to the configuration file', required=True)
    return parser.parse_args()


def read_config(config_path):
    with open(config_path, 'r') as ymlfile:
        cfg = yaml.safe_load(ymlfile)
        validate_config(cfg)
    return cfg


def main():
    logging.basicConfig()
    logger = logging.getLogger("SIMASSET")
    logger.setLevel(logging.DEBUG)
    logger.info("starting simulated asset")

    args = parse_arguments()
    cfg = read_config(args.config)

    client = AsyncLattice(
        base_url=f"https://{cfg['lattice-endpoint']}", 
        client_id=cfg['lattice-client-id'], 
        client_secret=cfg['lattice-client-secret'], 
        headers={ "anduril-sandbox-authorization": f"Bearer {cfg['sandboxes-token']}" },
        timeout=300) # 5 minutes for long polling

    asset = SimulatedAsset(
        logger,
        client,
        "asset-01",
        {"latitude": cfg['asset-latitude'], "longitude": cfg['asset-longitude']})

    try:
        asyncio.run(asset.run())
    except KeyboardInterrupt:
        logger.info("keyboard interrupt detected")
    pass


if __name__ == "__main__":
    main()
