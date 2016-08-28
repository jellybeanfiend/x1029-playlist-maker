from flask import render_template, request, redirect, session, url_for, flash
from app import app
from models import db, User, Song, Playlist
import requests
import base64
from datetime import datetime
import sqlalchemy

SPOTIFY_BASE_URL = 'https://{}.spotify.com'
SPOTIFY_ENDPOINTS = {
    'authorize': ('accounts', '/authorize'),
    'token': ('accounts', '/api/token'),
    'create_playlist': ('api', '/v1/users/{}/playlists'),
    'profile': ('api', '/v1/me'),
    'add_tracks_to_playlist': ('api', '/v1/users/{}/playlists/{}/tracks'),
}


class SpotifyAPIError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return "{} - {}".format(self.value['status'], self.value['message'])


def get_spotify_url(endpoint, *args):
    subdomain, endpoint_url = SPOTIFY_ENDPOINTS[endpoint]
    url = SPOTIFY_BASE_URL.format(subdomain) + endpoint_url
    return url.format(*args)


@app.route("/")
def index():
    signed_in = 'spotify_user_id' in session
    user = None
    if signed_in:
            user = get_user_from_db()
    return render_template("index.html", signed_in=signed_in, user=user)


@app.route("/songs/")
def songs():
    songs = get_songs_from_db()
    return render_template("songlist.html", songs=songs)

@app.route('/aboutme/')
def about_me():
    data = get_spotify_user_data()
    print data['id']
    print session
    print session['spotify_user_id']
    return 'yay'


@app.route("/playlist/create/<playlist_name>")
def create_playlist(playlist_name):
    user = get_user_from_db()
    # Create spotify playlist
    try:
        playlist_id = create_spotify_playlist(playlist_name)
    except SpotifyAPIError as e:
        print e
        # TODO: Handle error gracefully
        return e.message
    # Update db with playlist name and id
    playlist_data = {
        'spotify_id': playlist_id,
        'name': playlist_name,
        'user_id': user.id
    }
    playlist = Playlist(**playlist_data)
    db.session.add(playlist)
    # add all songs to playlist
    songs = get_songs_from_db()
    add_songs_to_playlist(songs, user, playlist)
    playlist.last_updated = datetime.now()
    db.session.commit()
    flash('Your playlist, ' + playlist_name + ', was successfully created!', 'success')
    return render_template('index.html')


#
# Authorization Flow
#


@app.route("/authorize/request/", methods=["POST"])
def request_authorization():
    """ Step 1 - Request authorization from Spotify """

    if 'action' not in request.form:
        return redirect(url_for('index'))

    if request.form['action'] == 'create':
        playlist_name = request.form['playlistName'] or "X1029 Playlist"
        session['playlist_name'] = playlist_name
        session['action'] = 'create'

    if request.form['action'] == 'update':
        session['action'] = 'update'

    payload = {
            'client_id': app.config['CLIENT_ID'],
            'redirect_uri': app.config['REDIRECT_URI'],
            'response_type': 'code',
            'scope': "playlist-modify-public"
    }
    r = requests.get(get_spotify_url('authorize'), params=payload)
    return redirect(r.url)


@app.route("/authorize/response/")
def authorization_response():
    """ Step 2 - Spotify redirects here after the user authorizes access."""
    error = request.args.get('error')
    if error:
            print "Error! {}".format(error)
            return error
    code = request.args.get('code')
    set_access_and_refresh_tokens(code)
    # Get user id and check if it's in the db
    add_user()
    playlist_name = session['playlist_name']
    if session['action'] == 'create':
        return redirect(url_for('create_playlist', playlist_name=playlist_name))
    if session['action'] == 'update':
        return redirect(url_for('list_playlists'))
    return redirect(url_for('index'))



