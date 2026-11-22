# LinkedIn post

Brittle UI tests often fail because a class name, element order, or button position changed—not because the user journey broke.

I built PixelPilot to try a different recovery path. It resolves actions through a cached locator, accessible role and name, visible DOM text, then a Gemini bounding box. When a visual action succeeds, PixelPilot fingerprints the target’s appearance and stores a healed semantic locator. A later run validates that fingerprint before reusing it.

The numbers are intentionally separated. Across three stories per condition (sample size n=1), the scripted baseline fell from 3/3 to 0/3 under mutation. Standard PixelPilot stayed at 3/3 because semantic tiers handled this demo. VLM-only scored 1/3 in both conditions; the empty-cart case needed no visual grounding and passed, while visual grounding steps encountered HTTP 429 rate limits due to Gemini free-tier daily quota exhaustion.

That benchmark measures resilience to controlled UI mutation. It does not establish accuracy on arbitrary websites.

<!-- RESULTS_TABLE_START: paste the final benchmarks/RESULTS.md table below -->
| Runner | Mutation | Passed | Success |
|---|---:|---:|---:|
| Scripted baseline | 0 | 3/3 | 100.0% |
| Scripted baseline | 1 | 0/3 | 0.0% |
| PixelPilot (accessibility-semantic tiers) | 0 | 3/3 | 100.0% |
| PixelPilot (accessibility-semantic tiers) | 1 | 3/3 | 100.0% |
| PixelPilot VLM-only (pure vision) | 0 | 1/3 | 33.3% |
| PixelPilot VLM-only (pure vision) | 1 | 1/3 | 33.3% |

*Note: Measured with sample size n=1 per condition. Pure vision (VLM-only) runs are limited by Gemini free-tier daily quota (20 requests/day per project/model); quota exhaustion (HTTP 429) caused visual grounding failures on coupon stories.*
<!-- RESULTS_TABLE_END -->

# Five-line version

Brittle UI tests fail when presentation changes but intent does not.
PixelPilot heals successful visual targets by fingerprinting their appearance.
The scripted baseline dropped from 3/3 to 0/3 under mutation.
Standard semantic-tier PixelPilot stayed 3/3; VLM-only was 1/3 (limited by free-tier quota).
The benchmark covers one controlled demo, not arbitrary websites.
