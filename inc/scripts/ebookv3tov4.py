

from WSUDOR_ContentTypes import logging
logging = logging.getChild("ebookv3tov4")


def convert_v3tov4():
	
	'''
	This function will take a v3 book and rewrite the objMeta for v4 export/ingest

	1) For each page (constituent of book)
		- write v4 objMeta
		- add datastreams
			- BAGIT_META
			- MODS
			- PDF (?)
			- OBJMETA

	'''





# def export_v3tov4():

# 	'''
# 	Goal is to export v3 books in the structure that IngestWorkspace would create for a v4 book.

# 	Roughly:
# 	/wayne:foobar

# 		/ data
# 			- MODS.xml
# 			- objMeta.json
# 			- RELS-EXT.xml
# 			- RELS-INT.xml

# 			/ datastreams
# 				- HTML_FULL # no file extension
# 				- PDF_FULL.pdf

# 			/ constituent_objects

# 				/ wayne:foobar_Page 1
# 					/ data
# 						/ datastreams
# 							- 001.tif
# 							- 001.pdf
# 							- 001.htm
# 							- 001.xml
# 						- MODS.xml
# 						- objMeta.json
# 						- RELS-EXT.xml
# 						- RELS-INT.xml					
# 					- manifest-md5.txt
# 					- tagmanifest-md5.txt
# 					- bag-info.txt
# 					- bagit.txt

# 		- manifest-md5.txt
# 		- tagmanifest-md5.txt
# 		- bag-info.txt
# 		- bagit.txt

# 	'''

# 	logging.debug("exporting v3 book for v4 ingest - to be used in conjunction with ingest_v3tov4()")


# def ingest_v3tov4():
# 	logging.debug("ingesting v3 book as v4 model - to be used in conjunction with export_v3tov4()")