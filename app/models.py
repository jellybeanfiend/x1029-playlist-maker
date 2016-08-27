from app import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(255), unique=True)
    display_name = db.Column(db.String(255))
    playlists = db.relationship('Playlist', backref='user', lazy='dynamic')

    def __init__(self, spotify_id, display_name):
        self.spotify_id = spotify_id
        self.display_name = display_name


class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    last_updated = db.Column(db.DateTime)
    spotify_id = db.Column(db.String(255))
    name = db.Column(db.String(255))

    def __init__(self, user_id, spotify_id, name):
        self.user_id = user_id
        self.spotify_id = spotify_id
        self.name = name


class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_added = db.Column(db.DateTime, default=db.func.now())
    name = db.Column(db.String(255))
    artist = db.Column(db.String(255))
    spotify_uri = db.Column(db.Text)
    is_valid = db.Column(db.Boolean)

    def __init__(self, name, artist, spotify_uri, is_valid):
        self.name = name
        self.artist = artist
        self.spotify_uri = spotify_uri
        self.is_valid = is_valid
