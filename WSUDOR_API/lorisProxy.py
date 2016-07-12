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
# MODEL
###################


class IIIFImageClient(object):
	'''Simple IIIF Image API client for generating IIIF image urls
	in an object-oriented, pythonic fashion.  Can be extended,
	when custom logic is needed to set the image id.  Provides
	a fluid interface, so that IIIF methods can be chained, e.g.::

		iiif_img.size(width=300).format('png')

	.. Note::

		Methods to set region, rotation, and quality are not yet
		implemented.
	'''

	api_endpoint = None
	image_id = None
	default_format = 'jpg'

	# iiif defaults for each sections
	image_defaults = {
		'region': 'full',  # full image, no cropping
		'size': 'full',    # full size, unscaled
		'rotation': '0',   # no rotation
		'quality': 'default',  # color, gray, bitonal, default
		'format': default_format
	}
	allowed_formats = ['jpg', 'tif', 'png', 'gif', 'jp2', 'pdf', 'webp']

	def __init__(self, api_endpoint=None, image_id=None, region=None,
				 size=None, rotation=None, quality=None, format=None):
		self.image_options = self.image_defaults.copy()
		if api_endpoint is not None:
			self.api_endpoint = api_endpoint
		if image_id is not None:
			self.image_id = image_id
		if region is not None:
			self.image_options['region'] = region
		if size is not None:
			self.image_options['size'] = size
		if rotation is not None:
			self.image_options['rotation'] = rotation
		if quality is not None:
			self.image_options['quality'] = quality
		if format is not None:
			self.image_options['format'] = format

	def get_image_id(self):
		'Image id to be used in contructing urls'
		return self.image_id

	def __unicode__(self):
		info = self.image_options.copy()
		info.update({
			'endpoint': self.api_endpoint.rstrip('/'), # avoid duplicate slashes',
			'id': self.get_image_id(),
		})
		return '%(endpoint)s/%(id)s/%(region)s/%(size)s/%(rotation)s/%(quality)s.%(format)s' % info

	def __str__(self):
		return str(unicode(self))

	def __repr__(self):
		return '<IIIFImageClient %s>' % self.get_image_id()
		# include non-defaults?

	def info(self):
		'JSON info url'
		return '%(endpoint)s/%(id)s/info.json' %  {
			'endpoint': self.api_endpoint.rstrip('/'), # avoid duplicate slashes',
			'id': self.get_image_id(),
		}

	def get_copy(self):
		'Get a clone of the current settings for modification.'
		return self.__class__(self.api_endpoint, self.image_id, **self.image_options)

	# methods to set region, rotation, quality not yet implemented

	def size(self, width=None, height=None, percent=None, exact=False):
		'''Set image size.  May specify any one of width, height, or percent,
		or both width and height, optionally specifying best fit / exact
		scaling.'''
		# width only
		if width is not None and height is None:
			size = '%s,' % (width, )
		# height only
		elif height is not None and width is None:
			size = ',%s' % (height, )
		# percent
		elif percent is not None:
			size = 'pct:%s' % (percent, )
		# both width and height
		elif width is not None and height is not None:
			size = '%s,%s' % (width, height)
			if exact:
				size = '!%s' % size

		img = self.get_copy()
		img.image_options['size'] = size
		return img

	def rotation(self, rotation, mirrored=False):
		img = self.get_copy()
		img.image_options['rotation'] = rotation
		if mirrored:
			img.image_options['rotation'] = '!%s' % img.image_options['rotation']
		return img

	def format(self, image_format):
		'Set output image format'
		if image_format not in self.allowed_formats:
			raise Exception('Image format %s unknown' % image_format)
		img = self.get_copy()
		img.image_options['format'] = image_format
		return img

	# methods to derive API info

	def derive_size(self):
		
		'''
		Return dictionary of parsed size request		
		'''

		# return dictionary
		size_d = {
			'full': False,
			'w': None,
			'h': None,
			'exact': False,
			'pct': False,
		}

		size = self.image_options['size']

		# full?
		if size == 'full':
			size_d['full'] = True
			# return immediately
			return size_d

		# percent?
		if "pct" in size:
			size_d['pct'] = int(size.split(":")[1])
			return size_d

		# exact?
		if size.startswith('!'):
			size_d['exact'] = True
			size = size[1:]

		# split width and height
		w,h = size.split(",")
		if w != '':
			size_d['w'] = int(w)
		if h != '':
			size_d['h'] = int(h)

		return size_d


	def derive_rotation(self):
		'''
		Return dictionary of parsed rotation request
		'''

		rotation_d = {
			'degrees': None,
			'mirrored': False
		}

		rotation = self.image_options['rotation']

		if rotation.startswith('!'):
			rotation_d['mirrored'] = True
			rotation = rotation[1:]

		rotation_d['degrees'] = int(rotation)

		return rotation_d


	def derive_region(self):
		
		'''
		Return dictionary of parsed region request		
		'''

		# return dictionary
		region_d = {
			'full': False,
			'x': None,
			'y': None,
			'w': None,
			'h': None,
			'pct': False
		}

		region = self.image_options['region']

		# full?
		if region == 'full':
			region_d['full'] = True
			# return immediately
			return region_d

		# percent?
		if "pct" in region:
			region_d['pct'] = True
			region = region.split("pct:")[1]

		# split to dictionary
		region_d['x'],region_d['y'],region_d['w'],region_d['h'] = region.split(",")

		return region_d

		
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
		format=format
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

	# options
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

	if restricted_status:

		downsize = False

		# derive size request
		size_d = ic.derive_size()

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
	'''
	
	# check for rotation relationships
	try:
		rotation_string = fedora_handle.risearch.get_objects('info:fedora/%s/%s' % (pid, ds), 'info:fedora/fedora-system:def/relations-internal#needsRotation').next()
		print "Rotating: %s" % rotation_string
	except StopIteration:
		return ic
	
	# apply to ic
	try:

		rotation_d = ic.derive_rotation()
		print rotation_d

		# pop '!' for mirrored, allow to mirrors to cancel (see elif)
		if rotation_string.startswith('!') and rotation_d['mirrored'] == False:
			rotation_string = rotation_string[1:]
			mirrored = True
		elif rotation_string.startswith('!') and rotation_d['mirrored'] == True:
			rotation_string = rotation_string[1:]
			mirrored = False
		if rotation_d['mirrored'] == True:
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
	checkRotation
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











