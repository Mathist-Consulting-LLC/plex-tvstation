const test = require('node:test');
const assert = require('node:assert/strict');

const { normalizeConfig } = require('../../src/node/config');
const { planPlaylist } = require('../../src/node/planner');

const library = {
  shows: [
    {
      slug: 'bobs-burgers',
      title: 'Bob\'s Burgers',
      genres: ['Comedy'],
      lastViewedAt: 10,
      episodes: [
        { ratingKey: 'show-bob-1', title: 'Human Flesh', index: 1, viewCount: 1, lastViewedAt: 10 },
        { ratingKey: 'show-bob-2', title: 'Crawl Space', index: 2, viewCount: 0, lastViewedAt: 0 }
      ]
    },
    {
      slug: 'raising-hope',
      title: 'Raising Hope',
      genres: ['Comedy'],
      lastViewedAt: 5,
      episodes: [
        { ratingKey: 'show-hope-1', title: 'Pilot', index: 1, viewCount: 0, lastViewedAt: 0 },
        { ratingKey: 'show-hope-2', title: 'Dead Tooth', index: 2, viewCount: 0, lastViewedAt: 0 }
      ]
    },
    {
      slug: 'the-expanse',
      title: 'The Expanse',
      genres: ['Science Fiction'],
      lastViewedAt: 1,
      episodes: [
        { ratingKey: 'show-expanse-1', title: 'Dulcinea', index: 1, viewCount: 0, lastViewedAt: 0 }
      ]
    }
  ],
  movies: [
    { slug: 'silent-running', title: 'Silent Running', year: 1972, genres: ['Science Fiction'], ratingKey: 'movie-silent', viewCount: 0, lastViewedAt: 0 },
    { slug: 'christmas-story', title: 'A Christmas Story', year: 1983, genres: ['Comedy'], ratingKey: 'movie-christmas', viewCount: 0, lastViewedAt: 0 },
    { slug: 'excluded-movie', title: 'Excluded Movie', year: 2000, genres: ['Comedy'], ratingKey: 'movie-excluded', viewCount: 0, lastViewedAt: 0 }
  ]
};

test('comfort playlists include explicitly configured shows and movies', () => {
  const config = normalizeConfig({
    playlists: [
      {
        name: 'Comfort Shows',
        comfort: true,
        maxItems: 5,
        include: {
          shows: ['bobs-burgers', 'raising-hope'],
          movies: ['silent-running']
        }
      }
    ]
  });

  const result = planPlaylist({
    library,
    config,
    playlist: config.playlists[0],
    now: new Date('2026-06-25T12:00:00Z'),
    randomIndex: () => 0
  });

  assert.deepEqual(result.items.map((item) => item.ratingKey), [
    'show-hope-1',
    'movie-silent',
    'show-bob-2',
    'show-hope-2'
  ]);
  assert.deepEqual(result.includedSeries.map((series) => series.slug), ['raising-hope', 'movies', 'bobs-burgers']);
});

test('genre playlists rotate shows and the synthetic movies bucket', () => {
  const config = normalizeConfig({
    playlists: [{ name: 'Sci-Fi TV Station', genre: 'Science Fiction', maxItems: 4 }]
  });

  const result = planPlaylist({
    library,
    config,
    playlist: config.playlists[0],
    now: new Date('2026-06-25T12:00:00Z'),
    randomIndex: () => 0
  });

  assert.deepEqual(result.items.map((item) => item.ratingKey), ['movie-silent', 'show-expanse-1']);
  assert.deepEqual(result.includedSeries.map((series) => series.title), ['Movies', 'The Expanse']);
});

test('planner respects excluded slugs and restricted play months', () => {
  const config = normalizeConfig({
    excludedSlugs: ['excluded-movie'],
    restrictedPlayMonths: {
      december: ['christmas']
    },
    playlists: [{ name: 'Comedy TV Station', genre: 'Comedy', maxItems: 10 }]
  });

  const result = planPlaylist({
    library,
    config,
    playlist: config.playlists[0],
    now: new Date('2026-06-25T12:00:00Z'),
    randomIndex: () => 0
  });

  assert.equal(result.items.some((item) => item.ratingKey === 'movie-christmas'), false);
  assert.equal(result.items.some((item) => item.ratingKey === 'movie-excluded'), false);
  assert.deepEqual(result.items.map((item) => item.ratingKey), ['show-hope-1', 'show-bob-2', 'show-hope-2']);
});