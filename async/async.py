import treq
from klein import Klein
import time
app = Klein()

i = 0

def timer(response):
	global i
	i = i + 1
	return "\nrequest: %s" % i

@app.route('/', branch=True)
def async_test(request):
    d = treq.get('http://localhost/api/item/wayne:vmc14515/loris/vmc14515_JP2/info.json')
    d.addCallback(timer)
    return d


app.run("0.0.0.0", 9876)