# Reforge: Local AI for Personalised Linux Migration and Environment Reconstruction

Project proposer and repository owner: **adi05rjn**.

## Problem

Changing an operating system often loses more than installed applications: editor habits, appearance choices, toolchain requirements and fixes discovered through use must be reconstructed manually. Device-specific workarounds can also be copied into an incompatible environment.

## Proposed solution

Reforge maintains a portable desired-state profile and explicit diagnostic memory. A locally running model uses the user's initial instructions, target capabilities and applicable lessons to help plan a personalised environment. Deterministic adapters translate approved application choices into target-specific actions. The intended destination includes Linux on Snapdragon laptops.

The initial implementation demonstrates the foundation: limited Linux capture, structured preferences, diagnostic memory with applicability checks, Debian package plans, an optional real local inference client, and reviewable JSON/Markdown output. It keeps kernel modification in the research roadmap until compatibility and recovery mechanisms are established.

## Technical focus

The embedded-development example centres on editors, search tools, debugging and ARM cross compilation. This gives the project a concrete systems-engineering use case spanning Linux configuration, toolchains and device-aware planning. It demonstrates those technical interests without making claims about the proposer's qualifications or unmeasured results.

## Longer-term outcome

Move from planning to approved, reversible user-space reconstruction; extend import from Windows/macOS and other Linux distributions; then investigate carefully scoped kernel/driver recommendations. Validate local model performance and device support on actual Snapdragon hardware before claiming optimisation.
