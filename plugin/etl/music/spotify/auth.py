import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPES = " ".join([
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-private",
    "playlist-modify-public",
    "user-library-read",
    "user-library-modify",
    "user-read-recently-played",
    "user-top-read",
])


def get_client(retries: int = 3, status_retries: int = 3) -> spotipy.Spotify:
    load_dotenv()
    auth_manager = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=SCOPES,
        cache_path=".cache-portal6",
    )
    return spotipy.Spotify(auth_manager=auth_manager, retries=retries, status_retries=status_retries)
