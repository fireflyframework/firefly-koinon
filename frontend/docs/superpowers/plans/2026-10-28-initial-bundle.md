# Initial Library Bundle Implementation Plan

**Goal:** Keep the complete Library initial and reduce management and Elements initial output below the existing 500000-byte budget.

**Architecture:** Remove framework dependencies from simple Library controls, defer genuine interaction panels and dialog infrastructure, and separate optional chat state from shell state where measurements require it. Keep synchronous public translation behavior, APF exports, service identity, and Shadow DOM boundaries.

**Constraints:** No budget increases, dependencies, SDK/API changes, managed service actions, commits, or Library visual changes. Library v17, Manrope, Foundation copyright, standalone atom styles, and pending SSE/context/cancel behavior remain intact.

1. Add an initial-output budget guard and a composition regression. Observe failures before implementation.
2. Replace simple initial Forms bindings with native value/input/change handlers. Keep search composition buffered until compositionend, including suppressed submit during composition. Run focused units and build measurements.
3. Defer palette, inspector, tree, citation and code content at their actual interaction conditions. Defer scoped overlay construction. Preserve error states, focus return, permission gating and dialog cancellation. Run relevant browser regressions and measure.
4. Use measurements to decide whether optional APF implementation ownership and lightweight shell chat state need separation. Keep root/chat/settings symbols and DI identities; test context switch and pending stream cancellation.
5. Preserve synchronous translations; avoid a locale flash or changing public text(key) behavior. Partition feature dictionaries only if the public contract can be retained; otherwise retain dictionaries and optimize other measured initial dependencies.
6. Run library/management/Elements/catalog builds, lints, units, all Chromium tests and packed consumer. Freeze source hashes and report output totals for independent review.

**Review focus:** IME completion versus trailing input; changing tenant during deferred loads; repeated open/close before load resolves; host CSS interference; context/auth resets during pending chat runs.
