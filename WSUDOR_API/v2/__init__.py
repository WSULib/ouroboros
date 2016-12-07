import localConfig

API_VERSION = 2
def gen_api_prefix(API_VERSION=API_VERSION):
	return "/%(APP_PREFIX)s/v%(API_VERSION)d" % {'APP_PREFIX':localConfig.WSUDOR_API_PREFIX.lstrip('/'), 'API_VERSION':API_VERSION}

# import umbrella API app
from WSUDOR_API import WSUDOR_API_app

# import local views and handlers
from views import api_blueprint

# register blueprints
WSUDOR_API_app.register_blueprint(api_blueprint, url_prefix=gen_api_prefix())