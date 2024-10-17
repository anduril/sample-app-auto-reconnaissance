from logging import Logger

import entities_api as anduril_entities
import tasks_api as anduril_tasks


class Tasker:
    def __init__(self, logger: Logger, lattice_ip: str, bearer_token: str):
        self.logger = logger
        self.config = anduril_tasks.Configuration(host=f"https://{lattice_ip}/api/v1")
        self.api_client = anduril_tasks.ApiClient(configuration=self.config, header_name="Authorization",
                                                  header_value=f"Bearer {bearer_token}")
        self.task_api = anduril_tasks.TaskApi(api_client=self.api_client)

    def investigate(self, asset: anduril_entities.Entity, track: anduril_entities.Entity) -> str:
        try:
            # we have to convert EM.Entity to TM.Entity to be able to use these instances for task creation
            tm_asset = anduril_tasks.Entity(**asset.to_dict())
            tm_track = anduril_tasks.Entity(**track.to_dict())

            display_name = f"Asset {tm_asset.entity_id} -> Track {tm_track.entity_id}"
            description = f"Asset {tm_asset.entity_id} tasked to perform ISR on Track {tm_track.entity_id}"
            specification_type = "type.googleapis.com/anduril.tasks.v2.Investigate"
            specification_properties = {
                "objective": {
                    "entity_id": tm_track.entity_id
                },
                "parameters": {
                    "speed_m_s": tm_asset.location.speed_mps
                }
            }
            specification = anduril_tasks.GoogleProtobufAny(type=specification_type,
                                                            additional_properties=specification_properties)
            author_user = anduril_tasks.User(user_id="user/some_user")
            author = anduril_tasks.Principal(system=anduril_tasks.System(service_name="auto-reconnaissance"))
            relations_assignee_system = anduril_tasks.System(entity_id=tm_asset.entity_id)
            relations_assignee = anduril_tasks.Principal(system=relations_assignee_system)
            relations = anduril_tasks.Relations(assignee=relations_assignee)
            task_entity = anduril_tasks.TaskEntity(entity=tm_asset, snapshot=False)

            task_creation = anduril_tasks.TaskCreation(display_name=display_name,
                                                       description=description,
                                                       specification=specification,
                                                       author=author,
                                                       relations=relations,
                                                       is_executed_elsewhere=False,
                                                       initial_entities=[task_entity])
            returned_task = self.task_api.create_task(task_creation=task_creation,
                                                      _content_type="application/json")
            self.logger.info(f"Task created - view Lattice UI, task id is {returned_task.version.task_id}")
            return returned_task.version.task_id
        except Exception as e:
            self.logger.error(f"task creation error {e}")
            raise e

    def check_executing(self, task_id: str) -> bool:
        try:
            returned_task = self.task_api.get_task_by_id(task_id=task_id)
            self.logger.info(f"Current task status for this task_id is {returned_task.status.status}")
            return returned_task.status.status == "STATUS_EXECUTING"
        except Exception as e:
            self.logger.error(f"task creation error {e}")
            raise e
