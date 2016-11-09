# Utilities
import requests
import ast
import urllib2
from paste.util.multidict import MultiDict
import json
import re
import hashlib
import xmltodict
from localConfig import *


# takes XML URL as input, returns JSON
def XMLtoJSON(getParams):	

	URL = getParams['url'][0]
	
	r = requests.get(URL, auth=(FEDORA_USER, FEDORA_PASSWORD))			
	xmlString = r.text	
	outputDict = xmltodict.parse(xmlString)
	output = json.dumps(outputDict)
	return output


# These rules all independent, order of
# escaping doesn't matter
escapeRules = {'+': r'\+',
			   '-': r'\-',
			   '&': r'%26',
			   '|': r'\|',
			   '!': r'\!',
			   '(': r'\(',
			   ')': r'\)',
			   '{': r'\{',
			   '}': r'\}',
			   '[': r'\[',
			   ']': r'\]',
			   '^': r'\^',
			   '~': r'\~',			   
			   '?': r'\?',
			   ':': r'\:',			   
			   ';': r'\;',			   
			   ' ': r'+'
			   }

def escapedSeq(term):
	""" Yield the next string based on the
		next character (either this char
		or escaped version """
	for char in term:
		if char in escapeRules.keys():
			yield escapeRules[char]
		else:
			yield char

def escapeSolrArg(term):
	""" Apply escaping to the passed in query terms
		escaping special characters like : , etc"""
	term = term.replace('\\', r'\\')   # escape \ first
	return "".join([nextStr for nextStr in escapedSeq(term)])
