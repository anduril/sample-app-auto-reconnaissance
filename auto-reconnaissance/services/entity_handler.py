import asyncio, json

from datetime import datetime, timezone
from logging import Logger
from typing import Optional
from pydantic import BaseModel, Field

from anduril import AsyncLattice
from anduril import  (
    Entity, 
    MilView,
    Provenance
)

class EntityHandler:
    def __init__(self, logger: Logger, lattice_endpoint: str, client_id: str, client_secret: str, sandboxes_token: Optional[str] = None):
        self.logger = logger
        self.client = AsyncLattice(
            base_url=f"https://{lattice_endpoint}",
            client_id=client_id,
            client_secret=client_secret,
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
        try:
            event_stream = self.client.entities.stream_entities(pre_existing_only=False)
            async for event in event_stream:
                if event.event == "entity":
                    event_data = json.loads(event.data)
                    entity_data = event_data.get("entity")
                    typed_entity = Entity.model_validate(entity_data)
                    yield typed_entity
        except asyncio.CancelledError:
            print("Streaming cancelled...")
        except Exception as error:
            print(f"Exception: {error}")

    async def override_track_disposition(self, track: Entity):
        try:
            self.logger.info(f"overriding disposition for track {track.entity_id}")
            entity_id = track.entity_id
            override_track_entity = Entity(entity_id = entity_id, mil_view=MilView(disposition="DISPOSITION_SUSPICIOUS"))
            override_provenance = Provenance(integration_name=track.provenance.integration_name,
                                                              data_type=track.provenance.data_type,
                                                              source_id=track.provenance.source_id,
                                                              source_update_time=datetime.now(timezone.utc),
                                                              source_description=track.provenance.source_description, )
            await self.client.entities.override_entity(entity_id=entity_id,
                                                     field_path="mil_view.disposition",
                                                     entity=override_track_entity,
                                                     provenance=override_provenance)
            return
        except Exception as error:
            self.logger.error(f"lattice api stream entities error {error}")
