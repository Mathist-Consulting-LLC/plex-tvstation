const { createSlug } = require('./utils');

const DEFAULTS = {
  maxItems: 50,
  tvShowLimit: 0,
  rewatchDelay: {
    movies: '180 days',
    tv: '90 days'
  }
};

function normalizeSlugList(values = []) {
  return values.map(createSlug).filter(Boolean);
}

function normalizePlaylist(playlist = {}, defaults) {
  const include = playlist.include || {};
  return {
    ...playlist,
    name: playlist.name || 'TV Station',
    maxItems: playlist.maxItems || defaults.maxItems,
    tvShowLimit: playlist.tvShowLimit ?? defaults.tvShowLimit,
    genre: playlist.genre ? createSlug(playlist.genre) : undefined,
    franchise: playlist.franchise ? createSlug(playlist.franchise) : undefined,
    include: {
      shows: normalizeSlugList(include.shows),
      movies: normalizeSlugList(include.movies)
    }
  };
}

function getPlaylistDefinitions(rawConfig) {
  const playlists = [...(rawConfig.playlists || [])];
  const hasLegacyComfortLists = Boolean(
    (rawConfig.comfortShows && rawConfig.comfortShows.length) ||
    (rawConfig.comfortMovies && rawConfig.comfortMovies.length)
  );
  const hasComfortPlaylist = playlists.some((playlist) => playlist.comfort);

  if (hasLegacyComfortLists && !hasComfortPlaylist) {
    playlists.push({
      name: 'Comfort Shows',
      comfort: true,
      include: {
        shows: rawConfig.comfortShows || [],
        movies: rawConfig.comfortMovies || []
      }
    });
  }

  return playlists;
}

function normalizeConfig(rawConfig = {}) {
  const defaults = {
    ...DEFAULTS,
    ...(rawConfig.defaults || {}),
    rewatchDelay: {
      ...DEFAULTS.rewatchDelay,
      ...((rawConfig.defaults && rawConfig.defaults.rewatchDelay) || {})
    }
  };

  const metadata = (rawConfig.metadata || []).map((entry) => ({
    ...entry,
    slug: createSlug(entry.slug || entry.title)
  })).filter((entry) => entry.slug);

  return {
    defaults,
    playlists: getPlaylistDefinitions(rawConfig).map((playlist) => normalizePlaylist(playlist, defaults)),
    excludedSlugs: normalizeSlugList(rawConfig.excludedSlugs),
    franchises: normalizeSlugList(rawConfig.franchises),
    restrictedPlayMonths: rawConfig.restrictedPlayMonths || {},
    genreMappings: rawConfig.genreMappings || {},
    metadata,
    metadataBySlug: new Map(metadata.map((entry) => [entry.slug, entry]))
  };
}

module.exports = {
  normalizeConfig
};