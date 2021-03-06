from flask import Flask, render_template, redirect, session, url_for, request, flash, current_app

from custom_firebase import firebase

import os
import uuid
import requests
import json
import time
from forms import NewMural, NewArtist, EditMural, EditArtist, ValidateUser
from flask import make_response
from functools import update_wrapper, wraps

firebase_path = os.environ.get('FIREBASE_PATH')

app = Flask(__name__)

# This is a flask specific secret_key, used for encrypting session cookies
app.secret_key = os.environ.get('SECRET_KEY')

firebase = firebase.FirebaseApplication(firebase_path, None)


def sign_in_with_email_and_password(email, password):
    request_ref = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={0}".format(
        os.environ.get('APP_KEY'))
    headers = {"content-type": "application/json; charset=UTF-8"}
    data = json.dumps({"email": email, "password": password, "returnSecureToken": True})
    request_object = requests.post(request_ref, headers=headers, data=data)
    current_user = request_object.json()
    try:
        session["auth"] = current_user["idToken"]

        # Say it will expire in expiresIn seconds - 5 minutes
        # session["auth_expiration"] = time.time() + 10
        session["auth_expiration"] = time.time() + int(current_user["expiresIn"]) - 60 * 5

        return redirect("/get_all_murals")
    except KeyError:
        flash("Invalid Login")
        return redirect("/login", code=302)


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'auth' in session and 'auth_expiration' in session:
            auth = session['auth']
            auth_expiration = session['auth_expiration']

            # If the auth token is not expired, then you're still "logged in"
            if auth and auth_expiration and time.time() <= auth_expiration:
                firebase.authentication = auth
                result = f(*args, **kwargs)
                firebase.authentication = None
                return result

        return redirect('/login')

    return decorated


def requires_ssl(fn):
    @wraps(fn)
    def decorated_view(*args, **kwargs):
        if not app.debug:
            if request.is_secure:
                return fn(*args, **kwargs)
            else:
                return redirect(request.url.replace("http://", "https://"))

        return fn(*args, **kwargs)

    return decorated_view


def nocache(f):
    def new_func(*args, **kwargs):
        resp = make_response(f(*args, **kwargs))
        resp.cache_control.no_cache = True
        return resp

    return update_wrapper(new_func, f)


@app.route('/put', methods=['GET', 'POST'])
@requires_auth
@requires_ssl
def new_mural():
    new_mural_form = NewMural()
    artists = firebase.get('/', 'artists')
    sorted_artists = []
    for a in artists:
        sorted_artists.append((artists[a]["uuid"], artists[a]["name"]))
        sorted_artists = sorted(sorted_artists, key=lambda x: x[1])
        new_mural_form.artist.choices = sorted_artists
    if new_mural_form.validate_on_submit():
        uuid_token = uuid.uuid4()

        # the new mural's index = 1 + the number of existing murals
        murals = firebase.get('/', 'murals')
        index = 1 + len(murals)

        put_data = {'Photo': new_mural_form.photo.data, 'Lat': new_mural_form.lat.data,
                    'Long': new_mural_form.longitude.data, 'Artist': new_mural_form.artist.data,
                    'Title': new_mural_form.title.data, 'Month': new_mural_form.month.data,
                    'Year': new_mural_form.year.data, 'Description': new_mural_form.description.data,
                    'Medium': new_mural_form.medium.data, 'uuid': str(uuid_token),
                    'Index': index}
        firebase.put('/murals', uuid_token, put_data)
        return redirect(url_for('all_murals'), code=302)
    return render_template('new_mural.html', form=new_mural_form)


@app.route('/edit', methods=['GET', 'POST'])
@requires_auth
@requires_ssl
def edit_mural():
    edit_form = EditMural()
    mural_id = str(request.args["muralid"])
    murals = firebase.get('/', 'murals')
    mural = murals[mural_id]
    artists = firebase.get('/', 'artists')
    sorted_artists = []
    for a in artists:
        sorted_artists.append((artists[a]["uuid"], artists[a]["name"]))
    sorted_artists = sorted(sorted_artists, key=lambda x: x[1])
    edit_form.artist.choices = sorted_artists
    if edit_form.validate_on_submit():
        put_data = {'Photo': edit_form.photo.data, 'Lat': edit_form.lat.data,
                   'Long': edit_form.longitude.data, 'Artist': edit_form.artist.data,
                   'Title': edit_form.title.data, 'Month': edit_form.month.data,
                   'Year': edit_form.year.data, 'Description': edit_form.description.data,
                   'Medium': edit_form.medium.data, 'uuid': str(mural_id),
                   'Index': mural["Index"]}
        firebase.delete('/murals', str(mural_id))
        firebase.put('/murals', mural_id, put_data)
        return redirect(url_for('all_murals'), code=302)
    return render_template('edit_mural.html', form=edit_form, mural=mural, murals=murals, muralid=mural_id)


