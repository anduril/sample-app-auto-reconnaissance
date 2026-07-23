"""Orbit task handler for the simulated asset.

`OrbitTask` is a stateless handler: its methods read and update the asset's
location and velocity in place and drive the asset through a caller-supplied
``resolve_objective``/``report_task_failed`` surface (see the class docstring).
It has no dependency on Lattice, so it can be exercised in isolation. The
module-level functions above the class are generic geodesic helpers reusable by
future task handlers.
"""

import asyncio
import json
import math
from pathlib import Path

from geopy import Point
from geopy.distance import distance as geo_distance
from geopy.distance import geodesic
from jsonschema import Draft202012Validator

# Orbit behavior tuning.
GROUND_SPEED_MPS = 60  # Ground speed for both the ingress leg and the circling leg.
ORBIT_TICK_SECONDS = 1  # Simulation step; smaller values produce smoother motion.
ORBIT_RADIUS_TOLERANCE_M = (
    5  # How close to the target radius counts as "on the circle".
)

# JSON Schema for the Orbit task payload.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_DIR = (
    _REPO_ROOT
    / "tasks"
    / "jsonschema"
    / "sample-app-auto-reconnaissance_protoschema-jsonschema"
)
_ORBIT_SCHEMA_PATH = (
    _SCHEMA_DIR
    / "anduril.sample_app_auto_reconnaissance.v1.Orbit.jsonschema.bundle.json"
)
_ORBIT_VALIDATOR = Draft202012Validator(json.loads(_ORBIT_SCHEMA_PATH.read_text()))


# --- Pure geodesic helpers -------------------------------------------------


