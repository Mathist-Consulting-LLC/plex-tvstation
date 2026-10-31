import io
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from comfort_web import ComfortWebApp, read_config, update_config_selection


class FakeResponse:
    def __init__(self, payload=None, content=b'', headers=None, status_code=200):
        self.payload = payload or {}
        self.content = content
        self.headers = headers or {}
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class FakePlexSession:
    def __init__(self):
        self.requests = []

    def get(self, url, params=None, headers=None, **_kwargs):
        self.requests.append((url, params or {}, headers or {}))
        path = url.removeprefix('http://plex.test')
        if path == '/library/sections/':
            return FakeResponse({
                'MediaContainer': {
                    'Directory': [
                        {'title': 'Movies', 'type': 'movie', 'key': '1'},
                        {'title': 'TV Shows', 'type': 'show', 'key': '2'},
                    ]
                }
            })
        if path == '/library/sections/1/all':
            return FakeResponse({
                'MediaContainer': {
                    'Metadata': [
                        {'title': 'Silent Running', 'slug': 'silent-running', 'thumb': '/library/metadata/10/thumb'},
                        {'title': 'The Princess Bride', 'slug': 'the-princess-bride', 'thumb': '/library/metadata/11/thumb'},
                    ]
                }
            })
        if path == '/library/sections/2/all':
            return FakeResponse({
                'MediaContainer': {
                    'Metadata': [
                        {'title': "Bob's Burgers", 'slug': 'bobs-burgers', 'thumb': '/library/metadata/20/thumb'},
                        {'title': 'The Good Place', 'slug': 'the-good-place', 'thumb': '/library/metadata/21/thumb'},
                    ]
                }
            })
        if path.startswith('/library/metadata/') and path.endswith('/thumb'):
            return FakeResponse(content=b'fake image', headers={'Content-Type': 'image/jpeg'})
        return FakeResponse(status_code=404)


class FailingPlexSession:
    def get(self, *_args, **_kwargs):
        raise requests.ConnectionError('Plex unavailable')


class FakeHandler:
    def __init__(self, path, body=None):
        self.path = path
        encoded = json.dumps(body).encode('utf-8') if body is not None else b''
        self.headers = {'Content-Length': str(len(encoded))}
        self.rfile = io.BytesIO(encoded)
        self.wfile = io.BytesIO()
        self.status = None
        self.response_headers = {}

    def send_response(self, status):
        self.status = int(status)

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass

    @property
    def body_text(self):
        return self.wfile.getvalue().decode('utf-8')

    @property
    def json(self):
        return json.loads(self.body_text)


class ComfortWebTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / 'local_config.json'
        self.config_path.write_text(json.dumps({
            'comfortShows': ["Bob's Burgers"],
            'comfortMovies': ['silent-running'],
            'metadata': [{'slug': 'untouched'}],
            'unrelated': {'keep': True},
        }))
        self.session = FakePlexSession()
        self.app = ComfortWebApp(self.config_path, 'http://plex.test', 'token-secret', session=self.session)

    def tearDown(self):
        self.temp_dir.cleanup()

    def get(self, path):
        handler = FakeHandler(path)
        self.app.handle_get(handler)
        return handler

    def post(self, path, body):
        handler = FakeHandler(path, body)
        self.app.handle_post(handler)
        return handler

    def test_pages_and_api_do_not_expose_plex_token_and_show_checked_state(self):
        html_response = self.get('/shows')
        self.assertEqual(html_response.status, 200)
        self.assertNotIn('token-secret', html_response.body_text)

        api_response = self.get('/api/shows')
        self.assertEqual(api_response.status, 200)
        payload = api_response.json

        self.assertNotIn('token-secret', json.dumps(payload))
        self.assertEqual(
            [(item['slug'], item['checked']) for item in payload['items']],
            [('bobs-burgers', True), ('the-good-place', False)],
        )
        for url, _params, _headers in self.session.requests:
            self.assertNotIn('token-secret', url)

    def test_movies_listing_and_artwork_are_proxied_without_browser_token(self):
        movie_response = self.get('/api/movies')
        movie_payload = movie_response.json
        artwork_url = movie_payload['items'][0]['artworkUrl']
        self.assertEqual(artwork_url, '/artwork/movies/silent-running')
        self.assertNotIn('token-secret', json.dumps(movie_payload))

        artwork_response = self.get(artwork_url)

        self.assertEqual(artwork_response.status, 200)
        self.assertEqual(artwork_response.wfile.getvalue(), b'fake image')
        self.assertEqual(artwork_response.response_headers['Content-Type'], 'image/jpeg')
        for url, _params, _headers in self.session.requests:
            self.assertNotIn('token-secret', url)

    def test_plex_token_is_sent_only_to_server_side_session_params(self):
        self.get('/api/movies')

        self.assertTrue(self.session.requests)
        self.assertTrue(all(params == {'X-Plex-Token': 'token-secret'} for _url, params, _headers in self.session.requests))
        self.assertTrue(all(headers['Accept'] == 'application/json' for _url, _params, headers in self.session.requests))

    def test_request_handler_returns_a_gateway_error_when_plex_is_unavailable(self):
        app = ComfortWebApp(self.config_path, 'http://plex.test', 'token-secret', session=FailingPlexSession())
        handler_class = app.request_handler()
        handler = object.__new__(handler_class)
        handler.path = '/api/movies'
        handler.wfile = io.BytesIO()
        handler.send_response = lambda status: setattr(handler, 'status', int(status))
        handler.send_header = lambda *_args: None
        handler.end_headers = lambda: None

        handler.do_GET()

        self.assertEqual(handler.status, 502)
        self.assertIn('Could not load Plex library', handler.wfile.getvalue().decode('utf-8'))

    def test_check_uncheck_recheck_for_both_kinds_preserves_unrelated_config(self):
        unchecked = self.post('/api/shows/bobs-burgers', {'checked': False})
        checked = self.post('/api/shows/bobs-burgers', {'checked': True})
        movie_unchecked = self.post('/api/movies/silent-running', {'checked': False})
        movie_rechecked = self.post('/api/movies/silent-running', {'checked': True})

        self.assertEqual(unchecked.status, 200)
        self.assertEqual(checked.status, 200)
        self.assertEqual(movie_unchecked.status, 200)
        self.assertEqual(movie_rechecked.status, 200)
        config = read_config(self.config_path)
        self.assertEqual(config['comfortShows'], ['bobs-burgers'])
        self.assertEqual(config['comfortMovies'], ['silent-running'])
        self.assertEqual(config['metadata'], [{'slug': 'untouched'}])
        self.assertEqual(config['unrelated'], {'keep': True})

    def test_update_dedupes_and_removes_all_slug_representations(self):
        self.config_path.write_text(json.dumps({
            'comfortShows': [
                "Bob's Burgers",
                {'title': "Bob's Burgers"},
                {'slug': 'bobs-burgers'},
                'the-good-place',
            ],
            'comfortMovies': ['silent-running', 'Silent Running', {'slug': 'silent-running'}],
        }))

        update_config_selection(self.config_path, 'shows', 'bobs-burgers', False)
        update_config_selection(self.config_path, 'movies', 'silent-running', True)
        update_config_selection(self.config_path, 'movies', 'silent-running', True)

        config = read_config(self.config_path)
        self.assertEqual(config['comfortShows'], ['the-good-place'])
        self.assertEqual(config['comfortMovies'], ['silent-running'])

    def test_invalid_requests_are_rejected(self):
        not_bool = self.post('/api/shows/bobs-burgers', {'checked': 'yes'})
        bad_slug = self.post('/api/shows/Bobs%20Burgers', {'checked': True})
        missing = self.post('/api/nope/bobs-burgers', {'checked': True})

        self.assertEqual(not_bool.status, 400)
        self.assertEqual(bad_slug.status, 400)
        self.assertEqual(missing.status, 404)

    def test_save_failure_returns_error_without_mutating_ui_contract(self):
        app = ComfortWebApp(self.config_path, 'http://plex.test', 'token-secret', session=self.session, lock_path=Path('/dev/null/nope.lock'))
        handler = FakeHandler('/api/shows/bobs-burgers', {'checked': False})
        app.handle_post(handler)

        self.assertEqual(handler.status, 500)
        self.assertIn('Could not save selection', handler.json['error'])
        self.assertEqual(read_config(self.config_path)['comfortShows'], ["Bob's Burgers"])

    def test_concurrent_updates_are_locked_and_atomic(self):
        self.config_path.write_text(json.dumps({
            'comfortShows': [],
            'comfortMovies': [],
            'unrelated': {'keep': True},
        }))

        show_slugs = [f'show-{index}' for index in range(20)]
        movie_slugs = [f'movie-{index}' for index in range(20)]

        def update(slug_kind):
            kind, slug = slug_kind
            update_config_selection(self.config_path, kind, slug, True)

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(update, [('shows', slug) for slug in show_slugs] + [('movies', slug) for slug in movie_slugs]))

        config = read_config(self.config_path)
        self.assertEqual(sorted(config['comfortShows']), sorted(show_slugs))
        self.assertEqual(sorted(config['comfortMovies']), sorted(movie_slugs))
        self.assertEqual(config['unrelated'], {'keep': True})


if __name__ == '__main__':
    unittest.main()
