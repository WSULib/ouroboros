#Utility to link Fedora Commons FOXML objects and Solr, with augmentation in /search core

from fedoraManager2.sensitive import *
import os
import sys
import xml.etree.ElementTree as ET
import urllib, urllib2
import requests
from string import Template
import time
import datetime
from lxml import etree
from flask import Blueprint, render_template, abort, request

# revise
from cl.cl import celery
from celery import Task

# augmentCore 
from augmentCore import augmentCore

# define blueprint
FOXML2Solr_blue = Blueprint('FOXML2Solr', __name__, template_folder='templates')


@FOXML2Solr_blue.route("/updateSolr/<update_type>", methods=['POST', 'GET'])
def updateSolr(update_type):			

	if update_type == "fullIndex":				
		index_handle = FOXML2Solr.delay('fullIndex','')

	if update_type == "timestamp":		
		index_handle = FOXML2Solr.delay('timestampIndex','')
		
	# pass the current PIDs to page as list	
	return render_template("updateSolr.html",update_type=update_type)



@celery.task()
def FOXML2Solr(fedEvent, PID):	

	#Get DT Threshold
	def getLastFedoraIndexDate():	
		#evaluate solr response string as python dictionary
		LastFedoraIndexDict = eval(urllib.urlopen("http://localhost/solr4/fedobjs/select?q=id%3ALastFedoraIndex&fl=last_modified&wt=python&indent=true").read())	
		LastFedoraIndexDate = LastFedoraIndexDict['response']['docs'][0]['last_modified']
		print "Last Indexing of FOXML in Solr:",LastFedoraIndexDate,"\n"
		return LastFedoraIndexDate


	#Get Objects/Datastreams modified on or after this date
	def getToUpdate(LastFedoraIndexDate):
		print LastFedoraIndexDate
		# Pulls date last time Fedora was indexed in Solr
		# FYI, this line will limit to only objects: and $object<info:fedora/fedora-system:def/relations-external#isMemberOfCollection> <info:fedora/wayne:collectionBMC>
		# This will need to be paginate, broken up, something - quite slow at even 6,000+
		risearch_query = "select $object from <#ri> where $object <fedora-view:lastModifiedDate> $modified and $modified <mulgara:after> '{LastFedoraIndexDate}'^^<xml-schema:dateTime> in <#xsd>".format(LastFedoraIndexDate=LastFedoraIndexDate)	

		risearch_params = urllib.urlencode({
			'type': 'tuples', 
			'lang': 'itql', 
			'format': 'CSV',
			'limit':'',
			'dt': 'on', 
			'query': risearch_query
			})
		risearch_host = "http://{FEDORA_USER}:{FEDORA_PASSWORD}@localhost/fedora/risearch?".format(FEDORA_USER=FEDORA_USER,FEDORA_PASSWORD=FEDORA_PASSWORD)

		print "********************DEBUG****************************"
		print risearch_query
		print risearch_host

		modified_PIDs = urllib.urlopen(risearch_host,risearch_params)	
		iterPIDs = iter(modified_PIDs)	
		next(iterPIDs)	
		for PIDstring in iterPIDs:
			PIDproper = PIDstring.split("/")[1].rstrip()
			if PIDproper not in toUpdate:
				toUpdate.append(PIDproper)

		# print "PIDs to update:",toUpdate,"\n"
		print "Total to update:",len(toUpdate),"\n"		

		#exit if nothing to update
		if len(toUpdate) < 1:
			print "It does not appear any Fedora Objects have been modified since last Solr Indexing.  You may also enter a date stamp argument, formatted thusly '1969-12-31T12:59:59.265Z', when running FOXML2Solr as stand-alone script to index all records modified after that date."
			
			return False

		else:
			return True

			
	def indexFOXMLinSolr(toUpdate):

		count = 0
		for PID in toUpdate:
			count += 1
			print "Indexing PID:",PID,count," / ",len(toUpdate)
			
			#get object FOXML and parse as XML
			try:
				response = urllib.urlopen("http://{username}:{password}@localhost/fedora/objects/{PID}/objectXML".format(PID=PID,username=username,password=password))
				FOXML = response.read()
				XMLroot = etree.fromstring(FOXML)		
			except:
				print "Could not DOWNLOAD FOXML for",PID
				fhand_exceptions = open(Outputs['downloadExcepts'],'a')
				fhand_exceptions.write(str(PID)+"\n")
				fhand_exceptions.close()

			#get XSL doc, parse as XSL, transform FOXML as Solr add-doc
			try:			
				XSLhand = open('inc/xsl/FOXML_to_Solr.xsl','r')		
				xslt_tree = etree.parse(XSLhand)
		  		transform = etree.XSLT(xslt_tree)
				SolrXML = transform(XMLroot)
			except:
				print "Could not TRANSFORM FOXML for",PID
				fhand_exceptions = open(Outputs['transformExcepts'],'a')
				fhand_exceptions.write(str(PID)+"\n")
				fhand_exceptions.close()

			#index Solr-ready XML (SolrXML)		 
			try:
				updateURL = "http://localhost/solr4/fedobjs/update/"								
				headers = {'Content-Type': 'application/xml'}
				r = requests.post(updateURL, data=str(SolrXML), headers=headers)
				print r.text
			except:
				print "Could not INDEX FOXML for",PID
				fhand_exceptions = open(Outputs['indexExcepts'],'a')
				fhand_exceptions.write(str(PID)+"\n")
				fhand_exceptions.close()	
	
	
	def commitSolrChanges():		

		# commit changes in Solr
		print "*** Committing Changes ***"
		baseurl = 'http://localhost/solr4/fedobjs/update/' 
		data = {'commit':'true'}
		r = requests.post(baseurl,data=data)
		print r.text

	
	def replicateToSearch():
		
		# replicate to "search core"
		print "*** Replicating Changes ***"
		baseurl = 'http://localhost/solr4/search/replication?command=fetchindex' 
		data = {'commit':'true'}
		r = requests.post(baseurl,data=data)
		print r.text	

	
	def updateLastFedoraIndexDate():		

		#Updated LastFedoraIndex in Solr
		print "*** Updating LastFedoraIndex in Solr ***"
		updateURL = "http://localhost/solr4/fedobjs/update/?commit=true"
		dateUpdateXML = "<add><doc><field name='id'>LastFedoraIndex</field><field name='last_modified'>NOW</field></doc></add>"
		headers = {'Content-Type': 'application/xml'}
		r = requests.post(updateURL, data=dateUpdateXML, headers=headers)
		print r.text

	
	def removeFOXMLinSolr(PID):		
		
		print "*** Removing document from Solr ***"		
		PID = PID.replace(":","\:")
		updateURL = "http://localhost/solr4/fedobjs/update/"			
		deleteXML = "<delete><query>id:{PID}</query></delete>".format(PID=PID)
		headers = {'Content-Type': 'application/xml'}
		r = requests.post(updateURL, data=deleteXML, headers=headers)
		print r.text



	# determine Solr action
	#################################################################################################################	
	#Set output filenames
	now = datetime.datetime.now().isoformat()
	Outputs = {}
	Outputs['downloadExcepts'] = './reports/'+now+'_downloadExcepts.csv'
	Outputs['transformExcepts'] = './reports/'+now+'_transformExcepts.csv'
	Outputs['indexExcepts'] = './reports/'+now+'_indexExcepts.csv'

	if fedEvent == "timestampIndex":
		print "Indexing all Fedora items since last full index."
		
		#Globals
		toUpdate = []				

		#start timer
		startTime = int(time.time())

		#run funcs
		LastFedoraIndexDate = getLastFedoraIndexDate()
		
		# generate list of PIDs to update
		result = getToUpdate(LastFedoraIndexDate)		
		
		if result == True:
			# index PIDs in Solr
			indexFOXMLinSolr(toUpdate)
			# augment documents - from augmentCore.py
			augmentCore(toUpdate)	
			# update timestamp in Solr		
			updateLastFedoraIndexDate()
			# commit changes
			commitSolrChanges()
			# replicate changes to /search core
			replicateToSearch()			

			#end timer
			endTime = int(time.time())
			totalTime = endTime - startTime
			print "Total seconds elapsed",totalTime	

		else:
			print "Nothing to do. Finis."

	if fedEvent == "fullIndex":
		print "Indexing ALL Fedora items."
		
		#Globals
		toUpdate = []				

		#start timer
		startTime = int(time.time())		

		LastFedoraIndexDate = "1969-12-31T12:59:59.265Z"
		
		# generate list of PIDs to update
		result = getToUpdate(LastFedoraIndexDate)		
		
		# index PIDs in Solr
		indexFOXMLinSolr(toUpdate)
		# augment documents - from augmentCore.py
		augmentCore(toUpdate)	
		# update timestamp in Solr		
		updateLastFedoraIndexDate()
		# commit changes
		commitSolrChanges()
		# replicate changes to /search core
		replicateToSearch()			

		#end timer
		endTime = int(time.time())
		totalTime = endTime - startTime
		print "Total seconds elapsed",totalTime
		
		

	# Index single item per fedEvent
	if fedEvent == "modifyDatastreamByValue" or fedEvent == "ingest" or fedEvent == "modifyObject":

		# pause
		# time.sleep(1)

		print "Updating / Indexing",PID
		toUpdate = [PID]
		# index PIDs in Solr
		indexFOXMLinSolr(toUpdate)
		# augment documents - from augmentCore.py
		augmentCore(toUpdate)
		# update timestamp in Solr		
		updateLastFedoraIndexDate()
		# commit changes
		commitSolrChanges()
		# replicate changes to /search core
		replicateToSearch()		
		return

	# Remove Object from Solr Index on Purge
	if fedEvent == "purgeObject":
		print "Removing the following from Solr Index",PID		
		removeFOXMLinSolr(PID)
		# commit changes
		commitSolrChanges()
		# replicate changes to /search core
		replicateToSearch()
		return

	#################################################################################################################

if __name__ == '__main__':
    FOXML2Solr("timestampIndex","")
























