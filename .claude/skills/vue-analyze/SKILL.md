---
name: vue-analyze
description: Analyze Vue 3 component structure across client/src for performance issues and code-reuse opportunities, and report findings (no edits). Use when asked to review/audit Vue components for optimization, find duplicate component logic or markup, or evaluate reactivity patterns.
---

# Vue Component Structure Analysis

Report-only audit of this app's Vue 3 components for **performance** issues and **code-reuse** opportunities. This skill never edits files — it produces a findings report. If the user wants fixes applied after reviewing the report, that's a separate, explicit follow-up (e.g. delegate to the `vue-expert` subagent per this project's CLAUDE.md rule for `.vue` file edits).

## Scope

- **Default (no argument given):** sweep the whole component tree — `client/src/views/*.vue`, `client/src/components/*.vue`, `client/src/composables/*.js`.
- **If the user names a file or directory:** scope the analysis to that path only, but still cross-reference it against the rest of `client/src` for reuse findings (a single component can't be "duplicated" in isolation).

Use Glob to enumerate files in scope before reading. For a full sweep, read every `.vue`/`.js` file in scope — don't sample. If the tree is large enough that reading everything would be wasteful of context, delegate the read-and-extract-findings pass to the `Explore` agent or a `general-purpose` agent, but still ensure full coverage rather than a partial sample.

## Performance Checklist

For each component, check for:

1. **Method calls in templates instead of computed** — `{{ calculateTotal() }}` re-runs on every render; a `computed()` caches until dependencies change. Flag any method invoked directly in a template that only reads reactive state and returns a derived value.
2. **Watchers that duplicate what `computed` should do** — a `watch()` that just re-derives and assigns a ref is usually a computed in disguise. Legitimate watchers cause a side effect (API call, DOM manipulation); ones that just recompute a value should be computed.
3. **`v-for` without a stable unique `:key`** — index-as-key (`:key="index"` or no key) causes incorrect DOM reuse on reorder/insert/delete. Check against `item.id`, `item.sku`, or another stable field.
4. **`v-if` vs `v-show` mismatch** — elements toggled frequently (tabs, expand/collapse, filter-driven visibility) should use `v-show` (CSS toggle) not `v-if` (DOM add/remove), per this project's own `client/CLAUDE.md` guidance. Flag the reverse too: rarely-shown heavy content using `v-show` (wastes initial render cost).
5. **New object/array/function literals passed as props** — `:config="{ foo: bar }"` or `:onClick="() => doThing()"` inline in a template creates a new reference every parent render, defeating child memoization/causing unnecessary child updates. Flag and suggest hoisting to a computed or method reference.
6. **Unnecessary deep reactivity on large datasets** — a `ref([])`/`reactive([])` holding a large array that's only ever replaced wholesale (never mutated in place) doesn't need Vue's deep reactivity tracking overhead; note where `shallowRef` would be more appropriate.
7. **Console logging or debug statements left in hot paths** — logging inside a computed, a per-item template method, or a loop that runs on every render/every list item is both a performance and cleanliness issue. (This codebase has a live example: `client/src/views/Reports.vue`'s `formatNumber`/`formatMonth`/bar-height helpers `console.log` on every invocation, firing dozens of times per render — flag this pattern anywhere it recurs.)
8. **Missing debounce on filter-driven API calls** — a `watch()` on filter refs that immediately re-fetches on every keystroke/selection change without debouncing causes redundant network calls. Cross-check against the `watchDebounced` pattern already documented in `client/CLAUDE.md`.
9. **Oversized single-responsibility components** — a view or component file mixing many unrelated concerns (say, >300 lines with several distinct UI regions and no sub-component extraction) makes the whole tree re-render for unrelated state changes. Note candidates for splitting, and name the natural seams.

## Code-Reuse Checklist

This is about finding duplication *across* files, not just within one:

1. **Duplicate structural/CSS scaffolding across components** — grep for repeated class names or repeated blocks of scoped CSS across multiple `.vue` files. This codebase has a confirmed live example: `BacklogDetailModal.vue`, `PurchaseOrderModal.vue`, `ProfileDetailsModal.vue`, `TasksModal.vue`, `CostDetailModal.vue`, `InventoryDetailModal.vue`, and `ProductDetailModal.vue` all reimplement the same `modal-overlay`/`modal-container`/`modal-header`/close-button/`Transition name="modal"` scaffolding independently. Flag this class of duplication anywhere it appears (not just modals) and suggest extracting a shared base component (e.g. a `BaseModal.vue` wrapper taking a title/slot) or at minimum shared scoped-style tokens.
2. **Duplicated data-loading boilerplate** — the `loading`/`error`/`data` ref triad plus try/catch/finally documented in `client/CLAUDE.md`'s "Data Loading Pattern" is repeated near-verbatim across views. Flag files repeating this and suggest a `useAsyncData`/`useApiResource` composable, similar in spirit to the existing `useFilters` composable.
3. **Reimplemented formatting logic** — search for local currency/date/number formatting that duplicates `client/src/utils/currency.js` (or any other shared util) instead of importing it. Flag every local reimplementation found.
4. **Duplicated filter-application logic** — code that re-filters by warehouse/category/status/month inline instead of going through the `useFilters` composable's `getCurrentFilters()`/`hasActiveFilters` helpers.
5. **Repeated badge/status/priority styling** — CSS blocks for priority badges (`high`/`medium`/`low`), stock-status badges, etc. duplicated verbatim in multiple components' `<style scoped>` sections instead of a shared class set or a small `<StatusBadge>` component.
6. **Copy-pasted chart/SVG rendering logic** — if two components build structurally similar SVG charts with separately-maintained scaling/axis math, flag as an extraction candidate.

## How to Analyze

1. `Glob` for files in scope.
2. Read every file in scope (batch via a subagent if the sweep is large — see Scope section).
3. For **performance**, evaluate each file independently against the checklist above.
4. For **code-reuse**, this requires cross-file comparison: after reading, look for repeated class names, repeated method/computed shapes, repeated CSS blocks, and repeated import-then-reimplement patterns (e.g. formatting a currency by hand instead of importing `formatCurrency`). `grep`/`Bash` across the file set is useful here to quickly find which files share a given pattern (as done to confirm the modal duplication above) rather than relying purely on memory across many file reads.
5. Only report findings you've verified by reading the actual code — don't speculate about a file you haven't opened.

## Report Format

Do not use the `ReportFindings` tool (that's reserved for the `/code-review` skill's flow) — write the report directly as markdown:

```markdown
## Vue Component Analysis — <scope>

### Performance (N findings)
1. **`path/to/File.vue:LINE`** — <one-line issue> → <concrete suggested fix>
2. ...

### Code Reuse (N findings)
1. **`fileA.vue`, `fileB.vue`, `fileC.vue`** — <what's duplicated> → <suggested extraction, named concretely, e.g. "extract `BaseModal.vue` taking `title` prop + default slot">
2. ...

### Top 3 Highest-Impact Suggestions
1. ...
2. ...
3. ...
```

Rank by impact, not just count — a duplication spanning 7 files outweighs five isolated single-file nitpicks. End with the top-3 list so the user can act on the highest-value items first without reading the full report.

After presenting the report, ask the user whether they want any of the suggestions implemented — don't apply changes unprompted.
