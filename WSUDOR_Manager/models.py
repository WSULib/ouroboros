from WSUDOR_Manager import db, actions, app
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import CeleryWorker
from flask.ext.login import UserMixin
from datetime import datetime
import sqlalchemy
from json import JSONEncoder
from flask import Response, jsonify
import xmlrpclib
import os
# from itsdangerous import URLSafeTimedSerializer

# session data secret key
####################################
app.secret_key = 'WSUDOR'
####################################


########################################################################
# User Jobs
########################################################################

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

#Login_serializer used to encryt and decrypt the cookie token for the remember
#me option of flask-login
# login_serializer = URLSafeTimedSerializer(app.secret_key)

class User(db.Model, UserMixin):
    
    id = db.Column('id', db.Integer, primary_key=True)
    username = db.Column('username', db.String(64), index=True, unique=True)
    password = db.Column('password', db.String(64), index=True, unique=True)
    role = db.Column('role', db.String(120), nullable=True)
    restrictions = db.Column('restrictions', db.String(120), nullable=True)
    fedoraRole = db.Column('fedoraRole', db.String(120), nullable=True)

    def __init__(self, username, password, role, restrictions, fedoraRole):
        self.username = username
        self.password = password
        self.role = role
        self.restrictions = restrictions
        self.fedoraRole = fedoraRole

    def get_auth_token(self):
        """
        Encode a secure token for cookie
        """
        data = [str(self.id), self.fedoraRole]
        return login_serializer.dumps(data)
 
    @staticmethod
    def get(user):
        """
        Static method to search the database and see if userid exists.  If it 
        does exist then return a User Object.  If not then return None as 
        required by Flask-Login. 
        """
        for user in User.query.session.query(User).filter_by(username=user):
            return user
        return None


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


########################################################################
# DB Classes for ingestWorkspace
########################################################################
class ingest_workspace_job(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True, autoincrement=True)   
    # human readable name for job
    name = db.Column(db.String(255)) 
    # identifier, points to collection
    collection_identifier = db.Column(db.String(255))
    created = db.Column(db.DateTime, default=datetime.now)
    # column for raw ingest metadata
    ingest_metadata = db.Column(db.Text(4294967295))
    # column to hold python code (Classes) for creating bags
    bag_creation_class = db.Column(db.String(4096))
    # file index 
    file_index = db.Column(db.Text(4294967295))

    def __init__(self, name):       
        self.name = name    

    def __repr__(self):     
        return '<Name: %s>, ID: %s>' % (self.name, self.id)

    def _delete(self):
        db.session.delete(self)
        db.session.commit()

    def _commit(self):
        db.session.add(self)
        db.session.commit()


def dump_datetime(value):
    """Deserialize datetime object into string form for JSON processing."""
    if value is None:
        return None
    return [value.strftime("%Y-%m-%d"), value.strftime("%H:%M:%S")]


class ingest_workspace_object(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True, autoincrement=True)
    ingest_id = db.Column(db.Integer)
    created = db.Column(db.DateTime, default=datetime.now)
    # lazy link to job table above
    job_id = db.Column(db.Integer, db.ForeignKey('ingest_workspace_job.id'))
    job = db.relationship('ingest_workspace_job', backref=db.backref('objects', lazy='dynamic'))
    # content fields
    MODS = db.Column(db.Text(4294967295)) 
    objMeta = db.Column(db.Text(4294967295)) 
    bag_binary = db.Column(db.Text(4294967295)) 
    bag_path = db.Column(db.String(4096))
    # derived metadata
    object_title = db.Column(db.String(4096))
    DMDID = db.Column(db.String(4096))
    struct_map = db.Column(db.Text(4294967295))
    pid = db.Column(db.String(255))
    # flags and status
    object_type = db.Column(db.String(255))
    ingested = db.Column(db.String(255))
    repository = db.Column(db.String(255)) # eventually pull from localConfig.REPOSITORIES

    # init with 'job' as ingest_workspace_job instance
    def __init__(self, job, object_title="Unknown", DMDID=None):        
        self.job = job
        self.object_title = object_title
        self.DMDID = DMDID
        self.ingested = False
        self.repository = None      

    def __repr__(self):     
        return '<ID: %s>' % (self.id)

    def serialize(self):
        return {
            'id':self.id,
            'created':dump_datetime(self.created),
            'job':(self.job.name,self.job.id),
            'MODS':self.MODS,
            'objMeta':self.objMeta,
            'object_title':self.object_title,
            'DMDID':self.DMDID,
            'ingested':self.ingested,
            'repository':self.repository,
            'struct_map':self.struct_map
        }

    def _delete(self):
        db.session.delete(self) 
        db.session.commit()     

    def _commit(self):
        db.session.add(self)
        db.session.commit()
    

########################################################################
# objMeta class Object
########################################################################
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


########################################################################
# Solr
########################################################################

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

    




















