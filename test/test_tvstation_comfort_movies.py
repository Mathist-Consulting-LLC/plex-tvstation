import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import tvstation


def make_args(**overrides):
    values = {
        'genre': 'comfort',
        'franchise': None,
        'log_only': True,
        'reset': False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ComfortMoviesTests(unittest.TestCase):
    def test_set_plex_globals_keeps_comfort_show_and_movie_slugs_separate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / 'local_config.json'
            config_path.write_text(json.dumps({
                'defaultRewatchDelay': {'movies': '180 days', 'tv': '90 days'},
                'comfortShows': ['Bob\'s Burgers', {'title': 'The Good Place'}],
                'comfortMovies': ['Silent Running', {'slug': 'the-princess-bride'}],
            }))

            tvstation.set_plex_globals(make_args(), config_path, temp_path)

            self.assertEqual(
                tvstation.PLEX_GLOBALS['comfort_show_slugs'],
                ['bobs-burgers', 'the-good-place'],
            )
            self.assertEqual(
                tvstation.PLEX_GLOBALS['comfort_movie_slugs'],
                ['silent-running', 'the-princess-bride'],
            )

    def test_comfort_mode_builds_movies_only_when_comfort_movies_are_configured(self):
        args = make_args()
        tvstation.PLEX_GLOBALS = {
            'genre': 'comfort',
            'comfort_movie_slugs': ['silent-running'],
            'log_file': Path('/tmp/comfort-shows.md'),
            'log_dir': Path('/tmp'),
        }

        calls = []

        def record(name):
            def inner(*_args, **_kwargs):
                calls.append(name)
                if name == 'replace_playlist_items':
                    return 'updated'
                return None
            return inner

        with patch.object(tvstation, 'load_globals', record('load_globals')), \
             patch.object(tvstation, 'get_series_globals', record('get_series_globals')), \
             patch.object(tvstation, 'get_playlist_globals', record('get_playlist_globals')), \
             patch.object(tvstation, 'build_series_episodes', record('build_series_episodes')), \
             patch.object(tvstation, 'build_movie_list', record('build_movie_list')), \
             patch.object(tvstation, 'build_playlist_episode_keys', record('build_playlist_episode_keys')), \
             patch.object(tvstation, 'is_media_being_watched', return_value=False), \
             patch.object(tvstation, 'replace_playlist_items', record('replace_playlist_items')):
            result = tvstation.my_tv_station(object(), args)

        self.assertEqual(result, 'updated')
        self.assertIn('build_movie_list', calls)

    def test_comfort_mode_skips_movies_when_no_comfort_movies_are_configured(self):
        args = make_args()
        tvstation.PLEX_GLOBALS = {
            'genre': 'comfort',
            'comfort_movie_slugs': [],
            'log_file': Path('/tmp/comfort-shows.md'),
            'log_dir': Path('/tmp'),
        }

        with patch.object(tvstation, 'load_globals'), \
             patch.object(tvstation, 'get_series_globals'), \
             patch.object(tvstation, 'get_playlist_globals'), \
             patch.object(tvstation, 'build_series_episodes'), \
             patch.object(tvstation, 'build_movie_list') as build_movie_list, \
             patch.object(tvstation, 'build_playlist_episode_keys'), \
             patch.object(tvstation, 'is_media_being_watched', return_value=False), \
             patch.object(tvstation, 'replace_playlist_items', return_value='updated'):
            result = tvstation.my_tv_station(object(), args)

        self.assertEqual(result, 'updated')
        build_movie_list.assert_not_called()


if __name__ == '__main__':
    unittest.main()
