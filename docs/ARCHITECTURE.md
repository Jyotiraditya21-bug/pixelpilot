# Architecture

PixelPilot separates browser effects from reasoning. `Planner` converts the constrained Markdown story into typed semantic actions. `Observer` gathers a pruned visible-element snapshot and a bounded JPEG. `Grounder` escalates from cache through accessibility and text to an Ollama bounding box. `Actor` performs the action and allows one replan. `Verifier` checks concrete DOM facts before requesting visual judgment.

`Orchestrator` owns the safety envelope: 25 steps, 20 seconds per attempt, and two retries. It creates the system-Chrome session, retains the newest ten run directories, writes `run.json`, and creates OpenTelemetry run/step/agent spans. Reports are deterministic renderings of the JSON record plus sibling screenshots.

The demo mutates generated IDs, CSS classes, product order, flex direction, button placement, and color while retaining accessible language. This isolates selector brittleness from business-flow correctness.
