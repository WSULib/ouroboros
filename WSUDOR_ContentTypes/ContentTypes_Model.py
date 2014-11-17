'''
This file contains dictionaries used notate, in human and machine readable forms, what methods and attributes
different ContentTypes must contain to be valid and interoperable with Ouroboros.
'''

ContentType_Model = {
	# methods - contains all attributes each ContentType must include at minimum
	"attributes":[
		{
			# [CONTENT_TYPE_NAME]_struct_requirements
			"name":"[CONTENT_TYPE_NAME]_struct_requirements",
			"description":"This dictionary contains all datastreams and relationships required for that ContentType.  The amount of relationships is not required here, merely that this attribute exists."
		}
	],
	# methods - contains all methods each ContentType must include at minimum
	"method":[
		{
			"name":"ingestBag",
			"description":"Method for Bag type object to ingest itself"
		},
		{
			"name":"exportBag",
			"description":"Method to export WSUDOR object to BagIt form."
		}
	]
}