def bearing(origin, destination):
    """Initial great-circle bearing in degrees from origin to destination."""
    lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
    lat2, lon2 = math.radians(destination[0]), math.radians(destination[1])
    d_lon = lon2 - lon1
    x = math.sin(d_lon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(
        d_lon
    )
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def destination_point(origin, bearing_deg, meters):
    """Point reached by traveling `meters` along `bearing_deg` from `origin`."""
    point = geo_distance(meters=meters).destination(
        Point(origin[0], origin[1]), bearing=bearing_deg
    )
    return (point.latitude, point.longitude)


def distance_m(a, b):
    """Geodesic distance in meters between two (lat, lon) points."""
    return geodesic(a, b).meters


def velocity_enu(prev, new, prev_alt, new_alt, dt=ORBIT_TICK_SECONDS):
    """East/North/Up velocity (m/s) from a position change over `dt` seconds.

    Deriving velocity from the actual move keeps it consistent across the
    ingress, climb, and circling phases without special-casing each one.
    """
    horizontal_m = distance_m(prev, new)
    bearing_rad = math.radians(bearing(prev, new)) if horizontal_m else 0.0
    return {
        "e": horizontal_m * math.sin(bearing_rad) / dt,
        "n": horizontal_m * math.cos(bearing_rad) / dt,
        "u": (new_alt - prev_alt) / dt,
    }


# --- Orbit task ------------------------------------------------------------


class OrbitTask:
    """Handler for the Orbit task type.

    Bundles everything specific to orbiting: the task specification URL it
    handles, spec parsing, and the flight loop. `start` returns an asyncio.Task
    the asset can hold as its active task; the handler drives the asset's
    physical state and reports failure through the asset, so the asset itself
    stays task-agnostic. To add a new task type, define a sibling class with the
    same `SPECIFICATION_URL` / `start` surface and register it on the asset.

    The `asset` passed in must expose:
      - ``location``: dict with latitude/longitude/altitude_hae_meters (mutated),
      - ``velocity_enu``: dict with e/n/u (reassigned each tick),
      - ``climb_rate_mps``: vertical speed used to reach the orbit altitude,
      - ``logger``,
      - async ``resolve_objective(objective)`` -> (lat, lon, altitude_hae_m),
      - async ``report_task_failed(task_id)`` called if execution errors.
    """

    SPECIFICATION_URL = (
        "type.googleapis.com/anduril.sample_app_auto_reconnaissance.v1.Orbit"
    )

    @classmethod
    def start(cls, asset, specification, task_id):
        """Return an asyncio.Task that executes this orbit task against `asset`."""
        return asyncio.create_task(cls._execute(asset, specification, task_id))

    @classmethod
    async def _execute(cls, asset, specification, task_id):
        try:
            spec = cls.parse_spec(specification)
            await cls._fly(asset, spec)
        except asyncio.CancelledError:
            asset.logger.info("orbit: cancelled")
            raise
        except Exception as error:
            asset.logger.error(f"orbit execution error {error}")
            await asset.report_task_failed(task_id)

    @staticmethod
    def parse_spec(specification):
        """Validate and extract the Orbit fields from a task spec (GoogleProtobufAny).

        The spec carries the Orbit payload as camelCase extras alongside @type,
        which is the dialect the bundled JSON Schema uses. We validate against
        that schema before extracting so a malformed payload fails here (and is
        reported as a failed task) rather than partway through the flight.
        """
        spec = specification.model_dump(by_alias=True, exclude_none=True)
        spec.pop("@type", None)

        errors = sorted(_ORBIT_VALIDATOR.iter_errors(spec), key=lambda e: list(e.path))
        if errors:
            details = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
            raise ValueError(f"invalid Orbit task payload: {details}")

        return {
            "orbit_radius": float(spec["orbitRadius"]),
            "orbit_height": float(spec.get("orbitHeight", 0.0)),
            "orbit_direction": spec.get("orbitDirection", "ORBIT_CLOCKWISE"),
            "objective": spec.get("objective"),
        }

    @staticmethod
    def tangent_bearing(current, center, radius, direction_sign):
        """Bearing from `current` toward the tangent point on the orbit circle.

        From a point at distance d outside a circle of radius r, the tangent
        lines touch the circle at the center-bearings beta +/- arccos(r/d),
        where beta is the bearing from the center out to us. Picking the sign by
        orbit direction (CCW: +, CW: -) yields the tangent point we can enter
        moving in the orbit direction, for a smooth tangential join. If we are
        already inside the radius there is no tangent, so we just aim outward.
        """
        dist = distance_m(current, center)
        if dist <= radius:
            return bearing(center, current)
        phi = math.degrees(math.acos(radius / dist))
        beta = bearing(center, current)
        tangent_bearing_from_center = (beta + direction_sign * phi) % 360
        tangent_point = destination_point(center, tangent_bearing_from_center, radius)
        return bearing(current, tangent_point)

    @classmethod
    async def _fly(cls, asset, spec):
        """Fly `asset` to the objective, then circle it at the requested radius.

        The asset's location/velocity are updated in place; a publisher reads
        them on its next refresh, so the asset visibly moves in Lattice.
        """
        orbit_radius = spec["orbit_radius"]
        orbit_height = spec["orbit_height"]
        orbit_direction = spec["orbit_direction"]
        objective = spec["objective"]
        # Clockwise decreases bearing, counterclockwise increases it.
        direction_sign = -1 if orbit_direction == "ORBIT_CLOCKWISE" else 1

        asset.logger.info(
            f"orbit: objective={objective} radius={orbit_radius}m "
            f"height={orbit_height}m direction={orbit_direction} "
            f"speed={GROUND_SPEED_MPS}m/s climb_rate={asset.climb_rate_mps}m/s"
        )

        step_m = GROUND_SPEED_MPS * ORBIT_TICK_SECONDS
        climb_step_m = asset.climb_rate_mps * ORBIT_TICK_SECONDS

        # Ingress: fly to the tangent point where our path meets the orbit
        # circle, so we arrive already moving in the orbit direction rather than
        # hitting the circle head-on and having to turn. We climb toward the
        # target altitude at the same time, and keep climbing once circling
        # begins, so a slow climb never stalls the approach. The objective is
        # re-resolved every tick: if it's an entity, it may be moving, so we
        # always steer toward its current position.
        while True:
            center_lat, center_lon, center_alt = await asset.resolve_objective(
                objective
            )
            center = (center_lat, center_lon)
            # Maintain orbit_height of vertical separation above the objective.
            target_alt = center_alt + orbit_height
            prev = (asset.location["latitude"], asset.location["longitude"])
            prev_alt = asset.location["altitude_hae_meters"]
            dist_to_center = distance_m(prev, center)
            cls._climb_toward(asset.location, target_alt, climb_step_m)
            if dist_to_center <= orbit_radius + ORBIT_RADIUS_TOLERANCE_M:
                # On the circle; hand off to the circling phase (still climbing).
                break
            # Head for the tangent point rather than straight at the center.
            heading = cls.tangent_bearing(prev, center, orbit_radius, direction_sign)
            # Cap the step so we don't overshoot past the target radius.
            travel = min(step_m, dist_to_center - orbit_radius)
            asset.location["latitude"], asset.location["longitude"] = destination_point(
                prev, heading, travel
            )
            cls._update_velocity(asset, prev, prev_alt)
            await asyncio.sleep(ORBIT_TICK_SECONDS)

        asset.logger.info("orbit: reached radius, beginning to circle")

        # Circle: step along the tangent, then re-project back onto the circle
        # so numerical drift doesn't spiral us in or out.
        # Angular step (radians) = arc length / radius.
        angular_step = (step_m / orbit_radius) if orbit_radius > 0 else 0
        at_target_altitude = False  # Latch so we log the arrival only once.
        while True:
            # Re-resolve so a moving objective drags the circle along with it.
            center_lat, center_lon, center_alt = await asset.resolve_objective(
                objective
            )
            center = (center_lat, center_lon)
            target_alt = center_alt + orbit_height
            prev = (asset.location["latitude"], asset.location["longitude"])
            prev_alt = asset.location["altitude_hae_meters"]
            # Bearing from the center out to us is our current angle.
            angle = bearing(center, prev)
            next_angle = (angle + direction_sign * math.degrees(angular_step)) % 360
            asset.location["latitude"], asset.location["longitude"] = destination_point(
                center, next_angle, orbit_radius
            )
            # Track the objective's altitude as it moves, logging the first time
            # we settle onto the target altitude (and again if a moving objective
            # forces a fresh climb).
            reached = cls._climb_toward(asset.location, target_alt, climb_step_m)
            if reached and not at_target_altitude:
                asset.logger.info(f"orbit: reached target altitude {target_alt}m")
            at_target_altitude = reached
            cls._update_velocity(asset, prev, prev_alt)
            await asyncio.sleep(ORBIT_TICK_SECONDS)

    @staticmethod
    def _climb_toward(location, target_alt, step_m):
        """Move `location`'s altitude up to `step_m` toward `target_alt`.

        Returns True once the altitude is at the target.
        """
        current_alt = location["altitude_hae_meters"]
        delta = target_alt - current_alt
        if abs(delta) <= step_m:
            location["altitude_hae_meters"] = target_alt
            return True
        location["altitude_hae_meters"] = current_alt + math.copysign(step_m, delta)
        return False

    @staticmethod
    def _update_velocity(asset, prev, prev_alt):
        """Set asset.velocity_enu from the move since (prev, prev_alt)."""
        new = (asset.location["latitude"], asset.location["longitude"])
        asset.velocity_enu = velocity_enu(
            prev, new, prev_alt, asset.location["altitude_hae_meters"]
        )
