from fedoraManager2 import db
from datetime import datetime
import sqlalchemy


class user_pids(db.Model):
	id = db.Column(db.Integer, primary_key=True)	
	PID = db.Column(db.String(255)) 
	username = db.Column(db.String(255))	
	# consider making status TINYINT, either 0 or 1
	status = db.Column(db.String(64))
	group_name = db.Column(db.String(255))	

	def __init__(self, PID, username, status, group_name):
		self.PID = PID        
		self.username = username
		self.status = status
		self.group_name = group_name

	def __repr__(self):    	
		return '<PID {PID}, username {username}>'.format(PID=self.PID,username=self.username)


class user_jobs(db.Model):
	# id = db.Column(db.Integer, primary_key=True)
	job_num = db.Column(db.Integer, primary_key=True, unique=True, autoincrement=False)
	username = db.Column(db.String(255))
	# for status, expecting: spooling, pending, running, completed, supressed
	status = db.Column(db.String(255))
	celery_task_id = db.Column(db.String(255))

	def __init__(self, job_num, username, celery_task_id, status):
		self.job_num = job_num
		self.username = username
		self.celery_task_id = celery_task_id
		self.status = status

	def __repr__(self):    	
		return '<Job# {job_num}, username: {username}, celery_task_id: {celery_task_id}, status: {status}>'.format(job_num=self.job_num,username=self.username, celery_task_id=self.celery_task_id, status=self.status)


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
		return '<Job# {job_num}, username: {username}>'.format(job_num=self.job_num,username=self.username)


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
		return '<Name: {name}, Description: {description}>'.format(name=self.name,description=self.description)


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
		return '<Name: {name}>, ID: {id}>'.format(name=self.name, id=self.id)


























