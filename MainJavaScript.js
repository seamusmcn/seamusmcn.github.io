// JAVASCRIPT FILE!!

// Handle Credentials Form Submission
document.getElementById('spotify-credentials-form').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent the default form submission

    // Collect form data
    const client_id = document.getElementById('client_id').value;

    // Prepare the data to be sent as URL-encoded form data
    const formData = new URLSearchParams();
    formData.append('client_id', client_id);

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
