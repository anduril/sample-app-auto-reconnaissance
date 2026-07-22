import json
from logging import Logger
from pathlib import Path
from typing import Optional

from anduril import Lattice
from anduril import (
    Entity,
    GoogleProtobufAny,
    Principal,
    Relations,
    System,
    TaskEntity,
)
from jsonschema import Draft202012Validator

# Fully-qualified type URL of the Orbit task spec.
ORBIT_SPECIFICATION_URL = "type.googleapis.com/anduril.sample_app_auto_reconnaissance.v1.Orbit"

# JSON Schema for the Orbit task payload. `tasks/` lives at the repo root since
# it is shared between the auto-reconnaissance and simulated_asset programs. The
# camelCase `.jsonschema.bundle.json` dialect matches the GoogleProtobufAny wire
# format, so we validate the spec we build against it before sending the task.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ORBIT_SCHEMA_PATH = (
    _REPO_ROOT
    / "tasks"
    / "jsonschema"
    / "sample-app-auto-reconnaissance_protoschema-jsonschema"
    / "anduril.sample_app_auto_reconnaissance.v1.Orbit.jsonschema.bundle.json"
)
_ORBIT_VALIDATOR = Draft202012Validator(json.loads(_ORBIT_SCHEMA_PATH.read_text()))


class Tasker:
    def __init__(
        self,
        logger: Logger,
        lattice_ip: str,
        client_id: str,
        client_secret: str,
        sandboxes_token: Optional[str] = None,
        orbit_params: Optional[dict] = None,
    ):
        self.logger = logger
        self.orbit_params = orbit_params or {}
        self.client = Lattice(
            base_url=f"https://{lattice_ip}",
            client_id=client_id,
            client_secret=client_secret,
            headers={"anduril-sandbox-authorization": f"Bearer {sandboxes_token}"},
        )

    def build_orbit_specification(self, track: Entity) -> GoogleProtobufAny:
        """Build and validate the Orbit task spec targeting `track`.

        Fields are camelCase to match the JSON Schema (and GoogleProtobufAny wire
        format). We validate before sending so a bad orbit config is caught here
        rather than on the asset that receives the task.
        """
        specification = GoogleProtobufAny(
            type=ORBIT_SPECIFICATION_URL,
            objective={"entityId": track.entity_id},
            orbitRadius=self.orbit_params["orbit_radius"],
            orbitHeight=self.orbit_params["orbit_height"],
            orbitDirection=self.orbit_params["orbit_direction"],
        )

        payload = specification.model_dump(by_alias=True, exclude_none=True)
        payload.pop("@type", None)
        errors = sorted(_ORBIT_VALIDATOR.iter_errors(payload), key=lambda e: list(e.path))
        if errors:
            details = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
            raise ValueError(f"invalid Orbit task payload: {details}")

        return specification

    def investigate(self, asset: Entity, track: Entity) -> str:
        try:
            self.logger.info(
                f"Asset {asset.entity_id} tasked to Orbit Track {track.entity_id}"
            )
            description = f"Asset {asset.entity_id} tasked to Orbit Track {track.entity_id}"
            specification = self.build_orbit_specification(track)
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
                initial_entities=[task_asset, task_track],
            )

            self.logger.info(
                f"Task created - view Lattice UI, task id is {returned_task.version.task_id}"
            )
            return returned_task.version.task_id
        except Exception as e:
            self.logger.error(f"task creation error {e}")
            raise e

    def check_executing(self, task_id: str) -> bool:
        try:
            returned_task = self.client.tasks.get_task(task_id=task_id)
            self.logger.info(
                f"Current task status for this task_id is {returned_task.status.status}"
            )
            return returned_task.status.status == "STATUS_EXECUTING"
        except Exception as e:
            self.logger.error(f"task creation error {e}")
            raise e
