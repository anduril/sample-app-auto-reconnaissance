import asyncio
from logging import Logger

from utils.distance_calculator import DistanceCalculator

from services.cache_manager import CacheManager
from services.entity_handler import EntityHandler
from services.tasker import Tasker

DISTANCE_THRESHOLD_MILES = 5


class Arbiter:
    def __init__(self, logger: Logger, lattice_ip: str, bearer_token: str):
        self.logger = logger
        self.entity_handler = EntityHandler(logger, lattice_ip, bearer_token)
        self.cache_manager = CacheManager()
        self.tasker = Tasker(logger, lattice_ip, bearer_token)

    async def start(self):
        tasks = [
            asyncio.create_task(self.consume_entities()),
            asyncio.create_task(self.recon_job())
        ]
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt caught: cancelling tasks...")
            for task in tasks:
                task.cancel()
        finally:
            self.logger.info("Shutting down Entity Auto Recon System")

    async def consume_entities(self):
        while True:
            async for entity in self.entity_handler.stream_entities():
                self.cache_manager.handle_response(entity)

    async def recon_job(self):
        while True:
            self.arbitrate_isr()
            await asyncio.sleep(1)

    def within_range(self, asset, track) -> bool:
        distance = DistanceCalculator.calculate(asset, track)
        return distance <= DISTANCE_THRESHOLD_MILES

    def check_in_progress(self, asset, track) -> bool:
        skip = False
        asset_task_id = self.cache_manager.get_asset_tasks(asset.entity_id)
        if asset_task_id:
            asset_in_progress = self.tasker.check_executing(asset_task_id)
            if asset_in_progress:
                skip = True
            else:
                self.cache_manager.remove_asset_task(asset.entity_id)
        track_task_id = self.cache_manager.get_track_tasks(track.entity_id)
        if track_task_id:
            track_in_progress = self.tasker.check_executing(track_task_id)
            if track_in_progress:
                skip = True
            else:
                self.cache_manager.remove_track_task(track.entity_id)
        return skip

    def arbitrate_isr(self):
        assets = self.cache_manager.get_assets()
        tracks = self.cache_manager.get_tracks()
        self.logger.info(f"# of assets being tracked: {len(assets)}, # of tracks being tracked: {len(tracks)}")
        for asset in assets:
            for track in tracks:
                if self.within_range(asset, track) and track.mil_view.disposition not in ["DISPOSITION_FRIENDLY",
                                                                                          "DISPOSITION_ASSUMED_FRIENDLY"]:
                    self.logger.info(f"ASSET WITHIN RANGE OF NON-FRIENDLY TRACK")
                    if track.mil_view.disposition not in ["DISPOSITION_SUSPICIOUS", "DISPOSITION_HOSTILE"]:
                        self.entity_handler.override_track_disposition(track)
                    if self.check_in_progress(asset, track):
                        self.logger.info(f"INVESTIGATION ALREADY IN PROGRESS - SKIPPING")
                        continue
                    if self.cache_manager.get_asset_tasks(
                            asset.entity_id) is None and self.cache_manager.get_track_tasks(track.entity_id) is None:
                        task_id = self.tasker.investigate(asset, track)
                        self.cache_manager.add_asset_task(asset, task_id)
                        self.cache_manager.add_track_task(track, task_id)
