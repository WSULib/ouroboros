from twisted.internet import reactor, defer
from twisted.web import server, resource
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site

# import app
from fedoraManager2 import app

resource = WSGIResource(reactor, reactor.getThreadPool(), app)
site = Site(resource)

if __name__ == '__main__':
	print "Starting fedoraManager2 server..."
	reactor.listenTCP( 5001, site )
	reactor.run()