# Benchmark results

Measured locally with `3` runs per story per mutation condition.

| Runner | Mutation | Passed | Success |
|---|---:|---:|---:|
| Scripted baseline | 0 | 9/9 | 100.0% |
| Scripted baseline | 1 | 0/9 | 0.0% |
| PixelPilot | 0 | 9/9 | 100.0% |
| PixelPilot | 1 | 9/9 | 100.0% |
| PixelPilot VLM-only | 0 | 3/9 | 33.3% |
| PixelPilot VLM-only | 1 | 3/9 | 33.3% |

Targets: scripted baseline under mutation <30%; PixelPilot under mutation ≥85%.
Observed: baseline 0.0%, PixelPilot 100.0%.

The baseline intentionally uses fixed IDs/classes. Standard PixelPilot uses accessible semantics. PixelPilot VLM-only disables cache, role/name, and DOM text so every non-navigation grounding attempt exercises Gemini REST. Missing credentials and exhausted free-tier quota are counted as failures.
