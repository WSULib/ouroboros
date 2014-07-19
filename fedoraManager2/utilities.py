# utilities
import datetime
import hashlib

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