@app.route('/login', methods=['GET', 'POST'])
@requires_ssl
def validate():
    val_form = ValidateUser()
    if val_form.validate_on_submit():
        return sign_in_with_email_and_password(val_form.email.data, val_form.password.data)
    return render_template('login.html', form=val_form)


@app.route('/new_artist', methods=['GET', 'POST'])
@requires_auth
@requires_ssl
def artist_put():
    new_art_form = NewArtist()
    if new_art_form.validate_on_submit():
        uuid_token = uuid.uuid4()
        put_data = {'name': new_art_form.name.data,
                    'city': new_art_form.city.data,
                    'bio': new_art_form.bio.data,
                    'link': new_art_form.link.data,
                    'uuid': str(uuid_token)}
        firebase.put('/artists', uuid_token, put_data)
        return redirect(url_for('all_artists'), code=302)
    return render_template('new_artist.html', form=new_art_form)


@app.route('/', methods=['GET', 'POST'])
@app.route('/get_all_murals', methods=['GET', 'POST'])
@requires_auth
@requires_ssl
@nocache
def all_murals():
    artists = firebase.get('/', 'artists')
    murals = firebase.get('/', 'murals')

    sorted_keys = sorted(murals, key=lambda mural: murals[mural]["Index"])
    sorted_murals = []
    for m in sorted_keys:
        sorted_murals.append(murals[m])

    return render_template('disp_all_murals.html', artists=artists, murals=sorted_murals)


@app.route('/delete_mural', methods=['GET', 'POST'])
@requires_auth
@requires_ssl
def delete_mural():
    # reindex all the murals
    murals = firebase.get('/', 'murals')
    key = str(request.form["muralid"])
    removed_index = murals[key]["Index"]

    # if a mural's index is > removed_index, decrement the index
    for m in murals:
        if murals[m]["Index"] > removed_index:
            murals[m]["Index"] -= 1

    # remove the mural
    if key in murals: del murals[key]

    # update firebase
    firebase.delete('/murals', key)
    for id in murals:
        firebase.put('/murals', id, murals[id])

    return redirect(url_for('all_murals'), code=302)


@app.route('/change_mural_index', methods=['POST'])
@requires_auth
@requires_ssl
def change_mural_index():
    mural_id = str(request.form["muralid"])
    up_or_down = str(request.form["upOrDown"])
    murals = firebase.get('/', 'murals')

    # from_mural is the mural corresponding to the muralid
    # to_mural is the mural with the Index that from_mural's Index should be changed to
    from_mural = None
    to_mural = None

    for m in murals:
        if m == mural_id:
            from_mural = murals[m]

    # If the muralID turns out to not be valid
    if from_mural is None:
        return redirect(url_for('all_murals'), code=302)

    from_mural_index = from_mural["Index"]

    to_mural_index = 0
    if up_or_down == "UP":
        to_mural_index = from_mural_index - 1
    elif up_or_down == "DOWN":
        to_mural_index = from_mural_index + 1

    for m in murals:
        if murals[m]["Index"] == to_mural_index:
            to_mural = murals[m]

    # Handles when you want to move to an invalid index
    if to_mural is None:
        return redirect(url_for('all_murals'), code=302)

    from_mural["Index"] = to_mural_index
    to_mural["Index"] = from_mural_index

    # update firebase
    firebase.put('/murals', from_mural["uuid"], from_mural)
    firebase.put('/murals', to_mural["uuid"], to_mural)

    return redirect(url_for('all_murals'), code=302)


@app.route('/all_artists', methods=['GET', 'POST'])
@requires_auth
@nocache
@requires_ssl
def all_artists():
    artists = firebase.get('/', 'artists')
    return render_template('disp_all_artists.html', artists=artists)


@app.route('/edit_artist', methods=['GET', 'POST'])
@requires_auth
@requires_ssl
def edit_artist():
    form = EditArtist()
    artist_id = str(request.args["artists"])
    artists = firebase.get('/', 'artists')
    artist = artists[artist_id]
    if form.validate_on_submit():
        put_data = {'name': form.name.data,
                    'city': form.city.data,
                    'bio': form.bio.data,
                    'link': form.link.data,
                    'uuid': str(artist_id)}
        firebase.delete('/artists', str(artist_id))
        firebase.put('/artists', artist_id, put_data)
        return redirect(url_for('all_artists'), code=302)
    return render_template('edit_artist.html', form=form, artist=artist)


@app.route('/delete_artist', methods=['GET', 'POST'])
@requires_auth
@requires_ssl
def delete_artist():
    artist = str(request.form["artistid"])

    # Don't delete an artist if they have any murals
    murals = firebase.get('/', 'murals')
    for key in murals:
        if murals[key]["Artist"] == artist:
            flash("Cannot delete an artist with existing murals!")
            return redirect(url_for('all_artists'), code=302)

    firebase.delete('/artists', artist)
    return redirect(url_for('all_artists'), code=302)


@app.route('/logout', methods=['GET'])
@requires_ssl
def logout():
    session.clear()
    return redirect('/login')


if __name__ == "__main__":
    app.run()
