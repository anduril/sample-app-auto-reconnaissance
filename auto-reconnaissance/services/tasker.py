from logging import Logger
from typing import Optional

from anduril import Lattice
from anduril import (
    Aliases,
    Entity,
    EntityIdsSelector,
    Enu,
    GoogleProtobufAny,
    Location,
    Ontology,
    Position,
    Principal,
    Provenance,
    Relations,
    System,
    TaskCatalog,
    TaskDefinition,
    TaskEntity,
    TaskStatus,
    User,
)

class Tasker:
    def __init__(self, logger: Logger, lattice_ip: str, client_id: str, client_secret: str, sandboxes_token: Optional[str] = None):
        self.logger = logger
        self.client = Lattice(
            base_url=f"https://{lattice_ip}",
            client_id=client_id, 
            client_secret=client_secret, 
            headers={ "anduril-sandbox-authorization": f"Bearer {sandboxes_token}" }
        )
    def investigate(self, asset: Entity, track: Entity) -> str:
        try:
            self.logger.info(f"Asset {asset.entity_id} tasked to perform ISR on Track {track.entity_id}")
            description = f"Asset {asset.entity_id} tasked to perform ISR on Track {track.entity_id}"
            specification_type = "type.googleapis.com/anduril.tasks.v2.Investigate"
            specification = GoogleProtobufAny(
                type=specification_type,
                objective={
                        "entity_id": track.entity_id
                }
            )
            author = Principal(system=System(service_name="auto-reconnaissance"))
            relations_assignee_system = System(entity_id=asset.entity_id)
            relations_assignee = Principal(system=relations_assignee_system)
            relations = Relations(assignee=relations_assignee)
            task_asset = TaskEntity(entity=asset, snapshot=False)
            task_track = TaskEntity(entity=track, snapshot=False)

            returned_task = self.client.tasks.create_task(
                description=description,
                specification=specification,
                author=author,
                relations=relations,
                is_executed_elsewhere=False,
                initial_entities=[task_asset, task_track])

            self.logger.info(f"Task created - view Lattice UI, task id is {returned_task.version.task_id}")
            return returned_task.version.task_id
        except Exception as e:
            self.logger.error(f"task creation error {e}")
            raise e

    def check_executing(self, task_id: str) -> bool:
        try:
            returned_task = self.client.tasks.get_task(task_id=task_id)
            self.logger.info(f"Current task status for this task_id is {returned_task.status.status}")
            return returned_task.status.status == "STATUS_EXECUTING"
        except Exception as e:
            self.logger.error(f"task creation error {e}")
            raise e
