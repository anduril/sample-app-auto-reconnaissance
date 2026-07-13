# Exercise degradation and mesh preflight

Live exercises often fail in the gap between **sandbox CI** (asset + track simulators running on a stable network) and **field mesh** (relay loss, entity stream gaps, stale fusion). This sample app can gate `Investigate` task creation when streamed entities go stale — a lightweight preflight hook before exercise hours.

## Enable stale-entity gating

Add to `var/config.yml`:

```yaml
# Optional: block Investigate tasks when asset/track not seen on the entity stream
# within this many seconds. Omit or comment out to preserve default behavior.
entity-stale-seconds: 120
```

Restart the auto-reconnaissance arbiter after changing config.

When stale, the arbiter logs:

```
WARNING:EARS:STALE ENTITY — skipping Investigate task (entity=..., gap_s=..., threshold_s=120)
```

## Simulate relay loss locally

1. Start arbiter, simulated asset, and simulated track as in the main README.
2. Confirm an `Investigate` task is created when the track is in range.
3. **Stop** `simulated_track/track.py` (or `simulated_asset/asset.py`) — simulates mesh partition / publisher loss.
4. With `entity-stale-seconds` set, the arbiter stops creating new tasks once the entity exceeds the threshold.

This mirrors exercise scenarios where a relay drops and long-poll consumers retain last-known entity state while fusion desyncs.

## Example scenario fixture

See [`examples/relay-loss/scenario.yml`](relay-loss/scenario.yml) for a documented relay-death timeline (T+14h node loss) aligned with mesh exercise rehearsal workflows.

## Related work

For full **plan → run → doctor → report** exercise fate tooling, see [lattice-exercise-twin](https://github.com/Abhishek21g/lattice-exercise-twin) (community companion — not an Anduril product).
