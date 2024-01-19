from flask import Flask, render_template, request, current_app
from werkzeug.exceptions import BadRequest

from lb_content_resolver.content_resolver import ContentResolver
from lb_content_resolver.subsonic import SubsonicDatabase
from lb_content_resolver.lb_radio import ListenBrainzRadioLocal
import config

STATIC_PATH = "/static"
STATIC_FOLDER = "static"
TEMPLATE_FOLDER = "templates"

app = Flask(__name__,
            static_url_path = STATIC_PATH,
            static_folder = STATIC_FOLDER,
            template_folder = TEMPLATE_FOLDER)
app.config.from_object('config')

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/lb-radio", methods=["POST"])
def lb_radio():

    try:
        prompt = request.form["prompt"]
    except KeyError:
        raise BadRequest("arguments 'prompt' is required.")

    try:
        mode = request.form["mode"]
    except KeyError:
        raise BadRequest("arguments 'mode' is required.")

    db = SubsonicDatabase(current_app.config["DATABASE_FILE"], current_app.config)
    db.open()
    r = ListenBrainzRadioLocal()
    jspf = r.generate(mode, prompt, .8)
    if len(jspf["playlist"]["track"]) == 0:
        db.metadata_sanity_check(include_subsonic=upload_to_subsonic)
        return

    recordings = []
    for recording in jspf["playlist"]["track"]:
        recordings.append({"recording_name": recording["title"],
                           "recording_mbid": recording["identifier"][34:],
                           "release_mbid": "",
                           "release_name": recording["album"],
                           "artist_mbid": recording["extension"]["https://musicbrainz.org/doc/jspf#track"] \
                                                   ["artist_identifiers"][0],
                           "artist_name": recording["creator"]
                          })

    return render_template('lb-radio-table.html', recordings=recordings)
