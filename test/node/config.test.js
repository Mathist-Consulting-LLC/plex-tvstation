const test = require('node:test');
const assert = require('node:assert/strict');

const { normalizeConfig } = require('../../src/node/config');

test('normalizeConfig applies defaults and normalizes playlist definitions', () => {
  const config = normalizeConfig({
    playlists: [
      { name: 'TV Station', type: 'all' },
      { name: 'Sci-Fi TV Station', genre: 'Science Fiction' }
    ]
  });

  assert.equal(config.defaults.maxItems, 50);
  assert.equal(config.defaults.tvShowLimit, 0);
  assert.equal(config.defaults.rewatchDelay.movies, '180 days');
  assert.equal(config.defaults.rewatchDelay.tv, '90 days');
  assert.equal(config.playlists[0].name, 'TV Station');
  assert.equal(config.playlists[1].genre, 'science-fiction');
});

test('normalizeConfig keeps comfort show and movie include lists separate', () => {
  const config = normalizeConfig({
    playlists: [
      {
        name: 'Comfort Shows',
        comfort: true,
        include: {
          shows: ['Bob\'s Burgers', 'raising-hope'],
          movies: ['Silent Running']
        }
      }
    ]
  });

  assert.deepEqual(config.playlists[0].include.shows, ['bobs-burgers', 'raising-hope']);
  assert.deepEqual(config.playlists[0].include.movies, ['silent-running']);
});


test('normalizeConfig creates a comfort playlist from legacy comfort lists', () => {
  const config = normalizeConfig({
    comfortShows: ['Bob\'s Burgers'],
    comfortMovies: ['Silent Running']
  });

  assert.equal(config.playlists[0].name, 'Comfort Shows');
  assert.equal(config.playlists[0].comfort, true);
  assert.deepEqual(config.playlists[0].include.shows, ['bobs-burgers']);
  assert.deepEqual(config.playlists[0].include.movies, ['silent-running']);
});

test('normalizeConfig exposes metadata by slug', () => {
  const config = normalizeConfig({
    metadata: [
      { slug: 'Silent Running', year: 1972, rewatchDelay: '1 year' },
      { slug: 'bobs-burgers', alwaysInclude: true }
    ]
  });

  assert.equal(config.metadataBySlug.get('silent-running').year, 1972);
  assert.equal(config.metadataBySlug.get('bobs-burgers').alwaysInclude, true);
});