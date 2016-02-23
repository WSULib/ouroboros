from WSUDOR_Manager import db, actions
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from datetime import datetime
import sqlalchemy
from json import JSONEncoder
from flask import Response, jsonify

class user_pids(db.Model):
	id = db.Column(db.Integer, primary_key=True)	
	PID = db.Column(db.String(255)) 
	username = db.Column(db.String(255))
	status = db.Column(db.Boolean(1))	
	group_name = db.Column(db.String(255))	

	def __init__(self, PID, username, status, group_name):
		self.PID = PID        
		self.username = username
		self.status = status
		self.group_name = group_name

	def __repr__(self):    	
		return '<PID %s, username %s>' % (self.PID, self.username)


class user_jobs(db.Model):
	# id = db.Column(db.Integer, primary_key=True)
	job_num = db.Column(db.Integer, primary_key=True, unique=True, autoincrement=False)
	username = db.Column(db.String(255))
	# for status, expecting: spooling, pending, running, completed, supressed
	status = db.Column(db.String(255))
	celery_task_id = db.Column(db.String(255))
	job_name = db.Column(db.String(255))

	def __init__(self, job_num, username, celery_task_id, status, job_name):
		self.job_num = job_num
		self.username = username
		self.celery_task_id = celery_task_id
		self.status = status
		self.job_name = job_name

	def __repr__(self):
		return '<Job# %s, username: %s, celery_task_id: %s, status: %s>' % (self.job_num, self.username, self.celery_task_id, self.status)


ROLE_USER = 0
ROLE_ADMIN = 1

class User(db.Model):
    id = db.Column('id', db.Integer, primary_key = True)
    username = db.Column('username', db.String(64), index = True, unique = True)
    email = db.Column('email', db.String(120), index = True, unique = True)
    password = db.Column('password', db.String(120))
    role = db.Column('role', db.SmallInteger, default = ROLE_USER)

    def __init__(self , username ,password , email):
        self.username = username
        self.password = password
        self.email = email

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

    def __repr__(self):
        return '<User %r>' % (self.username)


class job_rollback(db.Model):
	job_num = db.Column(db.Integer, primary_key=True, unique=True, autoincrement=False)
	username = db.Column(db.String(255))
	taskname = db.Column(db.String(255))
	rollback_content = db.Column(db.String(10000))
	

	def __init__(self, job_num, username, taskname, rollback_content):
		self.job_num = job_num
		self.username = username
		self.taskname = taskname
		self.rollback_content = rollback_content
		

	def __repr__(self):    	
		return '<Job# %s, username: %s>' % (self.job_num, self.username)


class xsl_transformations(db.Model):
	id = db.Column(db.Integer, primary_key=True, unique=True, autoincrement=True)	
	name = db.Column(db.String(255))
	description = db.Column(db.String(1000))
	xsl_content = db.Column(db.Text(4294967295), nullable=False) #must be Text(4294967295) to work	

	def __init__(self, name, description, xsl_content):		
		self.name = name
		self.description = description
		self.xsl_content = xsl_content
		

	def __repr__(self):    	
		return '<Name: %s, Description: %s>' % (self.name, self.description)


class ingest_MODS(db.Model):
	id = db.Column(db.Integer, primary_key=True, unique=True, autoincrement=True)	
	name = db.Column(db.String(255))
	created = db.Column(db.DateTime, default=datetime.now)
	xsl_transform_key = db.Column(db.Integer) # id of xsl_transform, might come in handy...	
	MODS_content = db.Column(db.Text(4294967295), nullable=False) #must be Text(4294967295) to work	

	def __init__(self, name, xsl_transform_key, MODS_content):		
		self.name = name
		self.xsl_transform_key = xsl_transform_key
		self.MODS_content = MODS_content
		

	def __repr__(self):    	
		return '<Name: %s>, ID: %s>' % (self.name, self.id)


#objMeta class Object
class ObjMeta:
	# requires JSONEncoder

	def __init__(self, **obj_dict): 
			
		# required attributes
		self.id = "Object ID"
		self.policy = "info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted"
		self.content_type = "ContentTypes" #WSUDOR_X, not CM:X
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

	def downloadFile(self,form_data):
		form_data = str(form_data)
		return Response(form_data, mimetype="application/json", headers={"Content-Disposition" : "attachment; filename=objMeta.json"})

	def writeToObject(self):
		pass

	def importFromObject(self):
		pass

		#uses jsonify to set Content-Type headers to application/json
	def displayJSONWeb(self):
		return jsonify(**self.__dict__)

	#uses JSONEncoder class, exports only attributes
	def toJSON(self):
		return JSONEncoder().encode(self.__dict__)


class SolrDoc(object):	

	class SolrFields(object):
		def __init__(self, **fields): 
			self.__dict__.update(fields)

	# init
	def __init__(self,id):
		self.id = id
		self.escaped_id = self.id.replace(":","\:")

		# get stateful, current Solr doc
		query_params = {
			"q":'id:%s' % (self.escaped_id),
			"rows":1
		}
		response = solr_handle.search(**query_params)
		if len(response.documents) > 0:
			self.doc = self.SolrFields(**response.documents[0])
			#store version, remove from doc
			self.version = self.doc._version_ 
			del self.doc._version_
			# finally, set exists to True
			self.exists = True
		else:
			self.doc = self.SolrFields()
			self.doc.id = self.id # automatically set ID as PID
			self.exists = False

	# delete doc in Solr
	def delete(self):
		delete_response = solr_handle.delete_by_key(self.id, commit=False)
		return delete_response


	# update doc to Solr
	def update(self):
		update_response = solr_handle.update([self.doc.__dict__], commit=False)
		return update_response


	def commit(self):
		return solr_handle.commit()


	def asDictionary(self):
		return self.doc.__dict__


class SolrSearchDoc(object):	

	class SolrFields(object):
		def __init__(self, **fields): 
			self.__dict__.update(fields)

	# init
	def __init__(self,id):
		self.id = id
		self.escaped_id = self.id.replace(":","\:")

		# get stateful, current Solr doc
		query_params = {
			"q":'id:%s' % (self.escaped_id),
			"rows":1
		}
		response = solr_handle.search(**query_params)
		if len(response.documents) > 0:
			self.doc = self.SolrFields(**response.documents[0])
			#store version, remove from doc
			self.version = self.doc._version_ 
			del self.doc._version_
			# finally, set exists to True
			self.exists = True
		else:
			self.doc = self.SolrFields()
			self.doc.id = self.id # automatically set ID as PID
			self.exists = False	


	def asDictionary(self):
		return self.doc.__dict__

	





















