from flask import Flask, request, render_template  # Ensure Flask is imported correctly
import requests  # Optional, for making HTTP requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import numpy as np
from astropy.table import Table, vstack, Column
import logging
import time
import re
import os
import glob

app = Flask(__name__)

# Function to authenticate using the user-provided credentials
def authenticate_spotify(client_id, client_secret):
    sp_oauth = SpotifyOAuth(client_id=client_id, 
                            client_secret=client_secret, 
                            redirect_uri='http://localhost:8888/callback', 
                            scope='user-library-read playlist-read-private user-read-currently-playing user-read-playback-state user-modify-playback-state playlist-modify-private playlist-modify-public')
    token_info = sp_oauth.get_access_token(as_dict=True)
    return spotipy.Spotify(auth=token_info['access_token'])

# Function to get the current playing track
def get_current_playing_track(sp):
    current_track = sp.current_playback()
    if current_track and 'item' in current_track:
        track_info = current_track['item']
        return {
            'name': track_info['name'],
            'artists': [artist['name'] for artist in track_info['artists']],
            'album': track_info['album']['name'],
            'uri': track_info['uri'],
            'features': sp.audio_features(track_info['id'])[0]  # Get audio features
        }
    return None

# Add random song from Master Catalog
def add_song_to_queue(sp):
    # add random song from Master_Catalog into the queue
    MC = Table.read('Master_Catalog.csv', format='csv')
    random_song = MC[np.random.randint(0, len(MC))]
    song_uri = random_song['Track ID']
    sp.add_to_queue(song_uri)
    print(f"Added {song_uri} to queue.")

# Function that adds to queue the most similar song from Master Catalog
def best_next_songs(sp, Catalog, response_master, response_liked, n_songs=5):
    # Read the master catalog
    if Catalog in ['Liked','liked','Liked Songs','liked songs', 'Liked Playlist', 'liked playlist']:
        with open(pd.compat.StringIO(response_liked.text), mode='r', encoding='utf-8', errors='replace') as file:
            MC = pd.read_csv(file)
    else:
        with open(pd.compat.StringIO(response_master.text), mode='r', encoding='utf-8', errors='replace') as file:
            MC = pd.read_csv(file)

    # Ensure the columns are sanitized for easier access
    MC.columns = MC.columns.str.strip()

    # Get the current playback information
    current_track = sp.current_playback()
    if current_track and 'item' in current_track:
        track_info = current_track['item']
        current_track_id = track_info['id']  # Get the current track ID
        current_features = sp.audio_features(current_track_id)[0]  # Get audio features

        # Convert the current track features into a NumPy array (excluding None values)
        current_values = np.array([current_features[param] for param in [
            'danceability', 'energy', 'key', 'loudness', 'mode', 'speechiness', 
            'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo'
        ] if current_features[param] is not None])

        # Calculate distances to each song in the master catalog
        distances = []
        for _, row in MC.iterrows():
            # Skip if the song is the same as the currently playing song
            if row['Track ID'] == current_track_id:
                continue

            # Use a try-except block to ensure the correct column names are used
            try:
                features = np.array([row[param] for param in [
                    'Danceability Rating', 'Energy Rating', 'Key Rating', 'Loudness Rating', 'Mode Rating', 
                    'Speechiness Rating', 'Acousticness Rating', 'Instrumentalness Rating', 
                    'Liveness Rating', 'Valence Rating', 'Tempo Rating'
                ] if pd.notna(row[param])])

                if len(features) == len(current_values):
                    # Calculate Euclidean distance
                    distance = np.linalg.norm(current_values - features)
                    distances.append((row['Track Name'], row['Track ID'], distance))
            except KeyError as e:
                print(f"Error with track {row['Track Name']}: {e}")

        # Sort the distances to get the closest songs and select the top n_songs
        closest_songs = sorted(distances, key=lambda x: x[2])[:n_songs]

        # Queue the top n_songs
        for song_name, song_id, _ in closest_songs:
            # Fetch URI using Track ID if 'uri' column is not in the catalog
            if 'uri' in MC.columns:
                song_uri = MC[MC['Track ID'] == song_id]['uri'].values[0]
            else:
                # Fetch song URI from Spotify API using the Track ID
                song_info = sp.track(song_id)
                song_uri = song_info['uri']

            sp.add_to_queue(song_uri)
            print(f"Added {song_name} to queue.")

