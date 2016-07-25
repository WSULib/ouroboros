#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import mimetypes
import json
import uuid
from PIL import Image
import time
import traceback
import sys
import re
from bs4 import BeautifulSoup
import requests
import rdflib
from collections import defaultdict, OrderedDict

# eulfedora
import eulfedora

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_Manager.solrHandles import solr_handle, solr_bookreader_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, helpers, utilities
from WSUDOR_API.functions.packagedFunctions import singleObjectPackage

# localconfig
import localConfig


class WSUDOR_WSUebook_Page(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "WSUebook Page"
	description = "Page Model for the WSUebook"
	Fedora_ContentType = "CM:WSUebookPage"

	def __init__(self, object_type=False, content_type=False, payload=False,orig_payload=False):
		
		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload, orig_payload)

		
	# page order
	@helpers.LazyProperty
	def order(self):
			
		# get ordered, constituent objs
		sparql_response = fedora_handle.risearch.sparql_query('select $pageOrder WHERE {{ <info:fedora/%s> <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageOrder> $pageOrder . }}' % (self.pid))
		return int(sparql_response.next()['pageOrder'])

	# consider width and height?