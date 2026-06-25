function createSlug(value) {
  if (value === undefined || value === null) {
    return '';
  }

  return String(value)
    .trim()
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/'/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function parseDurationToDays(duration) {
  if (Number.isInteger(duration)) {
    return duration;
  }

  const match = String(duration || '').trim().toLowerCase().match(/^(\d+)\s+(day|days|month|months|year|years)$/);
  if (!match) {
    return 365;
  }

  const amount = Number.parseInt(match[1], 10);
  const unit = match[2];

  if (unit.startsWith('day')) {
    return amount;
  }
  if (unit.startsWith('month')) {
    return amount * 30;
  }
  return amount * 365;
}

function normalizeGenres(genres, mappings = {}) {
  if (genres === undefined || genres === null) {
    return new Set();
  }

  const rawGenres = Array.isArray(genres) ? genres : [genres];
  const parts = rawGenres.flatMap((genre) => {
    if (typeof genre === 'object' && genre !== null && typeof genre.tag === 'string') {
      return genre.tag;
    }
    return String(genre).split(/\s*(?:,|&|\band\b)\s*/i);
  });

  return new Set(parts
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean)
    .map((part) => mappings[part] || createSlug(part)));
}

module.exports = {
  createSlug,
  normalizeGenres,
  parseDurationToDays
};