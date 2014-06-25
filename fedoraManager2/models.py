from fedoraManager2 import db


class jobBlob:
	def __init__(self, job_num):
		self.job_num = job_num
		self.estimated_tasks = ''
		self.assigned_tasks = []
		self.assigned_tasks_count = ''
		self.pending_tasks = []
		self.completed_tasks = []
		self.error_tasks = []

class taskBlob:
	def __init__(self, job_num):
		self.job_num = job_num		
		self.estimated_tasks = ''
		self.last_completed_task_num = 'pending'
		self.completed_tasks = []



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

	def __init__(self, job_num, username, status):
		self.job_num = job_num
		self.username = username
		self.status = status

	def __repr__(self):    	
		return '<Job# {job_num}, username: {username}, status: {status}>'.format(job_num=self.job_num,username=self.username, status=self.status)