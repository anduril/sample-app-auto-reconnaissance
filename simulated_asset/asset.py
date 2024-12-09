import argparse
import asyncio
import logging
from datetime import datetime, timezone, timedelta

import entities_api as anduril_entities
import tasks_api as anduril_tasks
import yaml

EXPIRY_OFFSET = 15
REFRESH_INTERVAL = 5
STATUS_VERSION_COUNTER = 1


class SimulatedAsset:
    def __init__(self,
                 logger: logging.Logger,
                 entities_api_client: anduril_entities.EntityApi,
                 tasks_api_client: anduril_tasks.TaskApi,
                 entity_id: str,
                 location: dict):
        self.logger = logger
        self.entities_api_client = entities_api_client
        self.tasks_api_client = tasks_api_client
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
                self.entities_api_client.publish_entity_rest(
                    entity=self.generate_asset_entity()
                )
            except Exception as error:
                self.logger.error(f"lattice api stream entities error {error}")

            await asyncio.sleep(REFRESH_INTERVAL)

    def generate_asset_entity(self):
        return anduril_entities.Entity(
            entity_id=self.entity_id,
            is_live=True,
            expiry_time=datetime.now(timezone.utc) + timedelta(seconds=EXPIRY_OFFSET),
            aliases=anduril_entities.Aliases(
                name=f"Simulated Asset {self.entity_id}",
            ),
            location=anduril_entities.Location(
                position=anduril_entities.Position(
                    latitudeDegrees=self.location["latitude"],
                    longitudeDegrees=self.location["longitude"],
                    altitudeHaeMeters=55 # arbitrary value so asset is above mean sea level
                ),
                speedMps=1,
                velocityEnu=anduril_entities.ENU(
                    e=1,
                    n=1,
                    u=0
                )
            ),
            mil_view=anduril_entities.MilView(
                disposition="DISPOSITION_FRIENDLY",
                environment="ENVIRONMENT_SURFACE",
            ),
            provenance=anduril_entities.Provenance(
                data_type="Simulated Asset",
                integration_name="auto-reconnaissance-sample-app",
                source_update_time=datetime.now(timezone.utc),
            ),
            ontology=anduril_entities.Ontology(
                template="TEMPLATE_ASSET",
                platform_type="USV"
            ),
            task_catalog=anduril_entities.TaskCatalog(
                task_definitions=[
                    anduril_entities.TaskDefinition(
                        task_specification_url="type.googleapis.com/anduril.tasks.v2.Investigate"
                    )
                ]
            )
        )

    async def listen_for_tasks(self):
        self.logger.info(f"starting listen task for tasking simulated asset {self.entity_id}")
        while True:
            try:
                agent_listener = anduril_tasks.AgentListener(
                    agent_selector=anduril_tasks.EntityIdsSelector(entity_ids=[self.entity_id]))
                agent_request = await asyncio.to_thread(
                    self.tasks_api_client.long_poll_listen_as_agent,
                    agent_listener=agent_listener
                )
                if agent_request:
                    await self.process_task_event(agent_request)
            except Exception as error:
                self.logger.error(f"simulated asset task processing error {error}")

    async def process_task_event(self, agent_request: anduril_tasks.AgentRequest):
        global STATUS_VERSION_COUNTER
        STATUS_VERSION_COUNTER += 1
        self.logger.info(f"received task request {agent_request}")
        if agent_request.execute_request:
            self.logger.info(f"received execute request, sending execute confirmation")
            try:
                task_execute_update = anduril_tasks.TaskStatusUpdate(
                    # For an extenesive list of supported task status values, reference 
                    # https://docs.anduril.com/reference/models/taskmanager/v1/task#:~:text=of%20last%20update.-,statusTaskStatus,-The%20status%20of
                    new_status=anduril_tasks.TaskStatus(status="STATUS_EXECUTING"),
                    author=anduril_tasks.models.Principal(system=anduril_tasks.models.System(entity_id=self.entity_id)),
                    status_version=STATUS_VERSION_COUNTER  # Integration is to track its own status version. This version number 
                    # increments to indicate the task's current stage in its status lifecycle. Whenever a task's status updates, 
                    # the status version increments by one. Any status updates received with a lower status version number than 
                    # what is known are considered stale and ignored.
                )
                await asyncio.to_thread(
                    self.tasks_api_client.update_task_status_by_id,
                    task_id=agent_request.execute_request.task.version.task_id,
                    task_status_update=task_execute_update
                )
            except Exception as error:
                self.logger.error(f"simulated asset listening agent error {error}")
        elif agent_request.cancel_request:
            self.logger.info(f"received cancel request, sending cancel confirmation")
            try:
                task_cancel_update = anduril_tasks.TaskStatusUpdate(
                    # For an extenesive list of supported task status values, reference 
                    # https://docs.anduril.com/reference/models/taskmanager/v1/task#:~:text=of%20last%20update.-,statusTaskStatus,-The%20status%20of
                    new_status=anduril_tasks.TaskStatus(status="STATUS_DONE_NOT_OK"),
                    author=anduril_tasks.models.Principal(system=anduril_tasks.models.System(entity_id=self.entity_id)),
                    status_version=STATUS_VERSION_COUNTER  # Integration is to track its own status version. This version number 
                    # increments to indicate the task's current stage in its status lifecycle. Whenever a task's status updates, 
                    # the status version increments by one. Any status updates received with a lower status version number than 
                    # what is known are considered stale and ignored.
                )
                await asyncio.to_thread(
                    self.tasks_api_client.update_task_status_by_id,
                    task_id=agent_request.cancel_request.task_id,
                    task_status_update=task_cancel_update
                )
            except Exception as error:
                self.logger.error(f"simulated asset listening agent error {error}")


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

    entities_configuration = anduril_entities.Configuration(host=f"https://{cfg['lattice-ip']}/api/v1")
    entities_api_client = anduril_entities.ApiClient(configuration=entities_configuration,
                                                     header_name="Authorization",
                                                     header_value=f"Bearer {cfg['lattice-bearer-token']}")
    entities_api = anduril_entities.EntityApi(api_client=entities_api_client)

    tasks_configuration = anduril_tasks.Configuration(host=f"https://{cfg['lattice-ip']}/api/v1")
    tasks_api_client = anduril_tasks.ApiClient(configuration=tasks_configuration,
                                               header_name="Authorization",
                                               header_value=f"Bearer {cfg['lattice-bearer-token']}")
    tasks_api = anduril_tasks.TaskApi(api_client=tasks_api_client)

    asset = SimulatedAsset(
        logger,
        entities_api,
        tasks_api,
        "asset-01",
        {"latitude": cfg['latitude'], "longitude": cfg['longitude']})

    try:
        asyncio.run(asset.run())
    except KeyboardInterrupt:
        logger.info("keyboard interrupt detected")
    pass


if __name__ == "__main__":
    main()
