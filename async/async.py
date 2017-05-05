import treq
from klein import Klein
import time
app = Klein()

@app.route('/', branch=True)
def google(request):
    # d = treq.get('http://localhost/loris_local/dc/dc19ffeaa05903be1a5ed5016631b7fe.jp2/info.json')
    d = treq.get('http://localhost/api/item/wayne:vmc14515/loris/vmc14515_JP2/info.json')
    d.addCallback(treq.content)
    return d


app.run("0.0.0.0", 9876)