def set_access_and_refresh_tokens(code):
    """ Step 3 - Exchange code for access and refresh tokens """
    payload = {
        'grant_type': "authorization_code",
        'code': code,
        'redirect_uri': app.config['REDIRECT_URI']
    }
    response_data = request_access_token(payload)
    session['refresh_token'] = response_data['refresh_token']
    session['access_token'] = response_data['access_token']


def refresh_access_token():
    """ Step 4 - When the access token expires, request a new one with refresh
    token """
    payload = {
            'grant_type': "refresh_token",
            'refresh_token': session['refresh_token']
    }
    response_data = request_access_token(payload)
    session['access_token'] = response_data['access_token']


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


def get_spotify_user_data():
    headers = {'Authorization': "Bearer {}".format(session['access_token'])}
    r = requests.get(get_spotify_url('profile'), headers=headers)
    return r.json()


def add_user():
    user_data = get_spotify_user_data()
    spotify_user_id = user_data['id']
    display_name = user_data['display_name']
    session['spotify_user_id'] = spotify_user_id
    user = get_user_from_db()
    if user is None:
            user = User(spotify_user_id, display_name)
            db.session.add(user)
            db.session.commit()
    return user


def get_user_from_db():
    spotify_user_id = session['spotify_user_id']
    user = db.session.query(User).filter_by(spotify_id=spotify_user_id).first()
    return user


def create_spotify_playlist(playlist_name):
    spotify_user_id = session['spotify_user_id']
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


def get_songs_from_db(from_date=None):
    if from_date is None:
            # get all songs
            songs = db.session.query(Song).filter(Song.is_valid).all()
    else:
            # get songs that were added after last playlist update
            songs = db.session.query(Song).filter(sqlalchemy._and(
                                                  Song.is_valid,
                                                  Song.date_added > from_date
                                                  )).all()
    return songs


def add_songs_to_playlist(tracks, user, playlist):
    # Max of 100 tracks can be added per request
    for i in xrange(0, len(tracks), 100):
        url = get_spotify_url('add_tracks_to_playlist',
                              user.spotify_id,
                              playlist.spotify_id)
        authorization_header = "Bearer {}".format(session['access_token'])
        headers = {'Authorization': authorization_header,
                   'Content-Type': 'application/json'}
        data = {
                'uris': map(lambda x: x.spotify_uri, tracks[i:i+100])
        }
        print data
        r = requests.post(url, json=data, headers=headers)
        print r.text

@app.route('/add-tracks/')
def add_tracks():
    print 'in here'
    tracks = ['spotify:track:3m6KkYKdnbffMpGd9Pm9FP','spotify:track:69uxyAqqPIsUyTO8txoP2M']
    spotify_id = session['spotify_user_id']
    user = User.query.filter_by(spotify_id=spotify_id).first()
    playlist = Playlist.query.filter_by(user_id=user.id).first()
    print playlist.playlist_name
    url = get_spotify_url('add_tracks_to_playlist',
                             spotify_id,
                             playlist.spotify_id)
    authorization_header = "Bearer {}".format(session['access_token'])
    headers = {'Authorization': authorization_header,
               'Content-Type': 'application/json'}
    data = {
            'uris': tracks
    }
    print url
    print data
    r = requests.post(url, json=data, headers=headers)
    print r.status_code
    print r.text
    return "YAY"


def num_songs_added_since_last_updated(last_updated):
    return Song.query.filter(Song.date_added > last_updated).count()

@app.route('/test-error/')
def test_error():
    r = requests.get('https://api.spotify.com/v1/tracks/2KrxsD86ARO5beq7Q0Drfqa')
    response = r.json()
    if 'error' in response:
        raise SpotifyAPIError(response['error'])


@app.route('/playlists/')
def list_playlists():
    user = get_user_from_db()
    playlists = user.playlists
    num_songs_to_add = {}
    for playlist in playlists:
        num_songs_to_add[playlist.name] = num_songs_added_since_last_updated(playlist.last_updated)
    return render_template('playlists.html', playlists=playlists, num_songs_to_add=num_songs_to_add)
