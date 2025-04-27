from flask import Flask, request, render_template, session, redirect, jsonify
from flask_cors import CORS
import requests
import spotipy
import json
from uuid import uuid4
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import numpy as np
from astropy.table import Table, vstack, Column
from io import StringIO
import logging
import time
import re
import os
import glob
import sys

"""
List : 5 closest/similar to Song playing
Chain: 5 closest (for loop), 1st closest to one playing, then 2nd closest to queue,... so on. - might have a bunch of repeats

Spectrum: 10 bins of songs in the parameter 

Key playlists: 12 small buttons for each key, 1 for each key.

Document my favorite songs parameters as a scatter plot against the other parameters - look for trends with a specific number of that parameter
BOAT: make a playlist of all the songs within that parameter space - one gaussian distribution around the mean of that parameter space

When creating an artist catalog, retrieve artist listening to, on JS return checkboxes of other associated artists to add to the catalog
+ have a text box to add other artists to the catalog (separate by commas)
+ Also can look in master catalog for covers by other artists of songs by that artist that is being listened to (need to search all songs of artist in master catalog, and then check if there are duplicate names?)

"""


# Initialize Flask app
app = Flask(__name__)
CORS(app, 
     resources={r"/*": {"origins": "https://seamusmcn.github.io"}},
     supports_credentials=True,
     methods=['POST', 'GET'],
     allow_headers=['Content-Type']
)

# grab secret key from my server
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s', 
    stream=sys.stdout  # Ensures logs appear in Render
)

# Temporary in-memory store for state data
state_data_store = {}
user_tokens = {}

def authenticate_spotify(client_id, client_secret, redirect_uri, state):
    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        state=state,
        scope='user-library-read playlist-read-private user-read-currently-playing user-read-playback-state user-modify-playback-state playlist-modify-private playlist-modify-public',
        show_dialog=True
    )
    auth_url = sp_oauth.get_authorize_url()
    return auth_url

def read_csv_with_encoding(response):
    # Decode the response content with 'utf-8' and replace errors
    decoded_content = response.content.decode('utf-8', errors='replace')
    # Use StringIO to create a file-like object from the decoded string
    csv_data = StringIO(decoded_content)
    # Read the CSV into a DataFrame
    df = pd.read_csv(csv_data)
    return df

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

