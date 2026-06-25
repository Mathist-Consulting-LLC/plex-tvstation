const { normalizeGenres } = require('./utils');

function isExcluded(slug, config) {
  return config.excludedSlugs.includes(slug);
}

function isRestrictedThisMonth(slug, config, now) {
  const currentMonth = now.toLocaleString('en-US', { month: 'long', timeZone: 'UTC' }).toLowerCase();

  return Object.entries(config.restrictedPlayMonths).some(([month, partials]) => {
    if (month.toLowerCase() === currentMonth) {
      return false;
    }
    return Array.isArray(partials) && partials.some((partial) => slug.includes(String(partial).toLowerCase()));
  });
}

function matchesGenre(item, playlist, config) {
  if (!playlist.genre) {
    return true;
  }
  return normalizeGenres(item.genres, config.genreMappings).has(playlist.genre);
}

function getUnwatchedEpisodes(show) {
  return (show.episodes || [])
    .filter((episode) => (episode.viewCount || 0) === 0)
    .map((episode) => ({
      ratingKey: episode.ratingKey,
      type: 'tv',
      title: episode.title,
      seriesTitle: show.title,
      index: episode.index
    }));
}

function getEligibleShowSeries(library, config, playlist) {
  return (library.shows || [])
    .filter((show) => !isExcluded(show.slug, config))
    .filter((show) => {
      if (playlist.comfort) {
        return playlist.include.shows.includes(show.slug);
      }
      return matchesGenre(show, playlist, config);
    })
    .map((show) => ({
      slug: show.slug,
      title: show.title,
      lastViewedAt: show.lastViewedAt || 0,
      items: getUnwatchedEpisodes(show)
    }))
    .filter((series) => series.items.length > 0)
    .sort((a, b) => a.lastViewedAt - b.lastViewedAt || a.title.localeCompare(b.title));
}

function getEligibleMovieSeries(library, config, playlist, now) {
  const movies = (library.movies || [])
    .filter((movie) => !isExcluded(movie.slug, config))
    .filter((movie) => !isRestrictedThisMonth(movie.slug, config, now))
    .filter((movie) => (movie.viewCount || 0) === 0)
    .filter((movie) => {
      if (playlist.comfort) {
        return playlist.include.movies.includes(movie.slug);
      }
      return matchesGenre(movie, playlist, config);
    })
    .slice()
    .sort((a, b) => (a.year || 0) - (b.year || 0) || a.title.localeCompare(b.title))
    .map((movie) => ({
      ratingKey: movie.ratingKey,
      type: 'movie',
      title: movie.year ? `${movie.title} (${movie.year})` : movie.title,
      seriesTitle: 'Movies',
      index: movie.year || 0
    }));

  if (movies.length === 0) {
    return null;
  }

  return {
    slug: 'movies',
    title: 'Movies',
    lastViewedAt: Math.max(0, ...(library.movies || []).map((movie) => movie.lastViewedAt || 0)),
    items: movies
  };
}

function orderSeries(showSeries, movieSeries, playlist) {
  if (!movieSeries) {
    return showSeries;
  }

  if (playlist.comfort) {
    if (showSeries.length === 0) {
      return [movieSeries];
    }
    return [showSeries[0], movieSeries, ...showSeries.slice(1)];
  }

  return [...showSeries, movieSeries]
    .sort((a, b) => a.lastViewedAt - b.lastViewedAt || a.title.localeCompare(b.title));
}

function rotateSeries(seriesList, maxItems) {
  const items = [];
  const indexes = new Map();

  while (items.length < maxItems) {
    let added = false;

    for (const series of seriesList) {
      const nextIndex = indexes.get(series.slug) || 0;
      if (nextIndex >= series.items.length) {
        continue;
      }

      items.push(series.items[nextIndex]);
      indexes.set(series.slug, nextIndex + 1);
      added = true;

      if (items.length >= maxItems) {
        break;
      }
    }

    if (!added) {
      break;
    }
  }

  return items;
}

function planPlaylist({ library, config, playlist, now = new Date() }) {
  const showSeries = getEligibleShowSeries(library, config, playlist);
  const movieSeries = getEligibleMovieSeries(library, config, playlist, now);
  const includedSeries = orderSeries(showSeries, movieSeries, playlist);

  return {
    name: playlist.name,
    includedSeries: includedSeries.map(({ slug, title, items }) => ({ slug, title, itemCount: items.length })),
    items: rotateSeries(includedSeries, playlist.maxItems || config.defaults.maxItems)
  };
}

module.exports = {
  planPlaylist
};