from flask import render_template, request, redirect, session
from app import app
from models import db, User, Song
import requests
import base64
from datetime import datetime

SPOTIFY_BASE_URL = 'https://{}.spotify.com'

SPOTIFY_ENDPOINTS = {
    'authorize': ('accounts', '/authorize'),
    'token': ('accounts', '/api/token'),
    'create_playlist': ('api', '/v1/users/{}/playlists'),
    'profile': ('api', '/v1/me'),
    'add_tracks_to_playlist': ('api', '/users/{}/playlists/{}/tracks'),
}


class SpotifyAPIError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return "{} - {}".format(self.value['status'], self.value['message'])


def get_spotify_url(endpoint, *args):
    subdomain, endpoint_url = SPOTIFY_ENDPOINTS[endpoint]
    url = SPOTIFY_BASE_URL.format(subdomain) + endpoint_url
    return url.format(args)


@app.route("/")
def index():
    signed_in = 'user_id' in session
    user = None
    if signed_in:
            user = get_user_from_db()
    return render_template("index.html", signed_in=signed_in, user=user)


@app.route("/songs/")
def songs():
    songs = db.session.query(Song).all()
    return render_template("songlist.html", songs=songs)


# Step 1 - Request authorization from Spotify
@app.route("/authorize/request/")
def request_authorization():
    payload = {
            'client_id': app.config['CLIENT_ID'],
            'redirect_uri': app.config['REDIRECT_URI'],
            'response_type': 'code',
            'scope': "playlist-modify-public"
    }
    r = requests.get(get_spotify_url('authorize'), params=payload)
    return redirect(r.url)


# Step 2 - Spotify redirects here after the user authorizes access
@app.route("/authorize/response/")
def authorization_response():
    error = request.args.get('error')
    if error:
            print "Error! {}".format(error)
            return error
    code = request.args.get('code')
    set_access_and_refresh_tokens(code)
    # Get user id and check if it's in the db
    user = add_user()
    return render_template('index.html', signed_in=True, user=user)


def request_access_token(params):
    authorization_header = "{}:{}".format(app.config['CLIENT_ID'],
                                          app.config['CLIENT_SECRET'])
    base64encoded = base64.b64encode(authorization_header)
    headers = {'Authorization': "Basic " + base64encoded}
    r = requests.post(get_spotify_url('token'),
                      data=params,
                      headers=headers)
    response_data = r.json()
    return response_data


# Step 3 - Exchange code for access and refresh tokens
def set_access_and_refresh_tokens(code):
    payload = {
        'grant_type': "authorization_code",
        'code': code,
        'redirect_uri': app.config['REDIRECT_URI']
    }
    response_data = request_access_token(payload)
    session['refresh_token'] = response_data['refresh_token']
    session['access_token'] = response_data['access_token']


# Step 4 - When the access token expires, request a new one with refresh token
def refresh_access_token():
    payload = {
            'grant_type': "refresh_token",
            'refresh_token': session['refresh_token']
    }
    response_data = request_access_token(payload)
    session['access_token'] = response_data['access_token']


def get_spotify_user_data():
    headers = {'Authorization': "Bearer {}".format(session['access_token'])}
    r = requests.get(get_spotify_url('profile'), headers=headers)
    return r.json()


@app.route("/create-playlist/<playlist_name>")
def create_playlist(playlist_name):
    user = get_user_from_db()
    # Create spotify playlist
    return "HI"
    try:
        playlist_id = create_spotify_playlist(playlist_name)
    except SpotifyAPIError as e:
        return e.message
    # Update db with playlist name and id
    user.playlist_name = playlist_name
    user.playlist_id = playlist_id
    # add all songs to playlist
    songs = get_songs_from_db(user)
    add_songs_to_playlist(songs, user)
    user.last_updated = datetime.now()
    db.session.commit()
    return render_template('newplaylist.html', user=user)


def add_user():
    user_data = get_spotify_user_data()
    print user_data
    user_id = user_data['id']
    session['user_id'] = user_id
    display_name = user_data['display_name']
    user = get_user_from_db()
    if user is None:
            user = User(user_id, display_name)
            db.session.add(user)
            db.session.commit()
    return user


def get_user_from_db():
    user_id = session['user_id']
    user = db.session.query(User).filter_by(user_id=user_id).first()
    return user


def create_spotify_playlist(playlist_name):
    spotify_user_id = session['user_id']
    headers = {'Authorization': "Bearer {}".format(session['access_token']),
               'Content-Type': 'application/json'}
    data = {'name': playlist_name}
    r = requests.post(get_spotify_url('create_playlist', spotify_user_id),
                      json=data,
                      headers=headers)
    response = r.json()
    if 'error' in response:
        raise SpotifyAPIError(response['error'])
    return response['id']


def get_songs_from_db(user):
    if user.last_updated is None:
            # get all songs
            songs = db.session.query(Song).all()
    else:
            # get songs that were added after last playlist update
            songs = db.session.query(Song).filter(Song.date_added > user.last_updated)
    valid_spotify_uris = map(lambda x: x.spotify_uri, filter(lambda x: x.spotify_uri != '0', songs))
    return valid_spotify_uris


def add_songs_to_playlist(tracks, user):
    for i in xrange(0, len(tracks), 100):
            url = get_spotify_url('add_tracks_to_playlist',
                                  user.user_id,
                                  user.playlist_id)
            headers = {'Authorization': "Bearer {}".format(session['access_token']), 'Content-Type': 'application/json'}
            data = {
                    'uris': tracks[i:i+100]
            }
            r = requests.post(url, json=data, headers=headers)
            print r.status_code
            print r.content
    return "done"


@app.route('/test-error/')
def test_error():
    r = requests.get('https://api.spotify.com/v1/tracks/2KrxsD86ARO5beq7Q0Drfqa')
    response = r.json()
    if 'error' in response:
        raise SpotifyAPIError(response['error'])



