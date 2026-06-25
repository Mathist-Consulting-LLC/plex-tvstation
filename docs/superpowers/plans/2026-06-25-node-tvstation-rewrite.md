# Node TV Station Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Node.js rewrite slice for Plex TV station playlist planning with a dry-run CLI and tests.

**Architecture:** This PR keeps Plex mutation out of scope. It adds pure config normalization, playlist planning, and a dry-run CLI so behavior can be tested before live Plex integration.

**Tech Stack:** Plain JavaScript on Node.js 24, built-in `node:test`, CommonJS modules.

---

### Task 1: Utilities

**Files:** `src/node/utils.js`, `test/node/utils.test.js`

- [x] Write failing tests for slug creation, duration parsing, and genre normalization.
- [x] Implement `createSlug`, `parseDurationToDays`, and `normalizeGenres`.
- [x] Verify `npm test -- test/node/utils.test.js` passes.

### Task 2: Config Normalization

**Files:** `src/node/config.js`, `test/node/config.test.js`, `config/example.json`

- [x] Write failing tests for defaults, playlist normalization, comfort include lists, and metadata lookup.
- [x] Implement `normalizeConfig(rawConfig)`.
- [x] Add `config/example.json` for the proposed config shape.
- [x] Verify `npm test -- test/node/config.test.js` passes.

### Task 3: Pure Playlist Planner

**Files:** `src/node/planner.js`, `test/node/planner.test.js`

- [x] Write failing tests for comfort movies, rotation, exclusions, and restricted months.
- [x] Implement `planPlaylist({ library, config, playlist, now })` against fixture-shaped data.
- [x] Verify `npm test -- test/node/planner.test.js` passes.

### Task 4: Dry-Run CLI

**Files:** `src/node/cli.js`, `test/node/cli.test.js`

- [x] Write a failing CLI test using temp JSON fixture files.
- [x] Implement `dry-run --config <file> --library <file>`.
- [x] Verify `npm test -- test/node/cli.test.js` passes.

### Task 5: Documentation And Validation

**Files:** `README.md`, `docs/node-rewrite-migration.md`

- [x] Document the Node dry-run slice and remaining migration work.
- [ ] Run `npm test`.
- [ ] Run `git diff --check`.