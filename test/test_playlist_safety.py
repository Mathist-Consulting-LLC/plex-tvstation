import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import tvstation
from utils import build_genres_set


class PlaylistSafetyTests(unittest.TestCase):
    def test_science_fiction_normalizes_to_sci_fi(self):
        self.assertEqual(build_genres_set([{'tag': 'Science Fiction'}]), {'sci-fi'})

    def test_empty_replacement_preserves_existing_playlist(self):
        session = Mock()
        tvstation.PLEX_GLOBALS = {
            'machine_id': 'machine-id',
            'plex_ip': '127.0.0.1',
            'plex_port': '32400',
            'playlist_name': 'Sci Fi TV Station',
            'playlist_key': '123',
            'playlist_episode_keys': [],
            'max_episodes': 50,
        }

        with patch.object(tvstation, 'log_message') as log_message:
            result = tvstation.replace_playlist_items(session)

        self.assertIsNone(result)
        session.delete.assert_not_called()
        session.post.assert_not_called()
        log_message.assert_called_once_with(
            'No episodes to add to playlist -- existing playlist preserved'
        )


if __name__ == '__main__':
    unittest.main()
