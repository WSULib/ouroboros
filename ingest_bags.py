import sys
sys.path.insert(0, '/opt/ouroboros')
from console import *
import os

objDir = "/vagrant/downloads/WSUDOR_object_samples"
for objName in os.listdir(objDir):
    if objName.endswith((".tar", ".gz")):
        try:
            obj = WSUDOR_ContentTypes.WSUDOR_Object(objDir+"/"+objName, object_type="bag")
            obj.ingestBag()
            print "Ingested "+objName
        except Exception as e:
            print str(e)
            continue
        finally:
            pass
            # add in code to remove object folder in /tmp directory
    else:
        pass
