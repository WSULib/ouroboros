import localConfig

API_VERSION = 1
def gen_api_prefix(API_VERSION=API_VERSION):
	return "/%(APP_PREFIX)s/v%(API_VERSION)d" % {'APP_PREFIX':localConfig.WSUDOR_API_PREFIX.lstrip('/'), 'API_VERSION':API_VERSION}
print "setting api version prefix: %s" % gen_api_prefix()

# import umbrella API app
from WSUDOR_API import WSUDOR_API_app

# import local views and handlers
import bitStream, lorisProxy
import views

# register blueprints
WSUDOR_API_app.register_blueprint(views.views_blueprint, url_prefix=gen_api_prefix())
WSUDOR_API_app.register_blueprint(bitStream.bitStream_blueprint, url_prefix=gen_api_prefix())
WSUDOR_API_app.register_blueprint(lorisProxy.lorisProxy_blueprint, url_prefix=gen_api_prefix())
