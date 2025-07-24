import asyncio

from datetime import datetime, timezone
from logging import Logger
from typing import Optional
from pydantic import BaseModel, Field

from anduril import Lattice
from anduril import  (
    Entity, 
    MilView,
    Provenance
)

class EntityHandler:
    def __init__(self, logger: Logger, lattice_endpoint: str, environment_token: str, sandboxes_token: Optional[str] = None):
        self.logger = logger
        self.client = Lattice(
            base_url=f"https://{lattice_endpoint}",
            token=environment_token, 
            headers={ "anduril-sandbox-authorization": f"Bearer {sandboxes_token}" }
        )

    def filter_entity(self, entity: Entity) -> bool:
        """
        The statement returned basically filters for 1) an entity with the ontology.template field set to ASSET, or 2) an entity with the ontology.template field set to TRACK and their mil_view.disposition field set to HOSTILE or SUSPICIOUS.
        
        Args:
            entity: the entity to check if it satisfies the filter

        Returns:
            bool: True if the entity satisfies the filter, False otherwise.

        Raises:
            None
        """
        ontology_template = entity.ontology.template
        mil_view_disposition = entity.mil_view.disposition
        if ontology_template == "TEMPLATE_ASSET":
            return True
        elif (ontology_template == "TEMPLATE_TRACK" and
              mil_view_disposition != "DISPOSITION_FRIENDLY"):
            return True
        else:
            return False

    async def stream_entities(self):
        while True:
            try:
                response = self.client.entities.long_poll_entity_events(session_token="")
                if response.entity_events:
                    for entity_event in response.entity_events:
                        entity = entity_event.entity
                        if self.filter_entity(entity):
                            yield entity
                await asyncio.sleep(0.1)
            except Exception as error:
                self.logger.error(f"lattice api stream entities error {error}")
                await asyncio.sleep(30) 

    def override_track_disposition(self, track: Entity):
        try:
            self.logger.info(f"overriding disposition for track {track.entity_id}")
            entity_id = track.entity_id
            override_track_entity = Entity(entity_id = entity_id, mil_view=MilView(disposition="DISPOSITION_SUSPICIOUS"))
            override_provenance = Provenance(integration_name=track.provenance.integration_name,
                                                              data_type=track.provenance.data_type,
                                                              source_id=track.provenance.source_id,
                                                              source_update_time=datetime.now(timezone.utc),
                                                              source_description=track.provenance.source_description, )
            self.client.entities.override_entity(entity_id=entity_id,
                                                     field_path="mil_view.disposition",
                                                     entity=override_track_entity,
                                                     provenance=override_provenance)
            return
        except Exception as error:
            self.logger.error(f"lattice api stream entities error {error}")
