# Benchmark results

Measured locally with `3` runs per story per mutation condition.

| Runner | Mutation | Passed | Success |
|---|---:|---:|---:|
| Scripted baseline | 0 | 9/9 | 100.0% |
| Scripted baseline | 1 | 0/9 | 0.0% |
| PixelPilot | 0 | 9/9 | 100.0% |
| PixelPilot | 1 | 9/9 | 100.0% |

Targets: scripted baseline under mutation <30%; PixelPilot under mutation ≥85%.
Observed: baseline 0.0%, PixelPilot 100.0%.

The baseline intentionally uses fixed IDs/classes. PixelPilot uses accessible semantics; these demo runs do not require a VLM call, so free-tier model limits do not affect them.
