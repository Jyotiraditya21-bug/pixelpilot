# Benchmark results

Measured locally with `1` run per story per mutation condition.

| Runner | Mutation | Passed | Success |
|---|---:|---:|---:|
| Scripted baseline | 0 | 3/3 | 100.0% |
| Scripted baseline | 1 | 0/3 | 0.0% |
| PixelPilot | 0 | 3/3 | 100.0% |
| PixelPilot | 1 | 3/3 | 100.0% |
| PixelPilot VLM-only | 0 | 1/3 | 33.3% |
| PixelPilot VLM-only | 1 | 1/3 | 33.3% |

Targets: scripted baseline under mutation <30%; PixelPilot under mutation ≥85%.
Observed: baseline 0.0%, PixelPilot 100.0%.

The baseline intentionally uses fixed IDs/classes. Standard PixelPilot uses accessible semantics. PixelPilot VLM-only disables cache, role/name, and DOM text so every non-navigation grounding attempt exercises Gemini REST. Missing credentials and exhausted free-tier quota are counted as failures.

Note on sample size and quota: Measured with sample size n=1 per story condition. During the VLM-only evaluation, Gemini REST calls encountered HTTP 429 rate limiting due to the Google AI Studio free-tier quota limit (20 requests per day per project/model). The empty-cart story (which requires no visual grounding) passed, while visual grounding steps failed after retries due to quota exhaustion.
