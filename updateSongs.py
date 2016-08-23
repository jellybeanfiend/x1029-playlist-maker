import sqlalchemy
import time
import requests
from app import db
from app.models import Song


SPOTIFY_SEARCH_URL = 'https://api.spotify.com/v1/search'
LAST_SONGS_PLAYED_URL = 'http://lsp.x1029.com/api/v1/station/history/'
LSP_PARAMS = {
    'domain': '',
    'format': 'json',
    'is_song': True
}


def get_last_songs_played():
    url = requests.get(LAST_SONGS_PLAYED_URL, params=LSP_PARAMS).url
    while True:
        time.sleep(15)
        request_object = requests.get(url)
        if request_object.status_code != 200:
            break
        parsed_response = parse_X1029_response(request_object.json())
        print parsed_response
        for track in parsed_response['tracks']:
            artist, song = track
            add_song_to_db(artist, song)
        db.session.commit()
        if parsed_response['next_url']:
            url = parsed_response['next_url']
        else:
            break


def add_song_to_db(artist, song):
    song_db_record = Song.query.filter(sqlalchemy.and_(
        Song.name == song,
        Song.artist == artist)).first()
    # Add song to database if it isn't already there
    if song_db_record is None:
        song_uri = get_song_uri(artist, song)
        song_data = {
            'name': song,
            'artist': artist,
            'spotify_uri': song_uri,
            'is_valid': song_uri is not None
        }
        db.session.add(Song(**song_data))


def parse_X1029_response(response):
    result = {'tracks': []}
    try:
        tracks = response['results']
    except KeyError:
        result['tracks'] = []
    else:
        for track in tracks:
            try:
                song = track['title']
                artist = track['artist']
            except KeyError:
                continue
            else:
                result['tracks'].append((artist.lower(), song.lower()))
    try:
        next_url = response['next']
    except KeyError:
        next_url = None
    result['next_url'] = next_url
    return result


def get_song_uri(artist, song):
    params = {
        'q': 'artist:{} track:{}'.format(artist, song),
        'type': 'track',
        'limit': 1
    }
    request_object = requests.get(SPOTIFY_SEARCH_URL, params=params)
    if request_object.status_code != 200:
        return None
    response = request_object.json()
    try:
        return response['tracks']['items'][0]['uri']
    except LookupError:
        return None

get_last_songs_played()
