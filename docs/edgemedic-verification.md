# EdgeMedic verification

Status: **implemented, tested**. Live NX mission windows: **not experimentally validated**.

## Levels

| level | meaning | rollback | `recovery_success` | Repair Memory |
| --- | --- | --- | --- | --- |
| `none` | action did not stick | yes | false | failure |
| `config` | target state written (profile/backend/settings) | no | false | do not learn |
| `function` | module completed one valid functional execution | no | true | may learn |
| `mission` | observation window still meets the task | no | true | may learn |

`CONFIG_VERIFIED` is not recovery. `verified` in the Control response equals `recovery_success`.

## MissionVerificationPolicy

Mission is **not** `sleep(N)` then “no error”. GearPro records inspection cycles after `begin_verify_window()` and scores:

- `window_seconds` (SPARSE default 10 s)
- `min_cycles`
- `min_valid_output_ratio` (SPARSE 0.95)
- locator / V5 / elapsed **mean, p50, p95, max** (mission gate uses **p95**)
- `min_mission_utility`
- `min_health_score`
- `reject_on_critical_incident`

If the window is too short, the level stays `function`.

SAFE_STOP / pause / serial reconnect remain alias-mission once the IO/config effect is real.

## Last Known Good

| file | meaning |
| --- | --- |
| `var/settings.json` | active / latest configuration (written on persist) |
| `var/settings.last_known_good.json` | latest **function or mission** verified configuration |

Promote happens in `ControlService` after `recovery_success` on config-changing actions. Persist alone must not promote LKG.

## Mission Utility

\[
U = 0.3 Q_L + 0.5 Q_D + 0.2 Q_S
\]

`Q_D` uses actual `valid_output_ratio` times the profile **capability ceiling**. Profile name alone must not be treated as measured quality. Snapshot utility is still a single-frame estimate; window p95 lives in verify extras.