# makes a playlist from the master catalog based on artist you are listening to and most similar song.
def artist_cat(sp, response_master):
    # Read the master catalog
    with open(pd.compat.StringIO(response_master.text), mode='r', encoding='utf-8', errors='replace') as file:
            MC = pd.read_csv(file)
    # Get current playback information
    current_track = sp.current_playback()
    
    if current_track and 'item' in current_track:
        track_info = current_track['item']
        current_track_id = track_info['id']  # Get current track ID
        current_artists = [artist['name'] for artist in track_info['artists']]
        current_features = sp.audio_features(track_info['id'])[0]  # Get features of current song

        # Filter Master Catalog for songs by the current artist(s)
        filtered_catalog = MC[MC['Artist(s)'].apply(lambda x: any(artist in x for artist in current_artists))]

        # Remove the current song from the filtered catalog
        filtered_catalog = filtered_catalog[filtered_catalog['Track ID'] != current_track_id]

        # Calculate Euclidean distance for each song
        distances = []
        for _, row in filtered_catalog.iterrows():
            features = np.array([row[param] for param in [
                'Danceability Rating', 'Energy Rating', 'Key Rating', 'Loudness Rating', 'Mode Rating', 
                'Speechiness Rating', 'Acousticness Rating', 'Instrumentalness Rating', 
                'Liveness Rating', 'Valence Rating', 'Tempo Rating'
            ] if row[param] is not None])
            
            current_values = np.array([current_features[param] for param in [
                'danceability', 'energy', 'key', 'loudness', 'mode', 'speechiness', 
                'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo'
            ] if current_features[param] is not None])

            if len(features) == len(current_values):
                distance = np.linalg.norm(current_values - features)
                distances.append(distance)

        # Add distances to the filtered catalog
        filtered_catalog['Distance'] = distances

        # Sort the catalog by distance
        sorted_catalog = filtered_catalog.sort_values(by='Distance')

        # Create a new Spotify playlist
        playlist_name = track_info['artists'][0]['name'] + ' .cat'
        new_playlist = sp.user_playlist_create(user=sp.current_user()['id'], name=playlist_name)

        # Get sorted track URIs (excluding current song)
        track_uris = sorted_catalog['Track ID'].tolist()

        # Add the current song URI at the end of the track URIs
        current_track_uri = track_info['uri']
        track_uris.append(current_track_uri)  # Place the current song at the end

        # Spotify only allows 100 tracks at a time, so we need to batch them
        chunk_size = 100
        track_uri_chunks = [track_uris[i:i + chunk_size] for i in range(0, len(track_uris), chunk_size)]

        # Add sorted songs (including the current song at the end) to the new playlist in chunks
        for chunk in track_uri_chunks:
            sp.user_playlist_add_tracks(user=sp.current_user()['id'], playlist_id=new_playlist['id'], tracks=chunk)

        # Play the new playlist
        sp.start_playback(context_uri=new_playlist['uri'])
        print(f"Playlist '{playlist_name}' created and now playing!")

# Route to your homepage
@app.route('/')
def home():
    return "Hello, this is your Flask app!"

# Route to execute your first Python script
@app.route('/pull_text')
def pull_text():
    # Add your script logic here
    # Example: You can pull data from GitHub and then process it.
    response = requests.get('https://raw.githubusercontent.com/seamusmcn/seamusmcn.github.io/main/README.md')
    data = response.text
    return data

# Route to handle Spotify credentials submission
@app.route('/submit_credentials', methods=['POST'])
def submit_credentials():
    client_id = request.form['client_id']
    client_secret = request.form['client_secret']
    redirect_uri = request.form['redirect_uri']

    # Authenticate with Spotify
    sp_oauth = SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
    token_info = sp_oauth.get_access_token()

    # Store access and refresh tokens in the session (or use a database)
    session['access_token'] = token_info['access_token']
    session['refresh_token'] = token_info['refresh_token']
    session['token_expires'] = token_info['expires_at']  # Timestamp when the access token expires

    return "We're in"

def ensure_token():
    token_expires = session.get('token_expires')
    if time.time() > token_expires:
        # Token expired, refresh it
        sp_oauth = SpotifyOAuth(client_id=session.get('client_id'),
                                client_secret=session.get('client_secret'),
                                redirect_uri=session.get('redirect_uri'))
        token_info = sp_oauth.refresh_access_token(session.get('refresh_token'))
        session['access_token'] = token_info['access_token']
        session['token_expires'] = token_info['expires_at']

    return session['access_token']


@app.route('/most_similar_song', methods=['POST'])
def most_similar_song():
    # Ensure the token is valid
    access_token = ensure_token()

    # Use the access token to authenticate Spotify requests
    sp = authenticate_spotify_with_token(access_token)

    # Fetch catalog data and find the best next song
    Catalog = request.form['Catalog']
    response_master = requests.get('https://raw.githubusercontent.com/seamusmcn/seamusmcn.github.io/main/Master_Catalog.csv')
    response_liked = requests.get('https://raw.githubusercontent.com/seamusmcn/seamusmcn.github.io/main/Liked_Songs.csv')

    song_name = best_next_songs(sp, Catalog, response_master, response_liked)

    return

@app.route('/artist_playlist', methods=['POST'])
def make_artist_playlist():
    # Ensure the token is valid
    access_token = ensure_token()

    # Use the access token to authenticate Spotify requests
    sp = authenticate_spotify_with_token(access_token)

    response_master = requests.get('https://raw.githubusercontent.com/seamusmcn/seamusmcn.github.io/main/Master_Catalog.csv')

    artist_cat(sp, response_master)

    return 


if __name__ == '__main__':
    app.run(debug=True)
