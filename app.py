app = Flask(__name__)

# Function to prompt user for their Spotify API credentials
def get_user_credentials():
    client_id = input("Enter your Spotify Client ID: ")
    client_secret = input("Enter your Spotify Client Secret: ")
    redirect_uri = input("Enter your Redirect URI: ")
    return client_id, client_secret, redirect_uri

# Function to authenticate using the user-provided credentials
def authenticate_spotify(client_id, client_secret, redirect_uri):
    sp_oauth = SpotifyOAuth(client_id=client_id, 
                            client_secret=client_secret, 
                            redirect_uri=redirect_uri, 
                            scope='user-library-read playlist-read-private user-read-currently-playing user-read-playback-state user-modify-playback-state')
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

# Make sure that the first song playing is not the one you are already playing

# Function that adds to queue the most similar song from Master Catalog
def best_next_song(sp, response_cat):
    # Read the master catalog
    MC = Table.read(response_cat, format='csv')
    
    # Get the current playback information
    current_track = sp.current_playback()
    if current_track and 'item' in current_track:
        track_info = current_track['item']
        current_features = sp.audio_features(track_info['id'])[0]  # Get audio features
        
        # Convert the current track features into a NumPy array (excluding None values)
        current_values = np.array([current_features[param] for param in [
            'danceability', 'energy', 'key', 'loudness', 'mode', 'speechiness', 
            'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo'
        ] if current_features[param] is not None])

        # Calculate distances to each song in the master catalog
        distances = []
        for row in MC:
            features = np.array([row[param] for param in [
                'danceability', 'energy', 'key', 'loudness', 'mode', 'speechiness', 
                'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo'
            ] if row[param] is not None])
            
            if len(features) == len(current_values):
                # Calculate Euclidean distance
                distance = np.linalg.norm(current_values - features)
                distances.append((row['Track Name'], distance))
        
        # Find the closest song
        closest_song = min(distances, key=lambda x: x[1])
        song_name = closest_song[0]
        
        # Add to queue
        song_uri = MC[MC['Track Name'] == song_name]['uri'][0]  # Assuming 'uri' is in your catalog
        sp.add_to_queue(song_uri)
        print(f"Added {song_name} to queue.")
        return song_name
    
# Function that makes playlist of artist songs from master catalog and arranges to most similar song 
def artist_cat(sp, response_cat):
    MC = Table.read(response_cat, format='csv')
    current_track = sp.current_playback()
    
    if current_track and 'item' in current_track:
        track_info = current_track['item']
        current_artists = [artist['name'] for artist in track_info['artists']]
        current_features = sp.audio_features(track_info['id'])[0]
        
        # Filter Master Catalog for songs by the current artist
        filtered_catalog = MC[np.isin(MC['Artist(s)'], current_artists)]
        
        # Calculate Euclidean distance for each song
        distances = []
        for row in filtered_catalog:
            features = row['features']  # Adjust based on how features are stored
            distance = np.linalg.norm(np.array(list(current_features.values())) - np.array(list(features.values())))
            distances.append(distance)
        
        # Add distances to the catalog
        filtered_catalog['Distance'] = distances
        
        # Sort by distance
        sorted_catalog = filtered_catalog[np.argsort(filtered_catalog['Distance'])]
        
        # Create a new Spotify playlist
        playlist_name = {track_info['name']} + ' .cat'
        new_playlist = sp.user_playlist_create(user=sp.current_user()['id'], name=playlist_name)
        
        # Add sorted songs to the new playlist
        track_uris = sorted_catalog['uri'].tolist()  # Adjust based on your URI column name
        sp.user_playlist_add_tracks(new_playlist['id'], track_uris)
        
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

# Play the most similar song from the Master Catalog
@app.route('/most_similar_song')
def most_similar_song():
    response = requests.get('https://raw.githubusercontent.com/seamusmcn/seamusmcn.github.io/main/Master_Catalog.csv')

    client_id, client_secret, redirect_uri = get_user_credentials()
    sp = authenticate_spotify(client_id, client_secret, redirect_uri)

    song_name = best_next_song(sp, response.text)

    return f"Added {song_name} to queue!"

if __name__ == '__main__':
    app.run(debug=True)
