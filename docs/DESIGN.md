# PixelPilot Instrument UI
Purpose: let engineers read agent decisions, evidence, healing, and timing without leaving the run surface.
Audience: test and platform engineers diagnosing a live or saved browser run.
Aesthetic: a light-first laboratory logbook—warm paper, near-black drafting ink, hairline rules, and compact instrumentation.
Light tokens: paper `#f4efe4`, raised paper `#fbf7ee`, ink `#171813`, muted ink `#5d6058`, rule `#77786f`, signal `#8b3b18`.
Dark tokens: paper `#15130f`, raised paper `#201d17`, ink `#f2ecdf`, muted ink `#b9b2a5`, rule `#8a8376`, signal `#f0a56a`.
Tier colors are semantic and distinct: cached slate, role/name green, DOM text teal, vision ochre, replan crimson, heal olive.
Pass and fail use labeled green and red states; color is never the only indicator and text contrast is at least 4.5:1.
Display type is `Avenir Next Condensed`/`Arial Narrow`; all data and telemetry use `SFMono-Regular`/Consolas.
Spacing uses a 4px base with 8px composition: 4, 8, 12, 16, 24, 32, 48; controls reach 44px on mobile.
Borders are one-pixel hairlines; radii are 2px for controls and 4px for frames; depth comes from rules, not shadows.
Motion uses `--ease`, `--dur-fast`, `--dur-base`, and `--dur-slow`; only transform and opacity animate.
Reduced motion removes staged movement, sweeps, pulses, shakes, and count-up transitions while preserving state changes.
Light is the default; the top-right dark toggle stores its explicit choice in `localStorage` inside `try/catch`.
The three-region layout stays evidence-first: run controls, live trace and ground view, then durable history and comparison.
