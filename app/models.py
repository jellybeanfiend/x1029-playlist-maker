from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
	__tablename__ = 'users'

	id = Column(Integer, primary_key=True)
	user_id = Column(String(255), unique=True)
	display_name = Column(String(255))
	last_updated = Column(DateTime)
	playlist_id = Column(String(255))
	playlist_name = Column(String(255))

	def __init__(self, user_id, display_name):
		self.user_id = user_id
		self.display_name = display_name

class Song(Base):
	__tablename__ = 'songs'

	id = Column(Integer, primary_key=True)
	date_added = Column(DateTime)
	name = Column(String(255))
	artist = Column(String(255))
	spotify_uri = Column(Text)

	def __init__(self, date_added, name, artist, spotify_uri):
		self.date_added = date_added
		self.name = name
		self.artist = artist
		self.spotify_uri = spotify_uri