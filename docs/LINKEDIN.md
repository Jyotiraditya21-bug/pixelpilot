# LinkedIn post

Brittle UI tests often fail because a class name, element order, or button position changed—not because the user journey broke.

I built PixelPilot to try a different recovery path. It resolves actions through a cached locator, accessible role and name, visible DOM text, then a Gemini bounding box. When a visual action succeeds, PixelPilot fingerprints the target’s appearance and stores a healed semantic locator. A later run validates that fingerprint before reusing it.

The numbers are intentionally separated. Across three stories and three runs per condition, the scripted baseline fell from 9/9 to 0/9 under mutation. Standard PixelPilot stayed at 9/9 because semantic tiers handled this demo. VLM-only scored 3/9 in both conditions; the empty-cart cases needed no visual grounding, while missing credentials and free-tier quota failures counted as failures.

That benchmark measures resilience to controlled UI mutation. It does not establish accuracy on arbitrary websites.

<!-- RESULTS_TABLE_START: paste the final benchmarks/RESULTS.md table below -->

<!-- RESULTS_TABLE_END -->

# Five-line version

Brittle UI tests fail when presentation changes but intent does not.
PixelPilot heals successful visual targets by fingerprinting their appearance.
The scripted baseline dropped from 9/9 to 0/9 under mutation.
Standard semantic-tier PixelPilot stayed 9/9; VLM-only was 3/9.
The benchmark covers one controlled demo, not arbitrary websites.
