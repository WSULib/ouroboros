# These rules all independent, order of
# escaping doesn't matter
'''
Consider skipping "-" dash, as it can be used for 
saying "NOT" in solr query
'''
escapeRules = {'+': r'\+',
			   '-': r'\-',
			   '&': r'\&',
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
			   '*': r'\*',
			   '?': r'\?',
			   ':': r'\:',
			   # '"': r'\"', # skip escaping double quote
			   ';': r'\;',
			   ' ': r'\ '}

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