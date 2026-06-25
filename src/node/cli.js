#!/usr/bin/env node
const { readFile } = require('node:fs/promises');
const { normalizeConfig } = require('./config');
const { planPlaylist } = require('./planner');

function readOption(args, name) {
  const index = args.indexOf(name);
  if (index === -1 || index === args.length - 1) {
    return undefined;
  }
  return args[index + 1];
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, 'utf8'));
}

async function run(argv = process.argv.slice(2)) {
  const command = argv[0];

  if (command !== 'dry-run') {
    throw new Error('Usage: node src/node/cli.js dry-run --config <config.json> --library <library.json>');
  }

  const configPath = readOption(argv, '--config');
  const libraryPath = readOption(argv, '--library');

  if (!configPath || !libraryPath) {
    throw new Error('dry-run requires --config and --library');
  }

  const config = normalizeConfig(await readJson(configPath));
  const library = await readJson(libraryPath);
  const playlists = config.playlists.map((playlist) => planPlaylist({ library, config, playlist }));

  return { playlists };
}

if (require.main === module) {
  run()
    .then((result) => {
      process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    })
    .catch((error) => {
      process.stderr.write(`${error.message}\n`);
      process.exitCode = 1;
    });
}

module.exports = {
  run
};