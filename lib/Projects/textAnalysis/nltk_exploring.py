# coding: utf-8
from textAnalysis import *
rHTML = requests.get('http://silo.lib.wayne.edu/fedora/objects/yellowwallpaper:fullbook/datastreams/HTML_FULL/content')
rText = html2text.html2text(rHTML.text)
for punct in string.punctuation:
	rText = rText.replace(punct," ")
tokens = nltk.word_tokenize(rText)
text = nltk.Text(tokens)
text = nltk.Text(tokens)
text = nltk.Text(tokens)
rBlob = TextBlob(rText)
tokens_sans_stopwords = [w for w in tokens if not w in stopwords.words('english')]
freqs = nltk.FreqDist(tokens_sans_stopwords)
vocab = freqs.keys()
