# Ouroboros config
import localConfig

# flask proper
from flask import request, redirect, Response, jsonify, stream_with_context

# WSUDOR_API_app
from WSUDOR_API import WSUDOR_API_app
from WSUDOR_Manager import fedora_handle, redisHandles

from eulfedora.models import DatastreamObject, XmlDatastreamObject

import requests
import json
import uuid
import hashlib
from contextlib import closing
import rdflib

# use piffle for IIIF client
from piffle.iiif import IIIFImageClient


'''
Proxy for Loris allowing for eventual valves and fine-grained control over 
bitstreams returned.

Requires following in localConfig:

	LORIS_API_ENDPOINT = "http://localhost/loris_local/"
	LORIS_STREAM_CHUNK_SIZE = 1024


Requires the following in Apache:

	-- Reverse proxy for /loris to /WSUAPI/lorisProxy --
		# lorisProxy
		ProxyPass /loris http://localhost/WSUAPI/lorisProxy
		ProxyPassReverse /loris http://localhost/WSUAPI/lorisProxy

	-- LORIS WSGI --
		# LORIS-http
		ExpiresActive On
		ExpiresDefault "access plus 5184000 seconds"

		AllowEncodedSlashes On

		SetEnvIf Request_URI ^/loris loris
		CustomLog /var/log/loris-access.log combined env=loris

		WSGIDaemonProcess loris2 user=USERNAME_HERE group=GROUP_CHANGE umask=0002 processes=10 threads=15 maximum-requests=1000
		WSGIScriptAlias /loris_local /opt/loris2/loris2.wsgi
		WSGIProcessGroup loris2

		<Location /loris_local>

			# required for Loris
			Header unset Access-Control-Allow-Origin
			Require all granted

			RewriteCond %{REMOTE_HOST} !^::1$
			RewriteCond %{HTTP_HOST} !=localhost
			RewriteCond %{REMOTE_ADDR} !^(127\.0\.0\.1)$
			RewriteRule ^(.*)$ - [R=403]

		</Location>

'''

###################
# ROUTES
###################

# Loris Info 
@WSUDOR_API_app.route("/%s/lorisProxy/<image_id>/info.json" % (localConfig.WSUDOR_API_PREFIX), methods=['POST', 'GET'])
def loris_info(image_id):

	# instantiate IIIFImageClient
	ic = IIIFImageClient(api_endpoint=localConfig.LORIS_API_ENDPOINT,image_id=image_id)

	# debug url
	info_url = ic.info()
	print "loris info url: %s" % info_url
	r = requests.get(info_url).json()
	return jsonify(r)


# Loris Image API
'''
IIIF Image API
{scheme}://{server}{/prefix}/{identifier}/{region}/{size}/{rotation}/{quality}.{format}
'''
@WSUDOR_API_app.route("/%s/lorisProxy/<image_id>/<region>/<size>/<rotation>/<quality>.<format>" % (localConfig.WSUDOR_API_PREFIX), methods=['POST', 'GET'])
def loris_image(image_id,region,size,rotation,quality,format):
	
	# parse pid and datastream from image_id
	pid = image_id.split("fedora:")[1].split("|")[0]
	ds = image_id.split("fedora:")[1].split("|")[1]

	# instantiate IIIFImageClient
	ic = IIIFImageClient(
		api_endpoint=localConfig.LORIS_API_ENDPOINT,
		image_id=image_id,
		region=region,
		size=size,
		rotation=rotation,
		quality=quality,
		fmt=format
	)

	# run restrictions
	for func in restrictions:
		if "THUMBNAIL" not in ds:
			ic = func(pid,ds,ic)

	# run improvements
	for func in improvements:
		ic = func(pid,ds,ic)
	
	# debug url
	image_url = str(ic)
	print image_url
	r = requests.get(str(ic), stream=True)

	# stream_with_context
	# http://flask.pocoo.org/snippets/118/
	return Response(r.iter_content(chunk_size=localConfig.LORIS_STREAM_CHUNK_SIZE), content_type=r.headers['Content-Type'])


