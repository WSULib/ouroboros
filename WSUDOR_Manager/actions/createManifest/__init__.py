# TASK: CreateManifest - Create Manifest

# handles
from WSUDOR_Manager.forms import createManifestForm
from WSUDOR_Manager import utilities, roles
from flask import Blueprint, render_template, request, jsonify, redirect, session, Response, json
import re
import requests
from WSUDOR_Manager.models import ObjMeta

import localConfig

createManifest = Blueprint('createManifest', __name__, template_folder='templates', static_folder="static")


@createManifest.route('/createManifest')
@utilities.objects_needed
@roles.auth(['admin','metadata','view'])
def index():

    form = createManifestForm()
    return render_template("createManifest.html",form=form)


@createManifest.route('/stagingManifest', methods=['GET', 'POST'])
@roles.auth(['admin','metadata','view'])
def stagingManifest():

    if request.method == 'GET':
        return redirect("/tasks/createManifest", code=302)

    if request.method == 'POST':
        # objMeta initial model
        form_data = {
        'id' : request.form['objID'],
        'label' : request.form['objLabel'],
        'policy' : str(json.loads(request.form['lockDown'])['object']),
        'content_type' : "WSUDOR_"+str(json.loads(request.form['contentModel'])['object']).replace('info:fedora/CM:',''),
        'object_relationships' : [
            json.loads(request.form['isDiscoverable']),
            json.loads(request.form['lockDown']),
            json.loads(request.form['contentModel'])
        ],
        'datastreams' : []
        }

        # extract datastreams
        f = request.form
        counter = 1
        while True:
            temp_dictionary = {}
            flag = True
            for key in f.keys():
                # look for number and append each one that matches current number to a dictionary
                if key.endswith(str(counter)):
                    flag = False
                    # key_temp = re.sub('\_'+str(counter)+'$', '', key)
                    key_temp = key
                    temp_dictionary[key_temp] = f[key]
                    if key.startswith('isRepresentedBy'):
                        form_data['isRepresentedBy'] = temp_dictionary['dsID_'+str(counter)]
                        temp_dictionary.pop(key, None)

            if flag:
                break
            form_data['datastreams'].append(temp_dictionary)

            objMeta = ObjMeta(**form_data)
            session['objMetaManifestData'] = form_data
            objMeta.downloadFile(form_data)
            counter = counter + 1

        return render_template("stagingManifest.html", form_data=form_data)


@createManifest.route('/previewManifest', methods=['GET', 'POST'])
@roles.auth(['admin','metadata','view'])
def previewManifest():
    if request.method == 'POST':
        form_data = session['objMetaManifestData']
        objMeta = ObjMeta(**form_data)
        return objMeta.displayJSONWeb(form_data)


@createManifest.route('/downloadManifest', methods=['GET', 'POST'])
@roles.auth(['admin','metadata','view'])
def downloadManifest():
    if request.method == 'POST':
        form_data = session['objMetaManifestData']
        objMeta = ObjMeta(**form_data)
        return objMeta.downloadFile(form_data)


@createManifest.route('/mimeTypeSearch', methods=['GET', 'POST'])
@roles.auth(['admin','metadata','view'])
def mimeTypeSearch():
    if request.method == 'GET':
        return render_template("mimeTypeSearch.html")
    if request.method == 'POST':
        type = request.form['type']
        response = requests.get("http://%s/WSUAPI?functions%5B%5D=mimetypeDictionary&direction=extension2mime&inputFilter=" % (localConfig.APP_HOST)+type)
        return jsonify(**response.json())
