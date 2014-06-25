from bs4 import BeautifulSoup
import requests
import html2text
import nltk
from nltk.corpus import treebank
from nltk.corpus import stopwords
from nltk.collocations import *
from nltk.probability import FreqDist, LidstoneProbDist
from nltk.probability import ConditionalFreqDist as CFD
from nltk.util import tokenwrap, LazyConcatenation
from nltk.model import NgramModel
from nltk.metrics import f_measure, BigramAssocMeasures
from nltk.collocations import BigramCollocationFinder
from nltk.corpus import wordnet
from textblob import TextBlob
import string
import json
from collections import Counter
import shelve
from cPickle import HIGHEST_PROTOCOL
import math
import re




def main(getParams,requestPath):

	def shelvedText():
		class processedTextObj():
			def __init__(self):			
				print "Text Location:",getParams['text_location'][0]
				# GET DOC AND PREPARE TEXT	
				self.rHTML = requests.get(getParams['text_location'][0])
				# convert HTML to plain 
				# self.rText = html2text.html2text(self.rHTML.text) # using A.Schwartz script
				self.rText = nltk.clean_html(self.rHTML.text) # built-in NLTK function				
				####################################
				# ignore unicode and utf-8 characters
				# really designed for clean tokenization, a blunt approach
				self.rText = self.rText.encode('ascii','ignore')
				# remove BOM - http://stackoverflow.com/questions/9228202/tokenizing-unicode-using-nltk				
				####################################				
				# get sentences prior to punctuation removal
				self.sentences = nltk.sent_tokenize(self.rText)
				# remove punctuation
				for punct in string.punctuation:
					self.rText = self.rText.replace(punct," ")				
				# NLTK tokenization
				self.tokens = nltk.word_tokenize(self.rText)
				self.tokens = [w.lower() for w in self.tokens]
				self.text = nltk.Text(self.tokens)
				# TextBlob				
				self.rBlob = TextBlob(self.rText)					
				# remove stopwords
				self.tokens_sans_stopwords = [w for w in self.tokens if not w in stopwords.words('english')]
				# frequencies
				self.freqs_sans_stopwords = nltk.FreqDist(self.tokens_sans_stopwords)
				self.freqs = nltk.FreqDist(self.tokens)
				#unique words (missing counts)
				self.vocab_sans_stopwords = self.freqs_sans_stopwords.keys()
				self.vocab = self.freqs.keys()

		#check if text is shelved
		try:
			filename = "./lib/Projects/textAnalysis/texts/"+getParams['id'][0]+"_shelvedDB"
			with open(filename):
				#if so, retrieve and open
				print "shelved text object found, using..."
				shandle = shelve.open(filename,protocol=HIGHEST_PROTOCOL,writeback=True)
				return shandle
		except IOError:
			#if not, open and create shelved object	
			print 'shelved text object not found, creating...'
			filename = "./lib/Projects/textAnalysis/texts/"+getParams['id'][0]+"_shelvedDB"
			shandle = shelve.open(filename,protocol=HIGHEST_PROTOCOL,writeback=True)
			processedTextObj_temp = processedTextObj()
			processedTextObj_dict = processedTextObj_temp.__dict__
			for key in processedTextObj_dict:
				shandle[key] = processedTextObj_dict[key]
			shandle.sync()	
			return shandle
	
	def formJSON():

		# create JSON from resultsDict
		jsonString = json.dumps(returnDict);	

		response = {}
		response['headers'] = {}
		response['headers']['Access-Control-Allow-Origin'] = '*'
		response['headers']['Access-Control-Allow-Methods'] = 'GET, POST'
		response['headers']['Access-Control-Allow-Headers'] = 'x-prototype-version,x-requested-with'
		response['headers']['Access-Control-Max-Age'] = 2520
		response['headers']["content-type"] = "application/json"
		response['headers']['Connection'] = 'Close'
		response['content'] = '{{"textAnalysis": {jsonString} }}'.format(jsonString=jsonString)	
		return response



	def wordAnalysis(getParams,requestPath,shandle):
		# GET Word
		word = getParams['word'][0]

		#RUN ANALYSIS FOR GIVEN WORD	
		#concordance
		returnDict['concordance'] = concordance(shandle,word)
		#get synonyms
		returnDict['synsets'] = synsets(word)		


	# concordance
	def concordance(shandle,word):

		concReturnDict = {}
		concReturnDict['word'] = word

		concList = []
		width = 50
		lines = 1000

		concObj = nltk.text.ConcordanceIndex(shandle['tokens'])

		half_width = (width - len(word) - 2) // 2
		context = width // 4 # approx number of words of context	

		offsets = concObj.offsets(word)
		if offsets:
			lines = min(lines, len(offsets))
			concList.append("%s matches:" % (len(offsets)))
			for i in offsets:
				if lines <= 0:
					break
				left = (' ' * half_width +
				        ' '.join(concObj._tokens[i-context:i]))
				right = ' '.join(concObj._tokens[i+1:i+context])
				left = left[-half_width:]
				right = right[:half_width]
				
				# wrap the word in highlight HTML? 				
				concList.append( (left+" "+concObj._tokens[i]+" "+right) )

				lines -= 1		
		else:
			print("No matches")

		concReturnDict['conc_list'] = concList

		return concReturnDict

	def synsets(word):
		syns = wordnet.synsets(word)
		synset = [l.name for s in syns for l in s.lemmas]
		return synset

	def fullbookAnalysis(getParams, requestPath, shandle):		

		# RUN INDIVIDUAL ANALYSIS METRICS, PUSH TO resultsDict{}
		# collocations
		returnDict['collocations'] = local_collocations(shandle)
		returnDict['simple_metrics'] = simple_metrics(shandle)

	# collocations
	def local_collocations(shandle, num=20, window_size=2):

		'''
		Print collocations derived from the text, ignoring stopwords.

		:seealso: find_collocations
		:param num: The maximum number of collocations to print.
		:type num: int
		:param window_size: The number of tokens spanned by a collocation (default=2)
		:type window_size: int
		'''

		print("Building collocations list")
		ignored_words = stopwords.words('english')
		finder = BigramCollocationFinder.from_words(shandle['tokens'], window_size)
		finder.apply_freq_filter(2)
		finder.apply_word_filter(lambda w: len(w) < 3 or w.lower() in ignored_words)
		bigram_measures = BigramAssocMeasures()
		collocations = finder.nbest(bigram_measures.likelihood_ratio, num)
		colloc_strings = [w1+' '+w2 for w1, w2 in collocations]
		results = tokenwrap(colloc_strings, separator="; ")
		results = results.encode('utf-8')
		return results

	def simple_metrics(shandle):
		
		simpleBlob = {}

		#total word count
		simpleBlob['totalWordCount'] = len(shandle['tokens'])
		simpleBlob['totalWordCount_sans_stopwords'] = len(shandle['tokens_sans_stopwords'])

		# unique words
		simpleBlob['uniqueWords'] = len(shandle['vocab'])
		simpleBlob['uniqueWords_sans_stopwords'] = len(shandle['vocab_sans_stopwords'])

		# lexical diversity
		simpleBlob['lexicalDiversity'] = float(simpleBlob['totalWordCount']) / float(simpleBlob['uniqueWords'])
		simpleBlob['lexicalDiversity_sans_stopwords'] = float(simpleBlob['totalWordCount']) / float(simpleBlob['uniqueWords_sans_stopwords'])

		# total sentences
		simpleBlob['totalSentences'] = len(shandle['sentences'])

		# sentence metrics
		sentTokens = []
		for sentence in shandle['sentences']:
			sentenceTemp = sentence
			for punct in string.punctuation:
				sentenceTemp = sentenceTemp.replace(punct," ")
			sent_tokens = nltk.word_tokenize(sentenceTemp)
			if len(sent_tokens) > 0:
				sentTokens.append( (len(sent_tokens),sentence) )

		# avg sent length
		simpleBlob['avgSentenceLength'] = sum([l for l,s in sentTokens]) / len(sentTokens)

		# longest and shortest sentences
		sentTokens.sort(reverse=True)
		simpleBlob['longestSentence'] = {}
		simpleBlob['longestSentence']['length'] = sentTokens[0][0]
		simpleBlob['longestSentence']['text'] = sentTokens[0][1]
		simpleBlob['shortestSentence'] = {}
		simpleBlob['shortestSentence']['length'] = sentTokens[-1][0]
		simpleBlob['shortestSentence']['text'] = sentTokens[-1][1]

		#unique words
		simpleBlob['uniqueWordsList'] = []
		freqs_sans_stopwords = nltk.FreqDist(shandle['tokens_sans_stopwords'])		
		freqs_top = freqs_sans_stopwords.keys()[:15]
		for each in freqs_top:
			tempDict = {}
			tempDict['text'] = each
			tempDict['count'] = freqs_sans_stopwords[each]
			simpleBlob['uniqueWordsList'].append(tempDict)


		# frequently occuring, long words l > 5
		# magicRatio = math.log(float(len(shandle['tokens_sans_stopwords'])),2)
		# magicFreqNumber = magicRatio * (magicRatio - 7)
		magicFreqNumber = 7 #temporary for Yellow Wall-Paper
		print "magic number:",magicFreqNumber
		simpleBlob['freqLongWords'] = sorted([w for w in set(shandle['tokens_sans_stopwords']) if len(w) > 5 and freqs_sans_stopwords[w] > magicFreqNumber])		

		return simpleBlob

	# go time.
	##########################################################################################################################
	# global dict used to craete JSON response
	print getParams

	shandle = shelvedText()
	print "shandle keys:",shandle.keys()
	
	returnDict = {}	

	if getParams['type'][0] == 'fullbookAnalysis':		
		response = fullbookAnalysis(getParams,requestPath,shandle)

	if getParams['type'][0] == 'wordAnalysis':
		response = wordAnalysis(getParams,requestPath,shandle)
	
	# GENERATE JSON RESPONSE THAT BUBBLES BACK TO ANALYSIS PAGE	
	response  = formJSON()
	return response



