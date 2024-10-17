import entities_api as anduril_entities
from geopy.distance import geodesic


class DistanceCalculator:
    @staticmethod
    def calculate(asset: anduril_entities.Entity, track: anduril_entities.Entity) -> float:
        """
        Calculate the distance between two points on Earth using the latitude and longitude coordinates of two Entities.
        One thing to note is that this calculation does not take into account the altitude of the entities.

        Args:
            asset (EM.Entity): The asset entity, which contains the latitude and longitude of the first point.
            track (EM.Entity): The track entity, which contains the latitude and longitude of the second point.

        Returns:
            float: The distance between the two points in meters.
        """
        point1 = (asset.location.position.latitude_degrees, asset.location.position.longitude_degrees)
        point2 = (track.location.position.latitude_degrees, track.location.position.longitude_degrees)
        distance = geodesic(point1, point2).miles
        return distance
