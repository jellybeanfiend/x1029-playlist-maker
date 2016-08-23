from app import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), unique=True)
    display_name = db.Column(db.String(255))
    last_updated = db.Column(db.DateTime)
    playlist_id = db.Column(db.String(255))
    playlist_name = db.Column(db.String(255))

    def __init__(self, user_id, display_name):
        self.user_id = user_id
        self.display_name = display_name


class Song(db.Model):
    __tablename__ = 'songs'

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
