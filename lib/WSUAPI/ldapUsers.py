# LDAP Query Interpreter
import json
import ldap
import requests
from utils import *

def authUser(getParams):
	# if no Lib / validUser cookie, password is important
	# return username and display name in JSON nugget

	# tightening up - I think THIS needs to make a WSUDOR account check and retrieve the clientHash
	# OR make it on the fly right here and return it.

	try:

		username=getParams['username'][0]
		password=getParams['password'][0]

		returnDict = {}

		###############################################################
		# get clientHash# 
		try:
			userDict = {}
			baseURL = "http://localhost/solr4/users/select?"
			
			solrParams = {}
			solrParams['q'] = 'id:'+username
			solrParams["wt"] = "python"
			# add all other parameters	
			for k in solrParams:		
				baseURL += (k+"="+str(solrParams[k])+"&")	

			# make Solr Request, save to userDict
			r = requests.get(baseURL)				
			userDict = ast.literal_eval(r.text)
			print "\n\n\n"
			print "Results of clientHash retrieval from LDAP authorization:"
			print userDict['response']['docs'][0]['user_hash'][0]			
			print "\n\n\n"
			retrieved_clientHash = userDict['response']['docs'][0]['user_hash'][0]
			returnDict['clientHash'] = retrieved_clientHash
		except:
			print "Could not retrieve user hash"
		###############################################################

		# set ldap location, protocol version, and referrals
		l = ldap.initialize("ldaps://directory.wayne.edu:636")
		l.protocol_version = ldap.VERSION3
		l.set_option(ldap.OPT_REFERRALS, 0)

		submitted_username = username
		username = "uid="+submitted_username+",ou=People,DC=wayne,DC=edu"
		password = password
		if password == "":
			jsonString = '{"desc":"no password"}'
			return jsonString
		else:	
			try:
				l.bind_s(username, password)
			except ldap.LDAPError, e:
				jsonString = json.dumps(e.message)
				return jsonString

		# set baseDN, scope (SUBTREE searches searches for user and children), attributes
		baseDN = "dc=wayne,dc=edu"
		searchScope = ldap.SCOPE_SUBTREE
		retrieveAttributes = ['firstDotLast','givenName','uid']
		searchFilter = "uid="+submitted_username

		try:
			ldap_result_id = l.search(baseDN, searchScope, searchFilter, retrieveAttributes)
			result_set = list()
			result_type, result_data = l.result(ldap_result_id)
			for data in result_data:
				if data[0]:
					result_set.append(data)
			# jsonString = json.dumps(result_set)
			################################################
			# Couching in dictionary
			returnDict['LDAP_result_set'] = result_set
			print returnDict
			jsonString = json.dumps(returnDict)
			################################################
			return jsonString
		except ldap.LDAPError, e:
			jsonString = json.dumps(e.message)
			return jsonString


	except:
		jsonString = '{"desc":"something super borked"}'
		return jsonString

def getUserInfo(getParams):
	# Lib / validUser cookie present, just need their name
	# anonymous call
	try:

		username=getParams['username'][0]
		password=""


		# set ldap location, protocol version, and referrals
		l = ldap.initialize("ldap://directory.wayne.edu:389")
		l.protocol_version = ldap.VERSION3
		l.set_option(ldap.OPT_REFERRALS, 0)

		# test
		# when testing using library account, change searchFiler = "uid" to "cn"
		submitted_username = username
		username = "uid="+submitted_username+",ou=People,DC=wayne,DC=edu"
		password = password
		try:
			l.bind_s(username, password)
		except:
			jsonString = '{"desc":"Cannot bind username and password"}'
		
		# set baseDN, scope (SUBTREE searches searches for user and children), attributes
		baseDN = "dc=wayne,dc=edu"
		searchScope = ldap.SCOPE_SUBTREE
		retrieveAttributes = ['firstDotLast','givenName','uid']
		searchFilter = "uid="+submitted_username

		try:
			ldap_result_id = l.search(baseDN, searchScope, searchFilter, retrieveAttributes)
			result_set = list()
			result_type, result_data = l.result(ldap_result_id)
			if not result_data:
				jsonString = '{"desc":"not a valid User"}'
			else:
				for data in result_data:
					if data[0]:
						result_set.append(data)
						jsonString = json.dumps(result_set)		
		except ldap.LDAPError, e:
			jsonString = json.dumps(e.message)

	except:
		jsonString = '{"desc":"something super borked"}'
	return jsonString

