const test = require('node:test');
const assert = require('node:assert/strict');
const { execFile } = require('node:child_process');
const { mkdtemp, writeFile } = require('node:fs/promises');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const { promisify } = require('node:util');

const execFileAsync = promisify(execFile);

test('dry-run prints planned playlist JSON without Plex mutation', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'plex-tvstation-'));
  const configPath = join(dir, 'config.json');
  const libraryPath = join(dir, 'library.json');

  await writeFile(configPath, JSON.stringify({
    playlists: [
      {
        name: 'Comfort Shows',
        comfort: true,
        include: {
          shows: ['Raising Hope'],
          movies: ['Silent Running']
        }
      }
    ]
  }));

  await writeFile(libraryPath, JSON.stringify({
    shows: [
      {
        slug: 'raising-hope',
        title: 'Raising Hope',
        genres: ['Comedy'],
        episodes: [
          { ratingKey: 'show-hope-1', title: 'Pilot', index: 1, viewCount: 0 }
        ]
      }
    ],
    movies: [
      { slug: 'silent-running', title: 'Silent Running', year: 1972, genres: ['Science Fiction'], ratingKey: 'movie-silent', viewCount: 0 }
    ]
  }));

  const { stdout } = await execFileAsync(process.execPath, [
    'src/node/cli.js',
    'dry-run',
    '--config',
    configPath,
    '--library',
    libraryPath
  ], { cwd: process.cwd() });

  const result = JSON.parse(stdout);
  assert.equal(result.playlists[0].name, 'Comfort Shows');
  assert.deepEqual(result.playlists[0].items.map((item) => item.ratingKey), ['show-hope-1', 'movie-silent']);
});