# Design language

Spidey Sense turns coordination data into a navigable world without changing the
meaning of the core graph, activity, blocker, GitHub, or telemetry contracts.

## Spatial model

| Spidey Sense term | Source data | Visual behavior |
| --- | --- | --- |
| Web Zone | Repository directory | A spatial cluster in the 3D world |
| Web Node | Graph node / source file | A skyline structure sized by dependency degree |
| Strand | Directed graph edge | A blue connection between importer and dependency |
| Web Runner | Activity teammate or live CLI session | A live HUD entry and beacon above active nodes |
| Mission | Activity record | A Queued → On mission → Secured pathway |
| Web Signal | Directive record | An auditable human instruction, optionally sent to Codex |
| Tangle | Blocker record | A red strand, pulsing node, pathway marker, and explanation |
| Timeline Pulse | Git/GitHub telemetry | Recent commits, dirty files, branch, and merged work |

The UI labels `pending`, `working`, and `done` as **Queued**, **On mission**, and
**Secured**. These are presentation aliases only. Stored values and API schemas stay
stable for scripts and integrations.

## Interaction model

The 3D view answers “where is work happening?” while the surrounding HUD answers
“who is doing it, what is risky, and what can I change?” Selecting a Node identifies
its file and current owner. Filters isolate the full Web, live work, or Tangles.
Mission Dispatch edits the activity store; Web Signals enter the directive store and
can be delivered directly to a selected Codex thread when supported.

The scene groups files by their repository-relative directory rather than placing
them on a decorative map. Building height comes from dependency degree, every Strand
comes from a resolved graph edge, and every danger pulse traces to an explainable
blocker record.

## Visual identity

Spidey Sense uses an original abstract night-radar treatment: deep navy space, cobalt
topology lines, red early-warning pulses, luminous skyline Nodes, and a geometric web
mark. It intentionally contains no superhero characters, film imagery, logos, or
third-party game assets.

We studied [Claude Clan](https://github.com/mittal-parth/claude-clan) as a reference
for the general product pattern of turning repository structure and agent activity
into a spatial interface with an adjacent command HUD. Spidey Sense differs in its
visual system and terminology, supports Codex, Claude, and optional Entire telemetry,
uses dependency direction to name blockers, exposes a provider-neutral directive
inbox, and retains standalone JSON/CLI modules for every backend phase. No Claude
Clan code or artwork is copied into this project.

## Accessibility and performance

- The complete pathway, blocker, telemetry, and control UI works without WebGL.
- The 3D module is lazy-loaded and has explicit loading and fallback states.
- Mobile rendering is capped at device pixel ratio 1.
- Orbit controls do not capture page-wheel zoom.
- Reduced-motion preference disables automatic orbit and repeating UI animation.
- Every blocker remains available as text and through an accessible tooltip.
