const test = require('node:test');
const assert = require('node:assert/strict');

const { createSlug, normalizeGenres, parseDurationToDays } = require('../../src/node/utils');

test('createSlug normalizes titles into stable Plex-style slugs', () => {
  assert.equal(createSlug('Bob\'s Burgers'), 'bobs-burgers');
  assert.equal(createSlug('Star Trek: Strange New Worlds'), 'star-trek-strange-new-worlds');
  assert.equal(createSlug('  The Matrix Reloaded  '), 'the-matrix-reloaded');
});

test('parseDurationToDays supports days, months, and years', () => {
  assert.equal(parseDurationToDays('30 days'), 30);
  assert.equal(parseDurationToDays('6 months'), 180);
  assert.equal(parseDurationToDays('1 year'), 365);
  assert.equal(parseDurationToDays(45), 45);
});

test('normalizeGenres accepts strings, arrays, Plex genre objects, and mappings', () => {
  const mappings = {
    scifi: 'sci-fi',
    'science fiction': 'sci-fi',
    'romantic comedy': 'rom-com'
  };

  assert.deepEqual(normalizeGenres('Science Fiction & Adventure', mappings), new Set(['sci-fi', 'adventure']));
  assert.deepEqual(normalizeGenres(['Comedy', 'Romantic Comedy'], mappings), new Set(['comedy', 'rom-com']));
  assert.deepEqual(normalizeGenres([{ tag: 'SciFi' }, { tag: 'Action' }], mappings), new Set(['sci-fi', 'action']));
  assert.deepEqual(normalizeGenres(undefined, mappings), new Set());
});