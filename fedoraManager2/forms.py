from wtforms import Form, BooleanField, StringField, SelectField, TextAreaField, FileField, validators, fields

################################################################################################################
# this is essentially temporary - selection will come from the results of Solr, Fed, Risearch
################################################################################################################

class PIDselection(Form):    
    PID = fields.FieldList(fields.TextField(('PID')), min_entries=3)
    

class solrSearch(Form):
	# native Solr
	q = StringField('query (q)')
	fq = StringField('filter query (fq_')
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


# form for adding RDF triples
class RDF_edit(Form):
	# using params verbatim from Fedora documentation	
	predicate = SelectField('predicate', choices=[('info:fedora/fedora-system:def/relations-external#hasContentModel', 'hasContentModel'),
		('info:fedora/fedora-system:def/relations-external#isMemberOfCollection', 'isMemberOfCollection'),
		('info:fedora/fedora-system:def/relations-external#isMemberOf', 'isMemberOf'),
		('info:fedora/fedora-system:def/relations-external#isPartOf', 'isPartOf'),
		('http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy', 'hasSecurityPolicy'),
		('http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable', 'isDiscoverable'),
		('http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel', 'preferredContentModel')])
	obj = StringField('object')
	raw_xml = TextAreaField('Raw XML')	
	regex_search = StringField('regex search')
	regex_replace = StringField('regex replace')


# form for adding Datastreams
class batchIngestForm(Form):	
	name = StringField('Name of XSL Transformation:')
	description = StringField('Description:')
	content = TextAreaField('Paste Content (usually XML, and trumps file upload)')
	upload = FileField('Upload Content')

		


		
	


		