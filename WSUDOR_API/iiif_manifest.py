# Ouroboros config
import localConfig

# python modules
import json

# flask proper
from flask import render_template, request, session, redirect, make_response, Response

# WSUDOR_API_app
from WSUDOR_API import WSUDOR_API_app
import WSUDOR_ContentTypes
from functions.packagedFunctions import singleObjectPackage
from functions.fedDataSpy import makeSymLink

# manifest-factory
from manifest_factory import factory as iiif_manifest_factory



# SETUP
#########################################################################################################
fac = iiif_manifest_factory.ManifestFactory()
# Where the resources live on the web
fac.set_base_metadata_uri("http:/digital.library.wayne.edu/iiif_manifest")
# Where the resources live on disk
fac.set_base_metadata_dir("/tmp/iiif_manifest")

# Default Image API information
fac.set_base_image_uri("http://digital.library.wayne.edu/loris")
fac.set_iiif_image_info(2.0, 2) # Version, ComplianceLevel

# 'warn' will print warnings, default level
# 'error' will turn off warnings
# 'error_on_warning' will make warnings into errors
fac.set_debug("warn")



# IIIF_MANIFEST MAIN
#########################################################################################################
@WSUDOR_API_app.route("/iiif_manifest/<identifier>", methods=['POST', 'GET'])
def iiif_manifest(identifier):		

	'''
	While using fedora 3.x, we'll be sending the PID as the identifier
	'''

	getParams = {each:request.values.getlist(each) for each in request.values}

	try:
		# fire genManifest
		response = make_response( genManifest(identifier,getParams) )
		response.headers['Access-Control-Allow-Origin'] = '*'
		response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
		response.headers['Access-Control-Allow-Headers'] = 'x-prototype-version,x-requested-with'
		response.headers['Access-Control-Max-Age'] = 2520
		response.headers["Content-Type"] = "application/json"		
		response.headers['X-Powered-By'] = 'ShoppingHorse'
		response.headers['Connection'] = 'Close'
		return response

	except Exception,e:
		print "WSUDOR_API iiif_manifest call unsuccessful.  Error:",str(e)
		return '{{"WSUDOR_APIstatus":"WSUDOR_API iiif_manifest call unsuccessful.","WSUDOR_APIstatus iiif_manifest message":{exceptionErrorString}}}'.format(exceptionErrorString=json.dumps(str(e)))
	


def genManifest(identifier,getParams):

	'''
	Right here, you'll need to procure some information about the object from WSUDOR_Object handle
	'''

	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(identifier)

	# run singleObjectPackage
	getParams['PID'] = [identifier]	# current routes use GET params, using that here
	single_json = json.loads(singleObjectPackage(getParams))
	print "Working on:",single_json['objectSolrDoc']['mods_title_ms'][0]

	# create root mani obj
	manifest = fac.manifest( label=single_json['objectSolrDoc']['mods_title_ms'][0] )
	# manifest.set_metadata({"Date": "Some Date", "Location": "Some Location"})
	manifest.description = single_json['objectSolrDoc']['mods_abstract_ms'][0]
	manifest.viewingDirection = "left-to-right"


	# create image sequence
	if obj_handle.content_type == "WSUDOR_Image":
		
		# start anonymous sequence
		seq = manifest.sequence(label="default sequence")

		# iterate through component parts
		for image in single_json['parts_imageDict']['sorted']:
			
			print image

			# create symlink (CONSIDER USING HTTP RESOLVE IN LORIS)
			symlink = makeSymLink(identifier,image['jp2'])['symlink']
			symlink = symlink.split('/')[-1]

			# Create a canvas with uri slug of page-1, and label of Page 1
			cvs = seq.canvas(ident=symlink, label=image['ds_id'])

			# Create an annotation on the Canvas
			anno = cvs.annotation()

			# Add Image: http://www.example.org/path/to/image/api/p1/full/full/0/native.jpg
			img = anno.image(symlink, iiif=True)

			# OR if you have a IIIF service:
			img.set_hw_from_iiif()

			cvs.height = img.height
			cvs.width = img.width


	return manifest.toString()