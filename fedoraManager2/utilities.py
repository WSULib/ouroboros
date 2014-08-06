# utilities
import datetime
import hashlib
import requests
from requests.auth import HTTPBasicAuth
from fedoraManager2.sensitive import *
import json

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


def genUserPin(username):
	# create user pin
	date_obj = datetime.datetime.now()
	hashString = username + str(date_obj.month) + str(date_obj.day) + "WSUDOR"
	user_pin = hashlib.sha256(hashString).hexdigest()
	return user_pin	


def checkPinCreds(pin_package,check_type):
	if check_type == "purge":
		# check PINs are correct for username, and that usernames are not equal
		if pin_package['ap1'] == genUserPin(pin_package['an1']) and pin_package['ap2'] == genUserPin(pin_package['an2']) and pin_package['an1'] != pin_package['an2']:
			return True
		else:
			return False

def returnOAISets():
	query_statement = "select $subject $setSpec $setName from <#ri> where { $subject <http://www.openarchives.org/OAI/2.0/setSpec> $setSpec . $subject <http://www.openarchives.org/OAI/2.0/setName> $setName . }"
	base_URL = "http://localhost/fedora/risearch"
	payload = {
		"lang" : "sparql",
		"query" : query_statement,
		"flush" : "false",
		"type" : "tuples",
		"format" : "JSON"
	}
	r = requests.post(base_URL, auth=HTTPBasicAuth(FEDORA_USER, FEDORA_PASSWORD), data=payload )
	risearch = json.loads(r.text)
	shared_relationships = [ (each['subject'], each['setName']) for each in risearch['results'] ]	
	return shared_relationships

















