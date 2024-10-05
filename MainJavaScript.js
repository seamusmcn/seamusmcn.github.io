// JAVASCRIPT FILE!!

// JAVASCRIPT FILE!!

// Check URL parameters for authentication success
console.log("Checking URL parameters...");
const urlParams = new URLSearchParams(window.location.search);
const authSuccess = urlParams.get('auth_success');
const userId = urlParams.get('user_id');

console.log(`authSuccess: ${authSuccess}, userId: ${userId}`);

if (authSuccess === 'true' && userId) {
    console.log("Authentication was successful.");
    document.getElementById('status').innerText = 'Authentication successful!';
    // Store userId in localStorage for subsequent requests
    localStorage.setItem('user_id', userId);
} else {
    console.log("Authentication was not successful or authSuccess parameter missing.");
}

// Handle Credentials Form Submission
document.getElementById('spotify-credentials-form').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent the default form submission

    // Collect form data
    const user_name = document.getElementById('user_name').value;

    // Prepare the data to be sent as URL-encoded form data
    const formData = new URLSearchParams();
    formData.append('user_name', user_name);

    // Make a POST request to the Flask backend
    fetch('https://seamusmcn-github-io.onrender.com/submit_credentials', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
    })
    .then(response => {
        if (!response.ok) {
            // Attempt to parse error message
            return response.json().then(err => { throw err; });
        }
        return response.json();
    })
    .then(data => {
        if (data.auth_url) {
            // Redirect the user to Spotify's authorization page
            window.location.href = data.auth_url;
        } else if (data.error) {
            document.getElementById('status').innerText = `Error: ${data.error}`;
        } else {
            document.getElementById('status').innerText = 'Unexpected response from server.';
        }
    })
    .catch(error => {
        document.getElementById('status').innerText = `An error occurred: ${error.error || 'Unknown error'}`;
        console.error('Error:', error);
    });
});

// Handle Catalog Form Submission
document.getElementById('catalog-form').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent the default form submission

    // Get the catalog type from the input field
    let catalog = document.getElementById('Catalog').value;

    // Get userId from localStorage
    const userId = localStorage.getItem('user_id');

    if (!userId) {
        document.getElementById('status').innerText = 'Please authenticate first.';
        return;
    }

    // Make an AJAX request to the Flask route
    fetch(`https://seamusmcn-github-io.onrender.com/most_similar_song`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            'Catalog': catalog,
            'user_id': userId
        }).toString(),
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(err => { throw err; });
        }
        return response.text();
    })
    .then(data => {
        // Display the response in the 'status' paragraph
        document.getElementById('status').innerText = data;
    })
    .catch(error => {
        document.getElementById('status').innerText = `An error occurred: ${error}`;
        console.error('Error:', error);
    });
});

// Handle Artist.cat Button Click
document.getElementById('artist-cat-button').addEventListener('click', function() {
    // Get userId from localStorage
    const userId = localStorage.getItem('user_id');

    if (!userId) {
        document.getElementById('status').innerText = 'Please authenticate first.';
        return;
    }

    // Make a POST request to the Flask route
    fetch('https://seamusmcn-github-io.onrender.com/artist_playlist', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            'user_id': userId
        }).toString(),
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(err => { throw err; });
        }
        return response.text();
    })
    .then(data => {
        // Display the response in the 'status' paragraph
        document.getElementById('status').innerText = data;
    })
    .catch(error => {
        document.getElementById('status').innerText = `An error occurred: ${error}`;
        console.error('Error:', error);
    });
});