def get_current_playlist(sp):
    current_playback = sp.current_playback()

    if current_playback is None or 'context' not in current_playback or current_playback['context'] is None:
        return None

    # Check if the current context is a playlist
    if 'context' in current_playback and current_playback['context']['type'] == 'playlist':
        # Get the playlist URI
        playlist_uri = current_playback['context']['uri']

        # Extract the playlist ID from the URI (format is spotify:playlist:<playlist_id>)
        playlist_id = playlist_uri.split(':')[-1]

        # Use the playlist ID to get the playlist name (or other details)
        playlist_info = sp.playlist(playlist_id)
        playlist_name = playlist_info['name']
        
        return playlist_name
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
def best_next_songs(sp, MC, n_songs=3):

    # Ensure the columns are sanitized for easier access
    MC.columns = MC.columns.str.strip()

    # Get the current playback information
    current_track = sp.current_playback()
    if current_track and 'item' in current_track:
        track_info = current_track['item']
        current_track_id = track_info['id']  # Get the current track ID
        current_features = sp.audio_features(current_track_id)[0]  # Get audio features

        logging.debug(f"Requesting audio features for track ID: {current_track_id}")

        # Convert the current track features into a NumPy array (excluding None values)
        current_values = np.array([current_features[param] for param in [
            'danceability', 'energy', 'loudness', 'mode', 'speechiness', 
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
                    'Danceability Rating', 'Energy Rating', 'Loudness Rating', 'Mode Rating', 
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

        return closest_songs[0][0] if closest_songs else "No similar song found."
    
with open('artist_associations.json', 'r') as f:
    artist_associations = json.load(f)


# makes a playlist from the master catalog based on artist you are listening to and most similar song.
def artist_cat(sp, MC, artists_to_include):

    # Get current playback information
    current_track = sp.current_playback()
    if not current_track or 'item' not in current_track:
        return "No song currently playing", 400
    
    if current_track and 'item' in current_track:
        track_info = current_track['item']
        current_track_id = track_info['id']  # Get current track ID

        current_artists = [artist['name'] for artist in track_info['artists']]

        # Define playlist name based on the artist
        playlist_name = artists_to_include[0] + ' .cat'
        user_id = sp.current_user()['id']

        # Check if the playlist already exists
        playlists = sp.current_user_playlists()['items']
        existing_playlist = next((pl for pl in playlists if pl['name'] == playlist_name), None)

        if existing_playlist:
            # Delete the existing playlist if it exists
            sp.user_playlist_unfollow(user=user_id, playlist_id=existing_playlist['id'])

        # Filter Master Catalog for songs by the current artist(s)
        filtered_catalog = MC[MC['Artist(s)'].apply(lambda x: any(artist in x for artist in artists_to_include))]

        # Remove the current song from the filtered catalog
        filtered_catalog = filtered_catalog[filtered_catalog['Track ID'] != current_track_id]

        # Create a new Spotify playlist
        new_playlist = sp.user_playlist_create(user=user_id, name=playlist_name)

        ''' Add a caption to the playlist of all the total artists in it '''

        # Get sorted track URIs (excluding current song)
        track_uris = filtered_catalog['Track ID'].tolist()

        # Add the current song URI at the end of the track URIs
        current_track_uri = track_info['uri']
        track_uris.append(current_track_uri)  # Place the current song at the end

        # Spotify only allows 100 tracks at a time, so we need to batch them
        chunk_size = 100
        track_uri_chunks = [track_uris[i:i + chunk_size] for i in range(0, len(track_uris), chunk_size)]

        # Add sorted songs (including the current song at the end) to the new playlist in chunks
        for chunk in track_uri_chunks:
            sp.user_playlist_add_tracks(user=user_id, playlist_id=new_playlist['id'], tracks=chunk)

        # Turn On shuffle because Spotify took away all the audio features
        sp.shuffle(state=True)

        # Play the new playlist
        sp.start_playback(context_uri=new_playlist['uri'])
        print(f"Playing {playlist_name}")

        return playlist_name

# Route to handle Spotify credentials submission
@app.route('/submit_credentials', methods=['POST'])
def submit_credentials():

    # Parse form data
    user_name = request.form.get('user_name')
    logging.debug(f"Received credential submission for user: {user_name}")
    if user_name == os.environ.get('USER_NAME_S'): # Make this so we only have to login a user name, and then it grabs our secret keys/user_id for spotify
        user_abbrev = 'S'
    elif user_name == os.environ.get('USER_NAME_C'):
        user_abbrev = 'C'
    else:
        logging.warning("Unknown user attempted to login.")
        return jsonify({"error": "You're not in my system, bozo"}), 400
    
    client_id = os.environ.get(f'CLIENT_ID_{user_abbrev}')
    client_secret = os.environ.get(f'SPOTIFY_CLIENT_SECRET_{user_abbrev}')

    redirect_uri = 'https://seamusmcn-github-io.onrender.com/callback'  # Deployed URL

    if not client_id or not client_secret:
        logging.error("Missing credentials, submit credentials function")
        return jsonify({"error": "Missing credentials."}), 400

    # Generate a unique state string
    state = str(uuid4())

    # Store client_id associated with this state
    state_data_store[state] = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'user_abbrev': user_abbrev
        # You can add a timestamp here to expire old states
    }

    logging.debug(f"Generated state {state} for user: {user_name}, initializing authentication.")

    try:
        # Use the state parameter in the auth URL
        auth_url = authenticate_spotify(client_id, client_secret, redirect_uri, state)
        return jsonify({"auth_url": auth_url}), 200
    except Exception as e:
        logging.error(f"Error during Spotify authentication: {e}, submit_credentials function")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/callback')
def callback():
    code = request.args.get('code')
    state = request.args.get('state')

    logging.debug(f"Callback received with state: {state}")

    if not state or state not in state_data_store:
        logging.warning("Invalid or missing state parameter, callback function 1")
        return jsonify({"error": "Invalid or missing state parameter."}), 400

    # Retrieve stored data using state
    client_id = state_data_store[state]['client_id']
    redirect_uri = state_data_store[state]['redirect_uri']
    user_abbrev = state_data_store[state]['user_abbrev']

    # Optionally, remove the state from the store
    del state_data_store[state]

    # Retrieve client_secret from environment variables
    client_secret = os.environ.get(f'SPOTIFY_CLIENT_SECRET_{user_abbrev}')
    if not client_secret:
        logging.error("Spotify client_secret not set in environment variables, callback function 2.")
        return jsonify({"error": "Server configuration error."}), 500

    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        state=state,
        scope='user-library-read playlist-read-private user-read-currently-playing user-read-playback-state user-modify-playback-state playlist-modify-private playlist-modify-public'
    )

    if code:
        try:
            token_info = sp_oauth.get_access_token(code, as_dict=True)
            # Generate a unique user identifier
            user_id = str(uuid4())

            # Store the access token associated with this user_id
            user_tokens[user_id] = {
                'access_token': token_info['access_token'],
                'refresh_token': token_info['refresh_token'],
                'expires_at': token_info['expires_at'],
                'user_abbrev': user_abbrev 
            }

            logging.debug(f"Refresh Token: {token_info.get('refresh_token', 'NO REFRESH TOKEN')}")

            logging.debug("Spotify authentication successful, callback.")
            # Log token details to check for missing scopes
            logging.debug(f"Token scopes received: {token_info.get('scope', 'NO SCOPE RETURNED')}")
            
            # Redirect back to the main HTML page with user_id as a query parameter
            redirect_url = f"https://seamusmcn.github.io/templates/Spotify_buttons.html?user_id={user_id}&auth_success=true"
            return redirect(redirect_url)
        except Exception as e:
            logging.error(f"Error obtaining access token: {e}, callback function 3")
            return jsonify({"error": "Failed to obtain access token."}), 500
    else:
        logging.warning("Authorization code not found in callback.")
        return jsonify({"error": "Authorization failed."}), 400

# Function to ensure the token is valid and refresh if necessary
def ensure_token():
    token_info = {
        'access_token': session.get('access_token'),
        'refresh_token': session.get('refresh_token'),
        'expires_at': session.get('token_expires')
    }
    if not token_info['access_token'] or time.time() > token_info['expires_at']:
        sp_oauth = SpotifyOAuth(
            client_id=session.get('client_id'),
            client_secret=session.get('client_secret'),
            redirect_uri=session.get('redirect_uri')
        )
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['access_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']
        session['token_expires'] = token_info['expires_at']
    return token_info['access_token']


@app.route('/most_similar_song', methods=['POST'])
def most_similar_song():
    # Get user_id from the request
    user_id = request.form.get('user_id')
    logging.debug(f"Received request to queue most similar song for user {user_id}")

    if not user_id or user_id not in user_tokens:
        logging.warning(f"Unauthorized request for most_similar_song. User ID: {user_id}")
        return "User not authenticated. Please authenticate first.", 401

    # Retrieve the access token
    token_info = user_tokens[user_id]
    access_token = token_info['access_token']
    user_abbrev = token_info['user_abbrev']

    logging.debug(f"User info: {token_info}")

    # Optionally refresh the token if expired
    if time.time() > token_info['expires_at']:
        logging.debug(f"Refreshing token for user: {user_id}")
        client_id = os.environ.get(f'SPOTIFY_CLIENT_ID_{user_abbrev}')
        client_secret = os.environ.get(f'SPOTIFY_CLIENT_SECRET_{user_abbrev}')
        
        sp_oauth = SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri='https://seamusmcn-github-io.onrender.com/callback')
        
        new_token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        
        # Store the refreshed token properly
        user_tokens[user_id] = {
            'access_token': new_token_info['access_token'],
            'refresh_token': new_token_info['refresh_token'],
            'expires_at': new_token_info['expires_at'],
            'user_abbrev': user_abbrev
        }
        
        access_token = new_token_info['access_token']
        logging.debug(f"New token stored for user: {user_id}")
        logging.debug(f"Using access token: {access_token}")

    # Use the access token to authenticate Spotify requests
    sp = spotipy.Spotify(auth=access_token)

    # Fetch catalog data and find the best next song
    Catalog = request.form.get('Catalog')
    logging.debug(f"Fetching {Catalog} Catalog")

        # Read the master catalog
    if Catalog == 'Liked':
        logging.debug("Using Liked Songs catalog.")
        MC = read_csv_with_encoding(requests.get(f'https://raw.githubusercontent.com/seamusmcn/seamusmcn.github.io/main/{user_abbrev}_playlists/Liked_Songs.csv'))
    elif Catalog == 'Master':
        logging.debug("Using Master catalog.")
        MC = read_csv_with_encoding(requests.get(f'https://raw.githubusercontent.com/seamusmcn/seamusmcn.github.io/main/{user_abbrev}_playlists/Master_Catalog.csv'))
    elif Catalog == 'Current':
        # Get the currently playing playlist
        current_playlist = get_current_playlist(sp)
        
        if current_playlist:
            # Try to fetch the playlist CSV
            try:
                response_current = requests.get(f'https://raw.githubusercontent.com/seamusmcn/seamusmcn.github.io/main/{user_abbrev}_playlists/{current_playlist}.csv')
                if response_current.status_code == 200:
                    MC = read_csv_with_encoding(response_current)
                else:
                    # If the playlist is not documented, use the master catalog
                    MC = read_csv_with_encoding(requests.get(f'https://raw.githubusercontent.com/seamusmcn/seamusmcn.github.io/main/{user_abbrev}_playlists/Master_Catalog.csv'))
                    return "Playlist not documented, Master instead.", 404

            except Exception as e:
                logging.error(f"Error fetching current playlist: {str(e)}, most similar song")
                return f"Error fetching current playlist: {str(e)}", 500
        else:
            return "No playlist found", 404

    song_name = best_next_songs(sp, MC)

    logging.debug(f"Added {song_name} to queue for user {user_id}")

    return f"Added {song_name} to queue."


