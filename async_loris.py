from WSUDOR_Manager import *
from tornado import ioloop, httpclient
import os

# clear cache
os.system('sudo rm -r /var/cache/loris2/* && sudo rm -r /var/cache/ouroboros/fedora_binary_symlinks/* && sudo service varnish restart')

i = 0

def handle_request(response):
    global i
    i -= 1
    if i == 0:
        ioloop.IOLoop.instance().stop()

http_client = httpclient.AsyncHTTPClient()

obj = WSUDOR_ContentTypes.WSUDOR_Object('wayne:emeraldc1910b51099366')
for page in obj.constituents:
    i += 1
    http_client.fetch('http://localhost/loris/fedora:%s|%s/full/full/0/default.jpg' % (page.pid, 'IMAGE'), handle_request, method='GET')

stime = time.time()
ioloop.IOLoop.instance().start()
print "elapsed time: %s" % (float(time.time()) - float(stime))