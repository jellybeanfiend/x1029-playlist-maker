from flask import render_template, request, redirect, session
from app import app
from models import db, User, Song
import requests
import base64
from datetime import datetime


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
@app.route("/request-authorization/")
def request_authorization():
    payload = {
            'client_id': app.config['CLIENT_ID'],
            'redirect_uri': app.config['REDIRECT_URI'],
            'response_type': "code",
            'scope': "playlist-modify-public"
    }
    r = requests.get("https://accounts.spotify.com/authorize", params=payload)
    return redirect(r.url)


# Step 2-4 - Spotify redirects here after the user authorizes access
@app.route("/authorization-response/")
def authorization_response():
    error = request.args.get('error')
    if error:
            print "DAMNIT! Error! {}".format(error)
            return error
    code = request.args.get('code')
    response_data = get_access_token(code)
    session['refresh_token'] = response_data['refresh_token']
    session['access_token'] = response_data['access_token']
    # Get user id and check if it's in the db
    user = add_user()
    return render_template('index.html', signed_in=True, user=user)


def get_access_token(code):
    base64encoded = base64.b64encode("{}:{}".format(app.config['CLIENT_ID'], app.config['CLIENT_SECRET']))
    headers = {'Authorization': "Basic " + base64encoded}
    payload = {
            'grant_type': "authorization_code",
            'code': code,
            'redirect_uri': app.config['REDIRECT_URI']
    }
    r = requests.post("https://accounts.spotify.com/api/token", data=payload, headers=headers)
    response_data = r.json()
    print response_data
    return response_data


def get_spotify_user_data():
    headers = {'Authorization': "Bearer {}".format(session['access_token'])}
    url = 'https://api.spotify.com/v1/me'
    r = requests.get(url, headers=headers)
    return r.json()


@app.route("/create-playlist/", methods=['GET', 'POST'])
def create_playlist():
    user = get_user_from_db()
    if request.method == 'POST':
            playlist_name = request.form['playlistName']
            # Create spotify playlist
            playlist_id = create_spotify_playlist(playlist_name)
            print playlist_name
            print playlist_id
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


def refresh_access_token():
    base64encoded = base64.b64encode("{}:{}".format(app.config['CLIENT_ID'], app.config['CLIENT_SECRET']))
    headers = {'Authorization': "Basic " + base64encoded}
    payload = {
            'grant_type': "refresh_token",
            'refresh_token': refresh_token
    }
    r = requests.post("https://accounts.spotify.com/api/token", data=payload, headers=headers)
    response_data = r.json()
    session['access_token'] = response_data['access_token']


def create_spotify_playlist(name):
    user_id = session['user_id']
    headers = {'Authorization': "Bearer {}".format(session['access_token']), 'Content-Type': 'application/json'}
    data = {'name': name}
    r = requests.post('https://api.spotify.com/v1/users/' + user_id + '/playlists', json=data, headers=headers)
    response = r.json()
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
            url = "https://api.spotify.com/v1/users/{}/playlists/{}/tracks".format(user.user_id, user.playlist_id)
            headers = {'Authorization': "Bearer {}".format(session['access_token']), 'Content-Type': 'application/json'}
            data = {
                    'uris': tracks[i:i+100]
            }
            r = requests.post(url, json=data, headers=headers)
            print r.status_code
            print r.content
    return "done"
