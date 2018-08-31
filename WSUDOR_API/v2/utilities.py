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


def parseIntSet(nputstr=""):
	selection = set()
	invalid = set()
	# tokens are comma seperated values
	tokens = [x.strip() for x in nputstr.split(',')]
	for i in tokens:
		if len(i) > 0:
			if i[:1] == "<":
				i = "1-%s"%(i[1:])
		try:
			# typically tokens are plain old integers
			selection.add(int(i))
		except:
			# if not, then it might be a range
			try:
				token = [int(k.strip()) for k in i.split('-')]
				if len(token) > 1:
					token.sort()
					# we have items seperated by a dash
					# try to build a valid range
					first = token[0]
					last = token[len(token)-1]
					for x in range(first, last+1):
						selection.add(x)
			except:
				# not an int and not a range...
				invalid.add(i)
	# Report invalid tokens before returning valid selection
	if len(invalid) > 0:
		logging.debug("Invalid set: %s" % str(invalid))
	return selection