# -*- coding: utf-8 -*-
from music import app
from music.authorize import login_required
from flask import request
from flask import jsonify
from flask import session
from flask import render_template
from music.model.cache import Cache
from music.model.transpose import Transpose
from music.model.drive import Drive
from music.model.database import Folder
from music.model.database import File
from music import db


@app.route('/song/transpose', methods=['POST'])
@login_required
def transpose():
    # Get the parameters from the JSON request
    if not 'song' in request.json or not 'key' in request.json:
        return jsonify({'response': 'Failed', 'error': "The 'song' and 'key' must be supplied."})
        
    song = request.json['song']
    key = request.json['key']

    # Transpose the song
    t = Transpose(song, key)
    return jsonify(t.song)


@app.route('/song/<int:song_id>', methods=['GET', 'POST'])
@login_required
def song_by_id(song_id):
    song = Folder.query.get(song_id)
    if request.method != 'POST':
        return render_template('snippet_song.html', song=song)

    song.url = request.json.get('url')
    song.tempo = request.json.get('tempo')
    db.session.commit()
    return jsonify({'response': 'Success'})


@app.route('/monitor', methods=['GET'])
def monitor():
    """
    Expose a URL for the site monitoring that will also refresh the song cache
    from Dropbox every hour.
    """
    # Check if the local cache of the file/folder list is valid
    cache = Cache()
    cache_valid = cache.hcache_valid('fileshash')

    if not cache_valid:
        cache_files_in_database()

    return jsonify({'response': 'Success'})


@app.route('/refresh', methods=['GET'])
@login_required
def refresh():
    """
    Expose an authenticated URL refresh the song cache on demand.
    """
    cache_files_in_database()
    return jsonify({'response': 'Success'})


@app.route('/user/theme', methods=['POST'])
@login_required
def change_theme():
    """
    Store the user's theme as a session variable.
    """
    if 'theme' in request.json:
        session['theme'] = request.json['theme']
    return ''


def cache_files_in_database():
    """
    The folders and files are cached in the database, so that we have a persistent, local store that we can store
    additional metadata against a folder e.g. Youtube link to a song. The folders and files are in two tables with a
    parent-child relationship.

    Since Dropbox does not offer a reliable unique ID for a file, we can only identify the folders and files by name.
    If a folder or file is renamed, then we will lose the metadata stored against it. We will need to handle the
    removal of the old-named records ourselves.
    """
    # Get the current list of files from the Dropbox file store
    store = Drive()
    files = store.files()

    # Update database with the current list of files and folders
    folder = Folder()
    for filename, value in files.iteritems():
        # Check if the folder name exists
        song_folder = folder.query.filter_by(name=filename).first()
        if not song_folder:
            # No: create it
            song_folder = Folder()
            song_folder.name = filename
            db.session.add(song_folder)
            db.session.commit()
        else:
            # Remove all file records that are linked to the folder record
            for f in song_folder.files:
                db.session.delete(f)

        # Create the file records with the updated URLs
        for file_meta in value:
            f = File()
            f.folder_id = song_folder.id
            for field in ['name', 'path', 'extension', 'size', 'mime_type', 'url']:
                setattr(f, field, file_meta[field])
            db.session.add(f)
        db.session.commit()

    # Delete any folder records that no longer exist in Dropbox
    no_longer = Folder.query.filter(~Folder.name.in_(files.keys()))
    for nl in no_longer:
        db.session.delete(nl)

    db.session.commit()

    # Set the cache expiry
    cache = Cache()
    cache.hset_cache_expiry('fileshash')


@app.route('/admin/users', methods=['POST'])
@app.route('/admin/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def admin_user_edit(user_id=None):
    """
    Edit the user permissions.
    """
    if 'admin' not in session['role']:
        abort(403)

    if user_id:
        user = Person.query.get(user_id)
        if request.method == "GET":
            return render_template('snippet_user.html', user=user)
        elif request.method == "PUT":
            # Update the user record
            try:
                user.email = request.form.get('email')
                user.firstname = request.form.get('firstname')
                user.lastname = request.form.get('lastname')
                user.role = request.form.get('role')
                db.session.commit()
                return jsonify({'response': 'Success'})
            except ValueError, v:
                return jsonify({'response': 'Error', 'message': str(v)})
        elif request.method == "DELETE":
            # Delete the user
            try:
                user = Person.query.get(user_id)
                db.session.delete(user)
                db.session.commit()
                return jsonify({'response': 'Success'})
            except Exception, e:
                return jsonify({'response': 'Error', 'message': str(e)})
    elif request.method == "POST":
        # Add a new user record
        try:
            u = Person(request.form.get('email'), request.form.get('firstname'), request.form.get('lastname'))
            u.role = request.form.get('role')
            db.session.add(u)
            result = db.session.commit()
            app.logger.debug(result)
            return jsonify({'response': 'Success'})
        except ValueError, v:
            return jsonify({'response': 'Error', 'message': str(v)})
