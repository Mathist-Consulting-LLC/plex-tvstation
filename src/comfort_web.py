#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import fcntl
import html
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import requests
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(_path):
        return False

from tvstation import create_slug, normalize_config_slugs


KINDS = {
    'shows': {
        'config_key': 'comfortShows',
        'plex_type': 'show',
        'section_titles': ('TV Shows', 'Shows'),
        'page_title': 'Comfort Shows',
    },
    'movies': {
        'config_key': 'comfortMovies',
        'plex_type': 'movie',
        'section_titles': ('Movies',),
        'page_title': 'Comfort Movies',
    },
}

_THREAD_LOCKS = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class ConfigUpdateError(Exception):
    pass


class ComfortWebApp:
    def __init__(self, config_path, plex_base_url, plex_token, session=None, lock_path=None):
        self.config_path = Path(config_path)
        self.plex_base_url = plex_base_url.rstrip('/')
        self.plex_token = plex_token
        self.session = session or requests.Session()
        self.lock_path = Path(lock_path) if lock_path else self.config_path.with_suffix(self.config_path.suffix + '.lock')
        self._sections_lock = threading.Lock()
        self._section_keys = {}

    def request_handler(self):
        app = self

        class ComfortRequestHandler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_GET(self):
                try:
                    app.handle_get(self)
                except (requests.RequestException, LookupError, ValueError) as exc:
                    app._send_json(
                        self,
                        {'error': f'Could not load Plex library: {exc}'},
                        HTTPStatus.BAD_GATEWAY,
                    )

            def do_POST(self):
                app.handle_post(self)

        return ComfortRequestHandler

    def handle_get(self, handler):
        parsed = urlparse(handler.path)
        path = parsed.path.rstrip('/') or '/'

        if path == '/':
            self._redirect(handler, '/shows')
            return
        if path in ('/shows', '/movies'):
            self._send_html(handler, self.render_page(path.lstrip('/')))
            return
        if path in ('/api/shows', '/api/movies'):
            kind = path.rsplit('/', 1)[1]
            self._send_json(handler, {'items': self.list_items(kind)})
            return
        if path.startswith('/artwork/'):
            parts = path.split('/', 3)
            if len(parts) == 4 and parts[2] in KINDS:
                self.proxy_artwork(handler, parts[2], unquote(parts[3]))
                return

        self._send_json(handler, {'error': 'Not found'}, HTTPStatus.NOT_FOUND)

    def handle_post(self, handler):
        parsed = urlparse(handler.path)
        parts = parsed.path.strip('/').split('/')
        if len(parts) == 3 and parts[0] == 'api' and parts[1] in KINDS:
            kind = parts[1]
            slug = unquote(parts[2])
            try:
                body = self._read_json(handler)
                checked = body['checked']
                if not isinstance(checked, bool):
                    raise ValueError('checked must be a boolean')
                updated = update_config_selection(self.config_path, kind, slug, checked, self.lock_path)
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                self._send_json(handler, {'error': str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self._send_json(
                    handler,
                    {'error': f'Could not save selection: {exc}'},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            self._send_json(handler, {'slug': slug, 'checked': checked, 'items': updated})
            return

        self._send_json(handler, {'error': 'Not found'}, HTTPStatus.NOT_FOUND)

    def render_page(self, kind):
        if kind not in KINDS:
            raise ValueError(f'Unknown page kind: {kind}')
        other_kind = 'movies' if kind == 'shows' else 'shows'
        title = KINDS[kind]['page_title']
        other_title = KINDS[other_kind]['page_title']
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{CSS}</style>
</head>
<body data-kind="{kind}">
  <header>
    <nav>
      <a class="{'active' if kind == 'shows' else ''}" href="/shows">Shows</a>
      <a class="{'active' if kind == 'movies' else ''}" href="/movies">Movies</a>
    </nav>
    <h1>{html.escape(title)}</h1>
    <a class="secondary" href="/{other_kind}">{html.escape(other_title)}</a>
  </header>
  <main>
    <p id="status" role="status">Loading...</p>
    <ul id="media-list" aria-live="polite"></ul>
  </main>
  <script>{JS}</script>
</body>
</html>"""

    def list_items(self, kind):
        metadata = self.fetch_library_metadata(kind)
        checked_slugs = set(normalize_config_slugs(read_config(self.config_path).get(KINDS[kind]['config_key'], [])))
        items = []
        for item in metadata:
            title = item.get('title') or 'Untitled'
            slug = item.get('slug') or create_slug(title)
            art_path = item.get('thumb') or item.get('art') or ''
            items.append({
                'title': title,
                'slug': slug,
                'checked': slug in checked_slugs,
                'artworkUrl': f'/artwork/{kind}/{quote(slug)}' if art_path else '',
            })
        return items

    def fetch_library_metadata(self, kind):
        section_key = self.get_section_key(kind)
        response = self.plex_get(f'/library/sections/{section_key}/all')
        data = response.json()
        return data.get('MediaContainer', {}).get('Metadata', [])

    def get_section_key(self, kind):
        with self._sections_lock:
            if kind in self._section_keys:
                return self._section_keys[kind]

            response = self.plex_get('/library/sections/')
            sections = response.json().get('MediaContainer', {}).get('Directory', [])
            titles = KINDS[kind]['section_titles']
            for section in sections:
                if section.get('title') in titles or section.get('type') == KINDS[kind]['plex_type']:
                    self._section_keys[kind] = section['key']
                    return section['key']
        raise LookupError(f'Could not find Plex {kind} library section')

    def proxy_artwork(self, handler, kind, slug):
        item = next((item for item in self.fetch_library_metadata(kind) if (item.get('slug') or create_slug(item.get('title'))) == slug), None)
        if not item:
            self._send_json(handler, {'error': 'Artwork not found'}, HTTPStatus.NOT_FOUND)
            return

        artwork_path = item.get('thumb') or item.get('art')
        if not artwork_path:
            self._send_json(handler, {'error': 'Artwork not found'}, HTTPStatus.NOT_FOUND)
            return

        response = self.plex_get(artwork_path, stream=True, accept='image/*')
        content_type = response.headers.get('Content-Type', 'application/octet-stream')
        handler.send_response(HTTPStatus.OK)
        handler.send_header('Content-Type', content_type)
        handler.send_header('Cache-Control', 'private, max-age=300')
        handler.end_headers()
        handler.wfile.write(response.content)

    def plex_get(self, path, accept='application/json', **kwargs):
        url = f'{self.plex_base_url}{path}'
        response = self.session.get(
            url,
            params={'X-Plex-Token': self.plex_token},
            headers={'Accept': accept},
            timeout=10,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def _read_json(self, handler):
        length = int(handler.headers.get('Content-Length', '0'))
        if length <= 0:
            return {}
        return json.loads(handler.rfile.read(length).decode('utf-8'))

    def _send_json(self, handler, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode('utf-8')
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Content-Length', str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def _send_html(self, handler, body):
        encoded = body.encode('utf-8')
        handler.send_response(HTTPStatus.OK)
        handler.send_header('Content-Type', 'text/html; charset=utf-8')
        handler.send_header('Content-Length', str(len(encoded)))
        handler.end_headers()
        handler.wfile.write(encoded)

    def _redirect(self, handler, location):
        handler.send_response(HTTPStatus.FOUND)
        handler.send_header('Location', location)
        handler.end_headers()


def read_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as config_file:
        return json.load(config_file)


@contextmanager
def locked_config(lock_path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_lock_path = str(lock_path.resolve())
    with _THREAD_LOCKS_GUARD:
        thread_lock = _THREAD_LOCKS.setdefault(resolved_lock_path, threading.Lock())

    with thread_lock:
        with open(lock_path, 'a', encoding='utf-8') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def update_config_selection(config_path, kind, slug, checked, lock_path=None):
    if kind not in KINDS:
        raise ValueError(f'Invalid kind: {kind}')
    if not slug or create_slug(slug) != slug:
        raise ValueError('slug must be a non-empty normalized slug')

    config_path = Path(config_path)
    lock_path = Path(lock_path) if lock_path else config_path.with_suffix(config_path.suffix + '.lock')
    key = KINDS[kind]['config_key']

    try:
        with locked_config(lock_path):
            config = read_config(config_path)
            current = config.get(key, [])
            if not isinstance(current, list):
                raise ConfigUpdateError(f'{key} must be a list')

            kept = [entry for entry in current if entry_slug(entry) != slug]
            if checked:
                kept.append(slug)
            config[key] = kept
            write_config_atomic(config_path, config)
            return kept
    except OSError as exc:
        raise ConfigUpdateError(str(exc)) from exc


def entry_slug(entry):
    if isinstance(entry, str):
        return create_slug(entry)
    if isinstance(entry, dict):
        if entry.get('slug'):
            return create_slug(str(entry['slug']))
        if entry.get('title'):
            return create_slug(str(entry['title']))
    return None


def write_config_atomic(config_path, config):
    config_path = Path(config_path)
    temp_fd, temp_name = tempfile.mkstemp(
        prefix=f'.{config_path.name}.',
        suffix='.tmp',
        dir=str(config_path.parent),
        text=True,
    )
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as temp_file:
            json.dump(config, temp_file, indent='\t')
            temp_file.write('\n')
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, config_path)
        dir_fd = os.open(config_path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def build_app_from_args(args):
    env_path = Path(args.env_path).expanduser()
    if env_path.exists():
        load_dotenv(env_path)

    plex_ip = os.getenv('plex_ip', '127.0.0.1')
    plex_port = os.getenv('plex_port', '32400')
    plex_base_url = os.getenv('plex_base_url', f'http://{plex_ip}:{plex_port}')
    return ComfortWebApp(
        config_path=Path(args.config_path).expanduser(),
        plex_base_url=plex_base_url,
        plex_token=os.getenv('plex_api_token', ''),
    )


def main():
    parser = argparse.ArgumentParser(description='Comfort Shows and Movies web manager')
    parser.add_argument('--bind', default=os.getenv('COMFORT_WEB_BIND', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.getenv('COMFORT_WEB_PORT', '8088')))
    parser.add_argument('--config-path', default=os.getenv('COMFORT_WEB_CONFIG', 'local_config.json'))
    parser.add_argument('--env-path', default=os.getenv('COMFORT_WEB_ENV', '.env'))
    args = parser.parse_args()

    app = build_app_from_args(args)
    server = ThreadingHTTPServer((args.bind, args.port), app.request_handler())
    print(f'Comfort web manager listening on http://{args.bind}:{args.port}')
    server.serve_forever()


CSS = """
:root {
  color-scheme: light dark;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
body {
  margin: 0;
  background: #f6f7f9;
  color: #202124;
}
header {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.75rem;
  align-items: end;
  padding: 1.25rem clamp(1rem, 3vw, 2rem);
  background: #ffffff;
  border-bottom: 1px solid #dfe3e8;
}
nav {
  grid-column: 1 / -1;
  display: flex;
  gap: 0.5rem;
}
nav a,
.secondary {
  color: #1f5f8b;
  text-decoration: none;
  font-weight: 600;
}
nav a.active {
  color: #111827;
}
h1 {
  margin: 0;
  font-size: clamp(1.6rem, 3vw, 2.4rem);
}
main {
  padding: 1rem clamp(1rem, 3vw, 2rem) 2rem;
}
#status {
  min-height: 1.5rem;
  margin: 0 0 1rem;
}
#status.error {
  color: #9f1239;
}
ul {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
  list-style: none;
  margin: 0;
  padding: 0;
}
li {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 0.75rem;
  align-items: center;
  min-height: 108px;
  padding: 0.65rem;
  background: #ffffff;
  border: 1px solid #dfe3e8;
  border-radius: 8px;
}
img {
  width: 72px;
  height: 96px;
  object-fit: cover;
  border-radius: 4px;
  background: #d1d5db;
}
label {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.65rem;
  align-items: start;
  font-weight: 650;
  line-height: 1.25;
}
input[type="checkbox"] {
  width: 1.25rem;
  height: 1.25rem;
}
@media (prefers-color-scheme: dark) {
  body { background: #111827; color: #f9fafb; }
  header, li { background: #1f2937; border-color: #374151; }
  nav a, .secondary { color: #7dd3fc; }
  nav a.active { color: #ffffff; }
  #status.error { color: #fda4af; }
}
"""


JS = """
const kind = document.body.dataset.kind;
const statusEl = document.querySelector('#status');
const listEl = document.querySelector('#media-list');

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle('error', isError);
}

async function loadItems() {
  try {
    const response = await fetch(`/api/${kind}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Could not load library');
    renderItems(payload.items);
    setStatus(`${payload.items.length} items`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function renderItems(items) {
  listEl.textContent = '';
  for (const item of items) {
    const row = document.createElement('li');
    const img = document.createElement('img');
    img.alt = '';
    if (item.artworkUrl) img.src = item.artworkUrl;

    const label = document.createElement('label');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = item.checked;
    checkbox.addEventListener('change', () => saveSelection(item, checkbox));
    const title = document.createElement('span');
    title.textContent = item.title;

    label.append(checkbox, title);
    row.append(img, label);
    listEl.append(row);
  }
}

async function saveSelection(item, checkbox) {
  const previous = !checkbox.checked;
  checkbox.disabled = true;
  try {
    const response = await fetch(`/api/${kind}/${encodeURIComponent(item.slug)}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({checked: checkbox.checked})
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Could not save selection');
    setStatus(`${item.title} ${checkbox.checked ? 'selected' : 'removed'}`);
  } catch (error) {
    checkbox.checked = previous;
    setStatus(error.message, true);
  } finally {
    checkbox.disabled = false;
  }
}

loadItems();
"""


if __name__ == '__main__':
    main()
