// JAVASCRIPT FILE!!

// JAVASCRIPT FILE!!

// Check URL parameters for authentication success
console.log("Current Page URL:", window.location.href);
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

    // Get the selected catalog value from the radio buttons
    const catalogInputs = document.getElementsByName('Catalog');
    let selectedCatalog;
    for (const input of catalogInputs) {
        if (input.checked) {
            selectedCatalog = input.value;
            break;
        }
    }

    // If no catalog is selected, show an error message
    if (!selectedCatalog) {
        document.getElementById('status').innerText = 'Please select a catalog type.';
        return;
    }

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
            'Catalog': selectedCatalog,
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
document.getElementById('artist-cat-button')
  .addEventListener('click', async () => {
    const userId = localStorage.getItem('user_id');
    if (!userId) {
      return document.getElementById('status')
        .innerText = 'Please authenticate first.';
    }

    // clean up any old UI
    const old = document.getElementById('artist-options');
    if (old) old.remove();

    // 1) fetch the list of associated artists
    const res1 = await fetch('https://seamusmcn-github-io.onrender.com/artist_playlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ user_id: userId })
    });
    const data1 = await res1.json();
    const assoc = data1.associated_artists || [];

    // 2) build the UI
    const container = document.createElement('div');
    container.id = 'artist-options';
    container.style = 'border:1px solid #ccc; padding:10px; margin:10px 0;';

    // If json indicates artists, show checkboxes
    if (assoc.length) {
        const title = document.createElement('p');
        title.innerText = 'Include these artists?';
        container.appendChild(title);
  
        assoc.forEach(name => {
          const label = document.createElement('label');
          label.style = 'display:block;';
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.value = name;
          label.appendChild(cb);
          label.appendChild(document.createTextNode(' ' + name));
          container.appendChild(label);
        });
      } else {
        // otherwise add others
        const note = document.createElement('p');
        note.innerText = 'No pre-defined associated artists';
        container.appendChild(note);
      }

    // free-form text box
    const customLabel = document.createElement('label');
    customLabel.style = 'display:block; margin-top:8px;';
    customLabel.innerText = 'Add other artists (comma-separated): ';
    const customInput = document.createElement('input');
    customInput.type = 'text';
    customInput.placeholder = '';
    customInput.style = 'width:100%;';
    customLabel.appendChild(customInput);
    container.appendChild(customLabel);

    // final “Create playlist” button
    const go = document.createElement('button');
    go.innerText = 'Create playlist';
    go.style = 'margin-top:10px;';
    go.onclick = async () => {
      // collect selections
      const picked = Array.from(
        container.querySelectorAll('input[type="checkbox"]:checked')
      ).map(cb => cb.value);

      const extraText = customInput.value
        .split(',')
        .map(s => s.trim())
        .filter(s => s);
      const allExtras = picked.concat(extraText);

      // 3) POST again, with include_artists
      const res2 = await fetch('https://seamusmcn-github-io.onrender.com/artist_playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          user_id: userId,
          // Sends multiple include_artists fields
          // URLSearchParams knows how to encode an array
          'include_artists': allExtras
        })
      });
      const data2 = await res2.json();
      document.getElementById('status').innerText = data2.message;
      container.remove();
    };

    container.appendChild(go);
    document.body.appendChild(container);

    // 3) Insert button, instead of at the very bottom
    const btn = document.getElementById('artist-cat-button');
    btn.insertAdjacentElement('afterend', container);

  });
