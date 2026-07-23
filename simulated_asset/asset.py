import argparse
import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone

import httpx
import yaml
from anduril import (
    AgentRequest,
    Aliases,
    AsyncLattice,
    Classification,
    ClassificationInformation,
    Entity,
    EntityIdsSelector,
    Enu,
    Health,
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
from orbit import OrbitTask

EXPIRY_OFFSET = 15
REFRESH_INTERVAL = 5
STATUS_VERSION_COUNTER = 1
TASK_HANDLERS = {
    OrbitTask.SPECIFICATION_URL: OrbitTask,
}


class SimulatedAsset:
    def __init__(
        self,
        logger: logging.Logger,
        client: AsyncLattice,
        entity_id: str,
        location: dict,
        climb_rate_mps: float,
    ):
        self.logger = logger
        self.client = client
        self.entity_id = entity_id

        self.location = location  # Dict with latitude, longitude, altitude_hae_meters.
        self.velocity_enu = {
            "e": 0.0,
            "n": 0.0,
            "u": 0.0,
        }  # Current velocity (m/s) in East/North/Up.
        self.climb_rate_mps = (
            climb_rate_mps  # Vertical speed used when changing altitude.
        )
        self._active_task = (
            None  # asyncio.Task for the task currently being executed, if any.
        )

    async def run(self):
        tasks = [
            asyncio.create_task(self.publish_asset()),
            asyncio.create_task(self.listen_for_tasks()),
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
            data_classification=Classification(
                default=ClassificationInformation(
                    level="CLASSIFICATION_LEVELS_UNCLASSIFIED"
                )
            ),
            health=Health(
                connection_status="CONNECTION_STATUS_ONLINE",
                health_status="HEALTH_STATUS_HEALTHY",
            ),
            location=Location(
                position=Position(
                    latitude_degrees=self.location["latitude"],
                    longitude_degrees=self.location["longitude"],
                    altitude_hae_meters=self.location["altitude_hae_meters"],
                ),
                speed_mps=math.hypot(self.velocity_enu["e"], self.velocity_enu["n"]),
                velocity_enu=Enu(
                    e=self.velocity_enu["e"],
                    n=self.velocity_enu["n"],
                    u=self.velocity_enu["u"],
                ),
            ),
            mil_view=MilView(
                disposition="DISPOSITION_FRIENDLY",
                environment="ENVIRONMENT_AIR",
                platform_type="UAV",
            ),
            provenance=Provenance(
                data_type="Simulated Asset",
                integration_name="auto-reconnaissance-sample-app",
                source_update_time=datetime.now(timezone.utc),
            ),
            ontology=Ontology(template="TEMPLATE_ASSET", platform_type="UAV"),
            task_catalog=TaskCatalog(
                task_definitions=[
                    TaskDefinition(task_specification_url=url) for url in TASK_HANDLERS
                ]
            ),
        )

    async def listen_for_tasks(self):
        self.logger.info(
            f"starting listen task for tasking simulated asset {self.entity_id}"
        )
        while True:
            try:
                agent_request = await self.client.tasks.listen_as_agent(
                    agent_selector=EntityIdsSelector(entity_ids=[self.entity_id])
                )
                if agent_request:
                    self.logger.info(
                        f"received task request for simulated asset {self.entity_id}"
                    )
                    await self.process_task_event(agent_request)
            except httpx.ReadTimeout:
                continue  # Long polling expects re-initiating the request after 5 minutes.
            except Exception as error:
                self.logger.error(f"simulated asset task processing error {error}")

    async def process_task_event(self, agent_request: AgentRequest):
        global STATUS_VERSION_COUNTER
        STATUS_VERSION_COUNTER += 1
        if agent_request.execute_request:
            request_kind = "Execute"
        elif agent_request.cancel_request:
            request_kind = "Cancel"
        elif agent_request.complete_request:
            request_kind = "Complete"
        else:
            request_kind = "Unknown"
        self.logger.info(f"Received task request: {request_kind}")
        if agent_request.execute_request:
            task = agent_request.execute_request.task
            task_id = task.version.task_id

            spec_url = task.specification.type
            handler = TASK_HANDLERS.get(spec_url)
            if handler is None:
                self.logger.error(
                    f"received unsupported task type {spec_url}, rejecting"
                )
                await self._report_terminal_status(task_id, "STATUS_DONE_NOT_OK")
                return

            self.logger.info("Sending execute confirmation")
            try:
                self._cancel_active_task()
                self._active_task = handler.start(self, task.specification, task_id)

                await self.client.tasks.update_task_status(
                    # For an extenesive list of supported task status values, reference
                    new_status=TaskStatus(status="STATUS_EXECUTING"),
                    author=Principal(system=System(entity_id=self.entity_id)),
                    status_version=STATUS_VERSION_COUNTER,  # Integration is to track its own status version. This version number
                    # increments to indicate the task's current stage in its status lifecycle. Whenever a task's status updates,
                    # the status version increments by one. Any status updates received with a lower status version number than
                    # what is known are considered stale and ignored.
                    task_id=task_id,
                )
            except Exception as error:
                self.logger.error(f"simulated asset listening agent error {error}")
                return

        elif agent_request.cancel_request:
            self.logger.info("received cancel request, sending cancel confirmation")
            self._cancel_active_task()
            await self._report_terminal_status(
                agent_request.cancel_request.task_id, "STATUS_DONE_NOT_OK"
            )

        elif agent_request.complete_request:
            self.logger.info("received complete request, sending complete confirmation")
            self._cancel_active_task()
            await self._report_terminal_status(
                agent_request.complete_request.task_id, "STATUS_DONE_OK"
            )

    async def _report_terminal_status(self, task_id: str, status: str):
        global STATUS_VERSION_COUNTER
        try:
            await self.client.tasks.update_task_status(
                new_status=TaskStatus(status=status),
                author=Principal(system=System(entity_id=self.entity_id)),
                status_version=STATUS_VERSION_COUNTER,  # Integration is to track its own status version. This version number
                # increments to indicate the task's current stage in its status lifecycle. Whenever a task's status updates,
                # the status version increments by one. Any status updates received with a lower status version number than
                # what is known are considered stale and ignored.
                task_id=task_id,
            )
        except Exception as error:
            self.logger.error(f"simulated asset listening agent error {error}")

    def _cancel_active_task(self):
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
        self._active_task = None
        # No active tasking means the asset is holding position.
        self.velocity_enu = {"e": 0.0, "n": 0.0, "u": 0.0}

    async def report_task_failed(self, task_id: str):
        """Report that the active task could not be completed. Called by handlers."""
        await self._report_terminal_status(task_id, "STATUS_DONE_NOT_OK")

    async def resolve_objective(self, objective: dict):
        """Return the (latitude, longitude, altitude_hae_m) center for an Orbit objective.

        The objective is a oneof: either an inline `lla` position or an
        `entityId` we resolve to a live entity's current location.
        """
        if not objective:
            raise ValueError("orbit task has no objective")

        if objective.get("lla"):
            lla = objective["lla"]
            return (
                lla["latitudeDegrees"],
                lla["longitudeDegrees"],
                lla.get("altitudeHaeM", 0.0),
            )

        entity_id = objective.get("entityId")
        if entity_id:
            entity = await self.client.entities.get_entity(entity_id)
            position = entity.location.position
            return (
                position.latitude_degrees,
                position.longitude_degrees,
                position.altitude_hae_meters or 0.0,
            )

        raise ValueError(f"unsupported orbit objective: {objective}")


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
    parser = argparse.ArgumentParser(description="Simulated Asset")
    parser.add_argument(
        "--config", type=str, help="Path to the configuration file", required=True
    )
    return parser.parse_args()


def read_config(config_path):
    with open(config_path, "r") as ymlfile:
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
        client_id=cfg["lattice-client-id"],
        client_secret=cfg["lattice-client-secret"],
        headers={"anduril-sandbox-authorization": f"Bearer {cfg['sandboxes-token']}"},
        timeout=300,
    )  # 5 minutes for long polling

    asset = SimulatedAsset(
        logger,
        client,
        "asset-01",
        {
            "latitude": cfg["asset-latitude"],
            "longitude": cfg["asset-longitude"],
            "altitude_hae_meters": cfg["asset_altitude_hae_meters"],
        },
        cfg["asset_climb_rate"],
    )

    try:
        asyncio.run(asset.run())
    except KeyboardInterrupt:
        logger.info("keyboard interrupt detected")


if __name__ == "__main__":
    main()
