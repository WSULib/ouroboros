from wtforms import Form, BooleanField, StringField, SelectField, TextAreaField, FileField, validators, fields

from fedoraManager2.sensitive import *
from fedoraManager2 import utilities


'''
FORMS.PY - used throughout fedoraManagere2

Might make sense to keep much logic, imports, or heavy-lifting out of here, keep it focused on defining forms.  
Instead, we can farm that work out to fedoraManager2.utilities
'''


class PIDselection(Form):    
    PID = fields.FieldList(fields.TextField(('PID')), min_entries=3)
    

class solrSearch(Form):
	# native Solr
	q = StringField('query (q)',default="*")
	fq = StringField('filter query (fq)')
	fl = StringField('fields to return (fl)')	

	# Fedora RELS-EXT fields
	collection_object = SelectField('Collection')
	content_model = SelectField('Content Type')	


# form for adding Datastreams
class addDSForm(Form):
	# using params verbatim from Fedora documentation
	dsID = StringField('Datastream ID:')
	altIDs = StringField('Alternate Datastream ID:')		
	dsLabel = StringField('Datastream Label:')
	MIMEType = StringField('MIME-Type:')
	dsLocation = StringField('Location (note: will trump content below):')
	controlGroup = SelectField('Control Group:', choices=[('M', 'Managed Content'), ('X', 'Inline XML'), ('R', 'Redirect'), ('E', 'External Referenced')])	
	content = TextAreaField('Paste Content (usually XML, and trumps file upload)')
	upload = FileField('Upload Content')

# form for purging Datastreams
class purgeDSForm(Form):
	# using params verbatim from Fedora documentation
	dsID = StringField('Datastream ID: ')
	startDT = StringField('Start Date-Time Stamp: ')
	endDT = StringField('Ending Date-Time Stamp: ')
	logMessage = StringField('Log Message: ')
	force = StringField('Force Update: ')

# form for adding RDF triples
class RDF_edit(Form):
	# using params verbatim from Fedora documentation	
	predicate = SelectField('predicate', choices=[('info:fedora/fedora-system:def/relations-external#hasContentModel', 'hasContentModel'),
		#Fedora RELS-EXT
		('info:fedora/fedora-system:def/relations-external#isMemberOfCollection', 'isMemberOfCollection'),
		('info:fedora/fedora-system:def/relations-external#isMemberOf', 'isMemberOf'),
		('info:fedora/fedora-system:def/relations-external#isPartOf', 'isPartOf'),
		#WSUDOR
		('http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy', 'hasSecurityPolicy'),
		('http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable', 'isDiscoverable'),
		('http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel', 'preferredContentModel'),
		('http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isOAIHarvestable', 'isOAIHarvestable')
		])
	predicate_literal = StringField('predicate literal')
	obj = StringField('object')
	raw_xml = TextAreaField('Raw XML')	
	regex_search = StringField('regex search')
	regex_replace = StringField('regex replace')

# form for adding RDF triples
class OAI_sets(Form):
	# using params verbatim from Fedora documentation	
	predicate = StringField('predicate',default="http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet")	
	# obj = SelectField('object', choices=utilities.returnOAISets('dropdown'))
	# obj = SelectField('object')
	obj_PID = StringField('Collection PID (e.g. wayne:collectionLincolnLetters)')
	setSpec = StringField('Set ID (setSpec)')
	setName = StringField('Set Name (setName)')
	

# form for adding Datastreams
class batchIngestForm(Form):	
	name = StringField('Name of XSL Transformation:')
	description = StringField('Description:')
	content = TextAreaField('Paste Content (usually XML, and trumps file upload)')
	upload = FileField('Upload Content')

		


		
	


		