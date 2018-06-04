from flask import Flask
import json
import readfiles
app = Flask(__name__)

@app.route("/")
def hello():
    return json.dumps(readfiles.getFile())

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
