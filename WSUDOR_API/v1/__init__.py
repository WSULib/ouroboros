import localConfig

API_VERSION = 1
def gen_api_prefix(API_VERSION=API_VERSION):
	if not localConfig.WSUDOR_API_PREFIX.startswith('/'):
		APP_PREFIX = localConfig.WSUDOR_API_PREFIX.lstrip('/')
	else:
		APP_PREFIX = localConfig.WSUDOR_API_PREFIX
	return "%(APP_PREFIX)s/v%(API_VERSION)d" % {'APP_PREFIX':APP_PREFIX, 'API_VERSION':API_VERSION}