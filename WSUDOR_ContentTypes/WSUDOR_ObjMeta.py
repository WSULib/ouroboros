#objMeta class Object
from json import JSONEncoder

'''
SIMPLE EXAMPLE:

{
	"id":"waynev2:BAGTESTtree1",
	"label":"Hoh Rainforest - Trees",
	"policy":"info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted",
	"content_type":"WSUDOR_Image",
	"isRepresentedBy":"TREEWIDE",
	"object_relationships": {
		"http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable":"info:fedora/False",		
		"http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy":"info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted",
		"http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel":"info:fedora/CM:Image"
	},	
	"datastreams":[
		{
			"filename":"tree1.jpg",
			"ds_id":"TREEWIDE",
			"mimetype":"image/jpeg",
			"label":"Hoh Rainforest - wide image",
			"internal_relationships":{}
		}
	]
}

'''


class WSUDOR_ObjMeta:
	# requires JSONEncoder

	def __init__(self, **obj_dict): 
			
		# required attributes
		self.id = "Object ID"
		self.policy = "info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted"
		self.content_type = "ContentTypes"
		self.isRepresentedBy = "Datastream ID that represents object"
		self.object_relationships = []
		self.datastreams = []

		# optional attributes
		self.label = "Object label"

		# if pre-existing objMeta exists, override defaults
		self.__dict__.update(obj_dict)

	
	# function to validate ObjMeta instance as WSUDOR compliant
	def validate(self):
		pass

	def writeToFile(self,destination):
		fhand = open(destination,'w')
		fhand.write(self.toJSON())
		fhand.close()

	def importFromFile(self):
		pass

	def writeToObject(self):
		pass

	def importFromObject(self):
		pass

	#uses JSONEncoder class, exports only attributes
	def toJSON(self):
		return JSONEncoder().encode(self.__dict__)