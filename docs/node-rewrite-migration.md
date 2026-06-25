# Node Rewrite Migration

Issue #1 tracks the full Python-to-Node rewrite. This branch starts with the safest first slice: pure playlist planning and a dry-run CLI. It does not write to Plex yet.

## Current Node Commands

Run all Node tests:

```bash
npm test
```

Run a dry-run against JSON fixture data:

```bash
node src/node/cli.js dry-run --config config/example.json --library path/to/library-fixture.json
```

The dry-run prints planned playlists as JSON and performs no Plex API calls.

## Config Direction

Use `config/example.json` as the new shape. Playlist definitions are explicit, and the comfort playlist can include separate show and movie slug lists:

```json
{
  "name": "Comfort Shows",
  "comfort": true,
  "include": {
    "shows": ["bobs-burgers"],
    "movies": ["silent-running"]
  }
}
```

Secrets and machine-local values should stay in `.env` or future uncommitted local config, not in committed JSON.

## Still To Migrate

- Plex API reads and writes.
- Active playback session skip behavior.
- Watched-status reset behavior.
- Scheduled `pop-os` service or cron entry.
- Discovery and shutdown of the old WSL job after the Node job is verified.
- Static web/cache report behavior, unless intentionally kept in Python or split into a later issue.