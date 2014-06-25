#!/usr/bin/env python
import logging
import os
import re
from StringIO import StringIO
import fetch
import transforms

# getParams from Twisted Server
def imageWork(getParams):       

    #URL for image
    if 'obj' in getParams and "ds" in getParams:    	
        imgURL = "http://127.0.0.1/fedora/objects/"+getParams['obj'][0]+"/datastreams/"+getParams['ds'][0]+"/content"
    else:
        print "No image URL found! Aborting imageServer API call."        
        imgURL = "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDORThumbnails/datastreams/NoPhoto/content"        

    # Fetch a dictionary containing the string buffer representing the image, this is the image binary    
    image_dict = fetch.fetchBuffer(imgURL)         

    # Chain commands together
    for param in getParams:
        if not param:
            continue

        # pull in args, must be present with GET based parameters
        args = getParams[param][0]

        # 1st "command" is instantiated class from transforms.py, consider renaming for clarity
        transformAction = transforms.commands.get(param)
        if not transformAction:
            continue               
        
        image_dict['img_binary'] = transformAction().execute(StringIO(image_dict['img_binary']), args)
        
    
    return image_dict
    

