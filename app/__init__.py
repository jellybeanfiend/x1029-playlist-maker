from flask import Flask
from flask_sqlalchemy import SQLAlchemy 
from models import User, Song, Base

app = Flask(__name__)
app.config.from_object('config')
db = SQLAlchemy(app)

from app import views