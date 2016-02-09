from flask_sqlalchemy import SQLAlchemy 
from models import User, Song, Base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy import and_
from datetime import datetime
from bs4 import BeautifulSoup
import time
import requests

BASE_X1029_URL = 'http://www.x1029.com/lsp/'
engine = create_engine('sqlite:////tmp/1029playlist.db')
Session = sessionmaker(bind=engine)
session = Session()

def crawl_last_played(url):
	songs = set()
	date = datetime.now()
	while True:
		time.sleep(15)
		result = requests.get(url)
		if result.status_code != 200:
			print "UH OH -  status code was not 200"
			print result
			break
		html_soup = BeautifulSoup(result.content)
		songs = find_songs_on_page(html_soup)
		for artist, song in songs:
			result = session.query(Song).filter(and_(Song.name == song, Song.artist == artist)).first()
			if result is None:
				song_uri = search_song(artist, song)
				session.add(Song(name=song, artist=artist, spotify_uri=song_uri, date_added=date))
		session.commit()
		prevlink = html_soup.find("div", {"class":"cmPrevious"})
		if prevlink:
			url = BASE_X1029_URL + prevlink.a['href']
		else:
			break
	return songs

def find_songs_on_page(html_soup):
	songs = set()
	song_divs = html_soup.find_all("div", {"class": 'cmPlaylistContent'})
	for song_div in song_divs:
		links = song_div.find_all("a")
		song = links[0].string
		artist = links[1].string
		songs.add((artist, song))
	return songs

def search_song(artist, song):
	params = {
		'q': 'artist:{} track:{}'.format(artist, song),
		'type': 'track',
		'limit': 1
	}
	url = 'https://api.spotify.com/v1/search'
	r = requests.get(url, params=params)
	response = r.json()
	try:
		return response['tracks']['items'][0]['uri']
	except LookupError:
		return False

crawl_last_played(BASE_X1029_URL)

# print session.query(Song).filter(Song.spotify_uri == 0).all()