#!/usr/bin/python
 
# Script:    DataTables server-side script for PHP and MySQL
# Copyright: 2010 - Allan Jardine
# License:   GPL v2 or BSD (3-point)
 
# Modules
import cgi
import MySQLdb
 
# CGI header
print "Content-Type: text/plain\n\n"
 
 
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Easy set varaibles
#
 
# Array of database columns which should be read and sent back to DataTables
_columns = [ 'PID' ]
 
# Indexed column (used for fast and accurate table cardinality)
_indexColumn = "id";
 
# DB table to use
_sTable = "selectPID";
 
# Database connection information
_databaseInfo = dict(
  host   = "localhost",
  user   = "fm2",
  passwd = "fm2",
  db     = "fedoraManager2"
)
 
 
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# If you just want to use the basic configuration for DataTables with PHP server-side, there is
# no need to edit below this line
#
 
 
class DataTablesServer:
	#
	# __init__
	# Constructor
	#
	def __init__( self ):
		# Class properties
		self.cgi = cgi.FieldStorage()
		self.dbh = MySQLdb.connect(host=_databaseInfo['host'], user=_databaseInfo['user'], \
			passwd=_databaseInfo['passwd'], db=_databaseInfo['db'])
		self.resultData = None
		self.cadinalityFiltered = 0
		self.cadinality = 0
		 
		self.runQueries()
		self.outputResult()
	 
	 
	#
	# outputResult
	# Output the JSON required for DataTables
	#
	def outputResult( self ):
		output = '{'
		output += '"sEcho": '+str(int(self.cgi['sEcho'].value))+', '
		output += '"iTotalRecords": '+str(self.cardinality)+', '
		output += '"iTotalDisplayRecords": '+str(self.cadinalityFiltered)+', '
		output += '"aaData": [ '
		 
		for row in self.resultData:
			output += '['
			for i in range( len(_columns) ):
				if ( _columns[i] == "version" ):
			# 'version' specific formatting
					if ( row[ _columns[i] ] == "0" ):
						output += '"-",'
					else:
						output += '"'+str(row[ _columns[i] ])+'",'
				else:
			# general formatting
					output += '"'+row[ _columns[i] ].replace('"','\\"')+'",'
			 
			# Optional Configuration:
			# If you need to add any extra columns (add/edit/delete etc) to the table, that aren't in the
			# database - you can do it here
			 
			 
			output = output[:-1]
			output += '],'
		output = output[:-1]
		output += '] }'
		 
		print output
	 
	 
	#
	# runQueries
	# Generate the SQL needed and run the queries
	#
	def runQueries( self ):
		# Get the data
		dataCursor = self.dbh.cursor( cursorclass=MySQLdb.cursors.DictCursor )
		dataCursor.execute( """
			SELECT SQL_CALC_FOUND_ROWS %(columns)s
			FROM   %(table)s %(where)s %(order)s %(limit)s""" % dict(
				columns=', '.join(_columns), table=_sTable, where=self.filtering(), order=self.ordering(),
				limit=self.paging()
			) )
		self.resultData = dataCursor.fetchall()
		 
		cadinalityFilteredCursor = self.dbh.cursor()
		cadinalityFilteredCursor.execute( """
			SELECT FOUND_ROWS()
		""" )
		self.cadinalityFiltered = cadinalityFilteredCursor.fetchone()[0]
		 
		cadinalityCursor = self.dbh.cursor()
		cadinalityCursor.execute( """
		SELECT COUNT(%s)
		FROM %s
		""" % _indexColumn, _sTable )
		self.cardinality = cadinalityCursor.fetchone()[0]
	 
	 
	#
	# filtering
	# Create the 'WHERE' part of the SQL string
	#
	def filtering( self ):
		filter = ""
		if ( self.cgi.has_key('sSearch') ) and ( self.cgi['sSearch'].value != "" ):
			filter = "WHERE "
			for i in range( len(_columns) ):
				filter += "%s LIKE '%%%s%%' OR " % (_columns[i], self.cgi['sSearch'].value)
			filter = filter[:-3]
		return filter
	 
	 
	#
	# ordering
	# Create the 'ORDER BY' part of the SQL string
	#	
	def ordering( self ):
		order = ""
		print dir(self)
		if ( self.cgi['iSortCol_0'].value != "" ) and ( self.cgi['iSortingCols'].value > 0 ):
			order = "ORDER BY  "
			for i in range( int(self.cgi['iSortingCols'].value) ):
				order += "%s %s, " % (_columns[ int(self.cgi['iSortCol_'+str(i)].value) ], \
					self.cgi['sSortDir_'+str(i)].value)
		return order[:-2]
	 
	 
	#
	# paging
	# Create the 'LIMIT' part of the SQL string
	#
	def paging( self ):
		limit = ""
		if ( self.cgi['iDisplayStart'] != "" ) and ( self.cgi['iDisplayLength'] != -1 ):
			limit = "LIMIT %s, %s" % (self.cgi['iDisplayStart'].value, self.cgi['iDisplayLength'].value )
		return limit
 
 
# Perform the server-side actions for DataTables
dtserver=DataTablesServer()