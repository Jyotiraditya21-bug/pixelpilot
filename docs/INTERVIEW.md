# PixelPilot interview guide

## 1. Why use four grounding tiers instead of calling the VLM for every action?

Accessible locators and DOM text are faster, deterministic, and inexpensive.
The VLM remains a fallback for targets that semantic evidence cannot resolve.
This design reduces latency and exposure to provider quotas, but depends on usable page semantics.

## 2. How does self-healing work?

After a VLM-grounded action succeeds, PixelPilot stores its semantic locator and visual fingerprint by site and intent.
The next run validates the current element fingerprint before accepting the cached tier-(a) locator.
This heals repeat flows, but large visual and semantic changes deliberately invalidate the entry.

## 3. Why combine DOM facts with visual verification?

DOM facts provide exact evidence for text, totals, and confirmation states without another model call.
Visual verification is reserved for expectations that cannot be established from those facts.
The limitation is that DOM-visible text can still misrepresent what a user can actually perceive.

## 4. How are Gemini coordinates made safe for browser clicks?

Gemini returns `[ymin,xmin,ymax,xmax]` values normalized from 0 to 1000.
PixelPilot converts them to the 1280×900 viewport and waits for navigation after coordinate clicks.
Bounding boxes can still be approximate, so action success and later verification remain essential.

## 5. What does mutation mode test?

Mutation changes IDs, classes, ordering, layout direction, position, and color while preserving the task semantics.
It tests whether automation survives selector and presentation churn on the controlled demo application.
It does not prove reliability across arbitrary production sites, authentication flows, or anti-bot systems.

## 6. What is the difference between standard and VLM-only benchmark rows?

Standard PixelPilot may use cache, role/name, DOM text, and finally VLM grounding.
VLM-only disables the first three grounding tiers so non-navigation actions exercise visual grounding.
The rows answer different questions and must not be combined into one headline success rate.

## 7. Why can VLM-only results be lower even with a valid API key?

Every grounded action consumes a Gemini request, increasing latency and the chance of an approximate box.
The free-tier request-per-minute quota can return HTTP 429 during a bursty benchmark.
PixelPilot paces requests and retries, but quota exhaustion is still an external limitation, not a pass.

## 8. How do you debug and audit a failed run?

The console shows one compact tier, pass, and duration line for each step plus the run result.
Detailed spans go to `runs/traces.jsonl`, while `run.json` and screenshots feed the HTML evidence report.
Artifacts improve diagnosis, but retention is intentionally limited to the newest ten run directories.
