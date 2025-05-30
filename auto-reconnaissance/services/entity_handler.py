import asyncio

from datetime import datetime, timezone
from logging import Logger
from typing import Optional

import sys
import os

sys.path.append(os.path.abspath("../modules"))
from modules.types import (
    Entity, 
    EntityEvent,
    MilView,
    Provenance
)
from modules.client import anduril as LatticeClient


class Config(BaseModel):
    lattice_ip: str = Field(alias="lattice-ip")
    lattice_bearer_token: str = Field(alias="lattice-bearer-token")
    entity_update_rate_seconds: int = Field(alias="entity-update-rate-seconds")
    vessel_mmsi: list[int] = Field(alias="vessel-mmsi")
    ais_generate_interval_seconds: int = Field(
        alias="ais-generate-interval-seconds"
    )

class EntityHandler:
    def __init__(self, logger: Logger, lattice_ip: str, bearer_token: str, sandboxes_token: Optional[str] = None):
        self.logger = logger
        self.config = anduril_entities.Configuration(host=f"https://{lattice_ip}/api/v1")
        self.api_client = anduril_entities.ApiClient(configuration=self.config, header_name="Authorization",
                                                     header_value=f"Bearer {bearer_token}")
        if sandboxes_token:
            self.api_client.default_headers["anduril-sandbox-authorization"] = f"Bearer {sandboxes_token}"
        self.entity_api = anduril_entities.EntityApi(api_client=self.api_client)

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
                response = self.lattice_client.entity.long_poll_entity_events(session_token="")
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

            self.lattice_client.entity.put_entity_override_rest(entity_id=entity_id,
                                                     field_path="mil_view.disposition",
                                                     entity=override_track_entity,
                                                     provenance=override_provenance)
            return
        except Exception as error:
            self.logger.error(f"lattice api stream entities error {error}")