@app.route('/artist_playlist', methods=['POST'])
def make_artist_playlist():
    try:
        # Get user_id from the request
        user_id = request.form.get('user_id')

        if not user_id or user_id not in user_tokens:
            return "User not authenticated. Please authenticate first.", 401

        # Retrieve the access token
        token_info = user_tokens[user_id]
        access_token = token_info['access_token']
        user_abbrev = token_info['user_abbrev']

        # Optionally refresh the token if expired
        if time.time() > token_info['expires_at']:
            logging.debug(f"Refreshing token for user: {user_id}")
            client_id = os.environ.get(f'SPOTIFY_CLIENT_ID_{user_abbrev}')
            client_secret = os.environ.get(f'SPOTIFY_CLIENT_SECRET_{user_abbrev}')
            
            sp_oauth = SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri='https://seamusmcn-github-io.onrender.com/callback')
            
            new_token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            
            # Store the refreshed token properly
            user_tokens[user_id] = {
                'access_token': new_token_info['access_token'],
                'refresh_token': new_token_info['refresh_token'],
                'expires_at': new_token_info['expires_at'],
                'user_abbrev': user_abbrev
            }
            
            access_token = new_token_info['access_token']
            logging.debug(f"New token stored for user: {user_id}")


        # Use the access token to authenticate Spotify requests
        sp = spotipy.Spotify(auth=access_token)

        response_master = requests.get(f'https://raw.githubusercontent.com/seamusmcn/seamusmcn.github.io/main/{user_abbrev}_playlists/Master_Catalog.csv')
        if response_master.status_code != 200:
            return "Failed to fetch Master Catalog.", 500
        
        MC = read_csv_with_encoding(response_master)
        
        logging.debug("Read master Catalog")

        track = sp.current_playback().get('item', {})
        if not track:
            return "No song playing.", 400
        primary_artist = track['artists'][0]['name']

        include = request.form.getlist('include_artists')
        if include:
            # user made their selection → build & play
            playlist = artist_cat(sp, MC, [primary_artist] + include)
            return f"Now playing {playlist}", 200
        
        assoc = artist_associations.get(primary_artist, [])
        if assoc:
            return jsonify({ 'associated_artists': assoc }), 200
        else:
            # no associates defined → just build immediately
            playlist = artist_cat(sp, MC, [primary_artist])
            return f"Now playing {playlist}", 200
        
    except Exception as e:
        logging.error(f"Error in make_artist_playlist: {e}")
        return "Internal Server Error.", 500

    except Exception as e:
        logging.error(f"Exception Error fetching playback info: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
