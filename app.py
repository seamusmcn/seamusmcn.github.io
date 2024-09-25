from flask import Flask
import requests  # Optional, if you plan to pull data from GitHub

app = Flask(__name__)

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

# Route to execute another Python script
# @app.route('/script2')
# def run_script2():
#     return "Script 2 executed successfully!"

if __name__ == '__main__':
    app.run(debug=True)
