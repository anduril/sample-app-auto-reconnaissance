import entities_api as anduril_entities
from utils.lru_cache import LRUCache


class CacheManager:
    def __init__(self, capacity: int = 150):
        self.assets = LRUCache(capacity)
        self.tracks = LRUCache(capacity)
        self.asset_task = LRUCache(capacity)
        self.track_task = LRUCache(capacity)

    def add_asset(self, entity: anduril_entities.Entity):
        entity_id = entity.entity_id
        self.assets.put(entity_id, entity)

    def add_track(self, entity: anduril_entities.Entity):
        entity_id = entity.entity_id
        self.tracks.put(entity_id, entity)

    def add_asset_task(self, entity: anduril_entities.Entity, task_id: str):
        entity_id = entity.entity_id
        self.asset_task.put(entity_id, task_id)

    def add_track_task(self, entity: anduril_entities.Entity, task_id: str):
        entity_id = entity.entity_id
        self.track_task.put(entity_id, task_id)

    def remove_asset_task(self, entity_id: str):
        self.asset_task.remove(entity_id)

    def remove_track_task(self, entity_id: str):
        self.track_task.remove(entity_id)

    def get_assets(self) -> list[anduril_entities.Entity]:
        return self.assets.get_all()

    def get_tracks(self) -> list[anduril_entities.Entity]:
        return self.tracks.get_all()

    def get_asset_tasks(self, entity_id: str):
        return self.asset_task.get(entity_id)

    def get_track_tasks(self, entity_id: str):
        return self.track_task.get(entity_id)

    def handle_response(self, entity: anduril_entities.Entity):
        ontology_template = entity.ontology.template
        mil_view_disposition = entity.mil_view.disposition
        if ontology_template == "TEMPLATE_ASSET":
            self.add_asset(entity)
        elif (ontology_template == "TEMPLATE_TRACK" and
              mil_view_disposition != "DISPOSITION_FRIENDLY"):
            self.add_track(entity)
