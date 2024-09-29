
// JAVASCRIPT FILE!!

// document.querySelector('#clickButton').addEventListener('click', alert('Good Job!'));

fetch('https://seamusmcn-github-io.onrender.com/submit_credentials', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData.toString()
})
.then(response => {
    if (!response.ok) {
        // Try to parse error message
        return response.json().then(err => { throw err; });
    }
    return response.json();
})
.then(data => {
    if (data.auth_url) {
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