if __name__ == "__main__":
        main(getParams,requestPath)





	''' some fun

	Create normalized list of words from tokenized text
	words = [w.lower() for w in tokens]

	Get Concordance of a given word (where "fat" is imported fullbook_analysis.py):
	http://nltk.org/_modules/nltk/text.html
	fat.text.concordance('window')

	Words used in 'similar' context:
	fat.text.similar('she')

	Common contexts between words:
	fat.text.common_contexts(['she','he'])

	Generate random text from the parts of speech:
	fat.text.generate()

	All unique words:
	sorted(set(fat.text))

	Lexical Diversity:
	len(fat.text) / len(set(fat.text))

		def lexical_diversity(text):
			return len(text) / len(set(text))

	Frequency Distribution Graph:
	fd = nltk.FreqDist(fat.text)
	fd.plot(50, cumulative=True)

	Bigrams:
	nltk.bigrams(fat.text)

	*Collocations
	fat.text.collocations()

		In [3]: fat.text.collocations()
		Building collocations list
		WALL PAPER; YELLOW WALL; want; good deal; said; wall
		paper; never saw; John says; Cousin Henry; several times; stopped
		short; self control; old fashioned; moon shines; bulbous eyes; darling
		outside pattern; nervous weakness; shaded lane; three week


	'''