###################
# RESTRICT
###################

'''
where 'ic' is an IIIFImageClient object, passed to, and returned by, the function
CONSIDER MOVING ALL TO A RESTRICT CLASS
'''

def downsizeImage(pid,ds,ic):

	'''
	If collection is flagged for downsizing, downsize downloadable image to target size pixels on long or short side
	see: http://iiif.io/api/image/2.0/#size

	Improvements:
	We should pull target resolution size from colletion object
	Or policy?
	'''

	########################################################################################################################
	# RDF based
	########################################################################################################################

	target_resolution = 700	
	restricted_collections = [
		'wayne:collectionvmc',
		'wayne:collectionUniversityBuildings'
	]

	restricted_status = False
	collections = [ o for s,p,o in fedora_handle.get_object(pid).rels_ext.content if p == rdflib.term.URIRef(u'info:fedora/fedora-system:def/relations-external#isMemberOfCollection') ]
	for c in collections:
		if c.split("info:fedora/")[1] in restricted_collections:
			restricted_status = True
			break

	########################################################################################################################

	if restricted_status:

		downsize = False

		# derive size request
		size_d = ic.dict_opts()['size']

		# full requested
		if size_d['full']:
			downsize = True

		# percent requested
		# retrieve info.json and see if percent would exceed size restrictions
		r = requests.get(ic.info()).json()
		if ((r['width'] * float(size_d['pct']) / 100) >= target_resolution) or ((r['height'] * float(size_d['pct']) / 100) >= target_resolution):
			downsize = True

		# specific size requested
		if size_d['w'] >= target_resolution or size_d['h'] >= target_resolution:
			downsize = True

		# downsize if triggered
		if downsize:
			print "downsizing from %s to !%s,%s for Reuther" % (ic.image_options['size'], target_resolution, target_resolution)
			ic = ic.size(width=target_resolution, height=target_resolution, exact=True)

	return ic


# list of restriction functions to run
restrictions = [
	downsizeImage
]


###################
# IMPROVEMENTS
###################

def checkRotation(pid,ds,ic):

	'''
	Check metadata for known rotational changes
	Note: Breaks Mirador
	'''
	
	# check for rotation relationships
	try:
		rotation_string = fedora_handle.risearch.get_objects('info:fedora/%s/%s' % (pid, ds), 'info:fedora/fedora-system:def/relations-internal#needsRotation').next()
		print "Rotating: %s" % rotation_string
	except StopIteration:
		return ic
	
	# apply to ic
	try:

		rotation_d = ic.dict_opts()['rotation']
		print rotation_d

		# pop '!' for mirrored, allow to mirrors to cancel (see elif)
		if rotation_string.startswith('!') and rotation_d['mirrored'] == False:
			rotation_string = rotation_string[1:]
			mirrored = True
		elif rotation_string.startswith('!') and rotation_d['mirrored'] == True:
			rotation_string = rotation_string[1:]
			mirrored = False
		elif rotation_d['mirrored'] == True:
			mirrored = True
		else:
			mirrored = False

		# adjust rotation_string
		if rotation_string == '':
			rotation_int = 0
		else:
			try:
				rotation_int = int(rotation_string)
			except:
				print "could not glean int from rotation string, defaulting to 0"
				rotation_int = 0

		# adjust final rotation (if > 360)
		adjusted_rotation = rotation_d['degrees'] + rotation_int

		final_rotation = _pareRotation(adjusted_rotation)

		# add degrees of rotation from object metadata and mirrored status
		ic = ic.rotation(final_rotation, mirrored=mirrored) 
		return ic

	except:
		print "problem with rotation, aborting"
		return ic


# list of restriction functions to run
improvements = [
	# checkRotation #breaks Mirado functionality, but might have place for direct downloads
]


###################
# UTILITIES
###################

# returns expected results
def _pareRotation(degs):
	if degs < 360:			
		print "returning %s" % degs		
		return degs
	else:
		return _pareRotation(degs - 360)
