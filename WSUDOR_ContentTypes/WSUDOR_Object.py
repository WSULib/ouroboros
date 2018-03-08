# -*- coding: utf-8 -*-

import copy
import os
import json
import traceback
import sys
from lxml import etree
import tarfile
import uuid
import StringIO
import tarfile
import xmltodict
from lxml import etree
import requests
import time
import ast
import zipfile
import shutil
import ConfigParser
import glob
import hashlib
from urllib import unquote, quote_plus, urlopen
from collections import deque
import struct
from PIL import Image
import ssl
import operator
from dateutil import parser

# rdflib
import rdflib
from rdflib.namespace import XSD, RDF, Namespace

# library for working with LOC BagIt standard
import bagit

# celery
from WSUDOR_Manager import celery

# eulfedora
import eulfedora
from eulfedora import syncutil

# localConfig
import localConfig

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_ContentTypes import logging
logging = logging.getChild("WSUDOR_Object")
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import fedoraHandles
from WSUDOR_Manager.lmdbHandles import lmdb_env
from WSUDOR_Manager import models, helpers, redisHandles, actions, utilities, db
from WSUDOR_Indexer.models import IndexRouter

# derivatives
from inc.derivatives import Derivative
from inc.derivatives.image import ImageDerivative

# jpylyzer
from jpylyzer import jpylyzer
from jpylyzer import etpatch

# iiif-prezi
from iiif_prezi.factory import ManifestFactory



# class factory, returns WSUDOR_GenObject as extended by specific ContentType
def WSUDOR_Object(payload, orig_payload=False, object_type="WSUDOR"):

    '''
    Function to determine ContentType, then fire the appropriate subclass to WSUDOR_GenObject
    '''

    try:
        # Future WSUDOR object, BagIt object
        if object_type == "bag":

            # prepare new working dir & recall original
            working_dir = "/tmp/Ouroboros/"+str(uuid.uuid4())
            logging.debug("object_type is bag, creating working dir at %s" % working_dir)
            orig_payload = payload

            '''
            # determine if directory or archive file
            # if dir, copy to, if archive, decompress and copy
            # set 'working_dir' to new location in /tmp/Ouroboros
            '''
            if os.path.isdir(payload):
                logging.debug("directory detected, symlinking")
                # shutil.copytree(payload,working_dir)
                os.symlink(payload, working_dir)


            # tar file or gz
            elif payload.endswith(('.tar','.gz')):
                logging.debug("tar / gz detected, decompressing")
                tar_handle = tarfile.open(payload,'r')
                tar_handle.extractall(path=working_dir)
                payload = working_dir

            elif payload.endswith('zip'):
                logging.debug("zip file detected, unzipping")
                with zipfile.ZipFile(payload, 'r') as z:
                    z.extractall(working_dir)

            # if the working dir has a sub-dir, assume that's the object directory proper
            if len(os.listdir(working_dir)) == 1 and os.path.isdir("/".join((working_dir, os.listdir(working_dir)[0]))):
                logging.debug("we got a sub-dir")
                payload = "/".join((working_dir,os.listdir(working_dir)[0]))
            else:
                payload = working_dir
            logging.debug("payload is: %s" % payload)

            # read objMeta.json
            path = payload + '/data/objMeta.json'
            fhand = open(path,'r')
            objMeta = json.loads(fhand.read())
            # only need content_type
            content_type = objMeta['content_type']


        # Active, WSUDOR object
        if object_type == "WSUDOR":

            # check if payload actual eulfedora object or string literal, in latter case, attempt to open eul object
            if type(payload) != eulfedora.models.DigitalObject:
                payload = fedora_handle.get_object(payload)

            if payload.exists == False:
                logging.debug("Object does not exist, cannot instantiate as WSUDOR type object.")
                return False

            # GET WSUDOR_X object content_model
            '''
            This is an important pivot.  We're taking the old ContentModel syntax: "info:fedora/CM:Image", and slicing only the last component off
            to use, "Image".  Then, we append that to "WSUDOR_" to get ContentTypes such as "WSUDOR_Image", or "WSUDOR_Collection", etc.
            '''
            try:
                content_types = list(payload.risearch.get_objects(payload.uri,'info:fedora/fedora-system:def/relations-external#hasContentModel'))
                if len(content_types) <= 1:
                    content_type = content_types[0].split(":")[-1]
                else:
                    try:
                        # use preferredContentModel relationship to disambiguate
                        pref_type = list(payload.risearch.get_objects(payload.uri,'http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel'))
                        pref_type = pref_type[0].split(":")[-1]
                        content_type = pref_type
                    except:
                        logging.debug("More than one hasContentModel found, but no preferredContentModel.  Aborting.")
                        return False

                content_type = "WSUDOR_"+str(content_type)

            # fallback, grab straight from OBJMETA datastream / only fires for v2 objects
            except:
                if "OBJMETA" in payload.ds_list:
                    logging.debug("Race conditions detected, grabbing content_type from objMeta")
                    objmeta = json.loads(payload.getDatastreamObject('OBJMETA').content)
                    content_type = objmeta['content_type']

        # logging.debug("Our content type is:",content_type)

    except Exception,e:
        logging.debug("%s" % traceback.format_exc())
        logging.debug("%s" % e)
        return False

    # need check if valid subclass of WSUDOR_GenObject
    try:
        return getattr(WSUDOR_ContentTypes, str(content_type))(object_type = object_type, content_type = content_type, payload = payload, orig_payload = orig_payload)
    except:
        logging.debug("Could not find appropriate ContentType, returning False.")
        return False



# WSUDOR Generic Object class (designed to be extended by ContentTypes)
class WSUDOR_GenObject(object):
    '''
    This class represents an object already present, or destined, for Ouroboros.
    "object_type" is required for discerning between the two.

    object_type = 'WSUDOR'
        - object is present in WSUDOR, actions include management and export

    object_type = 'bag'
        - object is present outside of WSUDOR, actions include primarily ingest and validation
    '''

    # init
    ############################################################################################################
    def __init__(self, object_type=False, content_type=False, payload=False, orig_payload=False):

        self.index_on_ingest = True

        self.struct_requirements = {
            "WSUDOR_GenObject":{
                "datastreams":[
                    {
                        "id":"THUMBNAIL",
                        "purpose":"Thumbnail of image",
                        "mimetype":"image/jpeg"
                    },
                    {
                        "id":"MODS",
                        "purpose":"Descriptive MODS",
                        "mimetype":"text/xml"
                    },
                    {
                        "id":"RELS-EXT",
                        "purpose":"RDF relationships",
                        "mimetype":"application/rdf+xml"
                    },
                    {
                        "id":"POLICY",
                        "purpose":"XACML Policy",
                        "mimetype":"text/xml"
                    }
                ],
                "external_relationships":[
                    "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable",
                    "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy"
                ]
            }
        }

        self.orig_payload = orig_payload

        # WSUDOR or BagIt archive for the object returned
        try:

            # Future WSUDOR object, BagIt object
            if object_type == "bag":
                self.object_type = object_type

                # read objMeta.json
                path = payload + '/data/objMeta.json'
                fhand = open(path,'r')
                self.objMeta = json.loads(fhand.read())
                logging.debug("objMeta.json loaded for: %s/%s" % (self.objMeta['id'],self.objMeta['label']))

                # instantiate bag propoerties
                self.pid = self.objMeta['id']
                self.label = self.objMeta['label']
                self.content_type = content_type # use content_type as derived from WSUDOR_Object factory

                # placeholder for future ohandle
                self.ohandle = None

                # BagIt methods
                self.Bag = bagit.Bag(payload)
                self.temp_payload = self.Bag.path


            # Active, WSUDOR object
            if object_type == "WSUDOR":

                # check if payload actual eulfedora object or string literal
                if type(payload) != eulfedora.models.DigitalObject:
                    payload = fedora_handle.get_object(payload)

                # instantiate WSUDOR propoerties
                self.object_type = object_type
                self.pid = payload.pid
                self.pid_suffix = payload.pid.split(":")[1]
                self.content_type = content_type
                self.ohandle = payload

                # only fires for v2 objects
                if "OBJMETA" in self.ohandle.ds_list:
                    self.objMeta = json.loads(self.ohandle.getDatastreamObject('OBJMETA').content)


        except Exception,e:
            logging.debug("%s" % traceback.format_exc())
            logging.debug("%s" % e)


        try:
            # initiate IIIF Manifest Factory
            self.iiif_factory = ManifestFactory()
            # Where the resources live on the web
            self.iiif_factory.set_base_prezi_uri("%s://%s/item/%s/iiif" % (localConfig.IIIF_IPREZI_PROTOCOL, localConfig.IIIF_MANIFEST_TARGET_HOST, self.pid))
            # Where the resources live on disk
            self.iiif_factory.set_base_prezi_dir("/tmp")

            # Default Image API information
            self.iiif_factory.set_base_image_uri("%s://%s/loris" % (localConfig.IIIF_IPREZI_PROTOCOL, localConfig.IIIF_MANIFEST_TARGET_HOST))
            self.iiif_factory.set_iiif_image_info(2.0, 2) # Version, ComplianceLevel

            # 'warn' will print warnings, default level
            # 'error' will turn off warnings
            # 'error_on_warning' will make warnings into errors
            self.iiif_factory.set_debug("warn")
        except:
            self.iiif_factory = False



    # Lazy Loaded properties
    ############################################################################################################
    '''
    These properties use helpers.LazyProperty decorator, to avoid loading them if not called.
    '''

    # MODS metadata
    @helpers.LazyProperty
    def MODS_XML(self):
        return self.ohandle.getDatastreamObject('MODS').content.serialize()


    @helpers.LazyProperty
    def MODS_dict(self):
        return xmltodict.parse(self.MODS_XML)


    @helpers.LazyProperty
    def MODS_Solr_flat(self):
        # flattens MODS with GSearch XSLT and loads as dictionary
        XSLhand = open('inc/xsl/MODS_extract.xsl','r')
        xslt_tree = etree.parse(XSLhand)
        transform = etree.XSLT(xslt_tree)
        XMLroot = etree.fromstring(self.MODS_XML)
        SolrXML = transform(XMLroot)
        return xmltodict.parse(str(SolrXML))


    #DC metadata
    @helpers.LazyProperty
    def DC_XML(self):
        return self.ohandle.getDatastreamObject('DC').content.serialize()


    @helpers.LazyProperty
    def DC_dict(self):
        return xmltodict.parse(self.DC_XML)


    @helpers.LazyProperty
    def DC_Solr_flat(self):
        # flattens MODS with GSearch XSLT and loads as dictionary
        XSLhand = open('inc/xsl/DC_extract.xsl','r')
        xslt_tree = etree.parse(XSLhand)
        transform = etree.XSLT(xslt_tree)
        XMLroot = etree.fromstring(self.DC_XML)
        SolrXML = transform(XMLroot)
        return xmltodict.parse(str(SolrXML))


    #RELS-EXT and RELS-INT metadata
    @helpers.LazyProperty
    def RELS_EXT_Solr_flat(self):
        # flattens MODS with GSearch XSLT and loads as dictionary
        XSLhand = open('inc/xsl/RELS-EXT_extract.xsl','r')
        xslt_tree = etree.parse(XSLhand)
        transform = etree.XSLT(xslt_tree)
        # raw, unmodified RDF
        raw_xml_URL = "%s/objects/%s/datastreams/RELS-EXT/content" % (localConfig.FEDORA_ROOT.rstrip('/'), self.pid)
        raw_xml = requests.get(raw_xml_URL).text.encode("utf-8")
        XMLroot = etree.fromstring(raw_xml)
        SolrXML = transform(XMLroot)
        return xmltodict.parse(str(SolrXML))


    @helpers.LazyProperty
    def RELS_INT_Solr_flat(self):
        # flattens MODS with GSearch XSLT and loads as dictionary
        XSLhand = open('inc/xsl/RELS-EXT_extract.xsl','r')
        xslt_tree = etree.parse(XSLhand)
        transform = etree.XSLT(xslt_tree)
        # raw, unmodified RDF
        raw_xml_URL = "%s/objects/%s/datastreams/RELS-INT/content" % (localConfig.FEDORA_ROOT.rstrip('/'), self.pid)
        raw_xml = requests.get(raw_xml_URL).text.encode("utf-8")
        XMLroot = etree.fromstring(raw_xml)
        SolrXML = transform(XMLroot)
        return xmltodict.parse(str(SolrXML))


    # SolrDoc class
    @helpers.LazyProperty
    def SolrDoc(self):
        return models.SolrDoc(self.pid)


    # SolrSearchDoc class
    @helpers.LazyProperty
    def SolrSearchDoc(self):
        return models.SolrSearchDoc(self.pid)


    # return IIIF maniest
    @helpers.LazyProperty
    def iiif_manifest(self, format='string'):       

        # retrieve from LMDB database
        return models.LMDBClient.get('%s_iiif_manifest' % (self.pid))


    # PREMIS client
    @helpers.LazyProperty
    def premis(self):
        return models.PREMISClient(pid=self.pid)


    # MODS metadata
    def update_objMeta(self):
        '''
        Replaces OBJMETA datastream with current contents of self.objMeta (a dictionary)
        '''
        objMeta_handle = eulfedora.models.FileDatastreamObject(v3book.ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
        objMeta_handle.label = "Ingest Bag Object Metadata"
        objMeta_handle.content = json.dumps(self.objMeta)
        objMeta_handle.save()


    def calc_object_size(self, update_constituents=False):

        '''
        Method for calculating and storing object size
        Optionally, updating size of constituents as well
        '''

        stime = time.time()

        logging.debug("calculating object and constituent sizes")

        size_dict = {
            'datastreams':{}
        }
        fedora_obj_size = 0
        wsudor_obj_size = 0

        # loop through datastreams, append size to return dictionary
        for ds in self.ohandle.ds_list:
            ds_handle = self.ohandle.getDatastreamObject(ds)
            ds_size = ds_handle.size
            fedora_obj_size += ds_size            
            size_dict['datastreams'][ds] = ( ds_size, utilities.sizeof_fmt(ds_size) )

        # set as equal prior to constituent calc
        wsudor_obj_size = fedora_obj_size

        # loop through constituents and add as well
        if len(self.constituents) > 0:
            logging.debug("constituents found, including in object_size")
            size_dict['constituent_objects'] = { 'objects':{} }

            # set total size at 0
            constituent_objects_size = 0

            # loop through
            for obj in self.constituents:

                # check LMDB for stored constituent size
                if not update_constituents:

                    lmdb_constituent_size = models.LMDBClient.get('%s_object_size' % obj.pid)
                    if lmdb_constituent_size:
                        constituent_object_size = json.loads(lmdb_constituent_size)
                    
                # if we are updating constituents, or the result of the LMDB grab above was None, recalculate (also storing in LMDB)
                if update_constituents or not lmdb_constituent_size:
                    constituent_object_size = WSUDOR_ContentTypes.WSUDOR_Object(obj.pid).calc_object_size()
                
                # add constituent to constituents directory
                size_dict['constituent_objects']['objects'][obj.pid] = constituent_object_size
                constituent_objects_size += constituent_object_size['fedora_total_size'][0]

            # fold into constituents size_dict
            size_dict['constituent_objects']['total_constituents_size'] = ( constituent_objects_size, utilities.sizeof_fmt(constituent_objects_size) )
            # bump wsudor_obj_size
            wsudor_obj_size += constituent_objects_size

        # fold into self size_dict
        size_dict['fedora_total_size'] = (fedora_obj_size, utilities.sizeof_fmt(fedora_obj_size) )
        size_dict['wsudor_total_size'] = (wsudor_obj_size, utilities.sizeof_fmt(wsudor_obj_size) )

        # write to LMDB
        logging.debug("writing to LMDB")
        models.LMDBClient.put('%s_object_size' % self.pid, json.dumps(size_dict))

        # return
        logging.debug("elapsed: %s" % (time.time() - stime))
        return size_dict


    def object_size(self, update_self=False, update_constituents=False):

        '''
        returns object size stored in LMDB, if not present, recalculates
        '''
        
        if not update_self:
            # check LMDB
            object_size = models.LMDBClient.get("%s_object_size" % self.pid)

            # if found, return
            if object_size:
                return json.loads(object_size)

            # if not found, recalculate
            else:
                return self.calc_object_size()
        
        else:
            return self.calc_object_size(update_constituents=update_constituents)



    #######################################################
    # RDF Relationships
    #######################################################

    # constituent objects
    @helpers.LazyProperty
    def constituents(self):

        '''
        Returns OrderedDict with pageOrder as key, digital obj as val
        '''

        # get ordered, constituent objs
        sparql_response = fedora_handle.risearch.sparql_query('select $constituent WHERE {{ $constituent <info:fedora/fedora-system:def/relations-external#isConstituentOf> <info:fedora/%s> . }}' % (self.pid))
        constituent_objects = [ fedora_handle.get_object(obj['constituent']) for obj in sparql_response ]       
        return constituent_objects


    # constituent objects
    @helpers.LazyProperty
    def constituents_from_objMeta(self):

        '''
        Returns list of constitobjects bags in /constituent_objects from ObjMeta
        '''

        return self.objMeta['constituent_objects']


    # collection members
    @helpers.LazyProperty
    def collectionMembers(self):

        '''
        Returns generator of PIDs that are members
        '''

        # get all members
        return fedora_handle.risearch.get_subjects('fedora-rels-ext:isMemberOfCollection', self.ohandle.uri)


    # rels-int, partOf
    @helpers.LazyProperty
    def hasInternalParts(self):

        '''
        returns datastreams that are rels-int:partOf object
        '''
        
        sparql_response = fedora_handle.risearch.sparql_query('select $s WHERE {{ $s <info:fedora/fedora-system:def/relations-internal#isPartOf> <info:fedora/%s> . }}' % (self.pid))
        parts = [ fedora_handle.get_object(obj['s']) for obj in sparql_response ]
        parts = [ part.pid.split("/")[-1] for part in parts ]
        return parts


    # hasMemberOf
    @helpers.LazyProperty
    def hasMemberOf(self):

        '''
        returns subjecst that are isMember of object
        '''

        # get all members
        return list(fedora_handle.risearch.get_subjects('fedora-rels-ext:isMemberOf', self.ohandle.uri))


    # isMemberOfCollection
    @helpers.LazyProperty
    def isMemberOfCollections(self):

        '''
        returns list of collections object belongs to
        '''
        if 'rels_isMemberOfCollection' in self.SolrDoc.asDictionary():
            return self.SolrDoc.asDictionary()['rels_isMemberOfCollection']
        else:
            return False


    # learning objects
    @helpers.LazyProperty
    def hasLearningObjects(self):

        # get collections
        sparql_query = "select $lo_title $lo_uri from <#ri> where { $lo_uri <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/learningObjectFor> <fedora:%s> . $lo_uri <http://purl.org/dc/elements/1.1/title> $lo_title . }" % self.pid
        learning_objects = list(fedora_handle.risearch.sparql_query(sparql_query))
        return learning_objects



    # object triples
    @helpers.LazyProperty
    def rdf_triples(self):
        return list(self.ohandle.rels_ext.content)


    # WSUDOR_Object Methods
    ############################################################################################################


    def verify_checksums(self, log_to_premis=True, verify_constituents=False):

        '''
        using Fedora's built-in checksum test, confirm all datastream's checksums
        '''

        verify_dict = {
            'verdict':None,
            'datastreams':{}
        }

        # iterate through datastreams
        for ds in self.ohandle.ds_list:
            ds_handle = self.ohandle.getDatastreamObject(ds)
            if ds_handle.control_group != 'E':
                verify_dict['datastreams'][ds] = {
                    'checksum':ds_handle.checksum,
                    'valid_checksum':ds_handle.validate_checksum()
                }
        logging.debug(verify_dict)
                
        # get final verdict
        fail_dict = { ds:verify_dict['datastreams'][ds] for ds in verify_dict['datastreams'].keys() if not verify_dict['datastreams'][ds]['valid_checksum']}
        logging.debug(fail_dict)
        if len(fail_dict.keys()) == 0:
            verify_dict['verdict'] = True
        else:
            verify_dict['verdict'] = False
            verify_dict['offenders'] = fail_dict

        # log verification as premis event
        if log_to_premis:
            event = self.premis.add_custom_event({
                'type':'verify_checksums',
                'detail':'checksum verification via Fedora validation',
                'outcome':{
                    'result':str(verify_dict['verdict']),
                    'detail':verify_dict
                }
            })

        # optionally, verify checksums for constituents
        '''
        Currently, this check is defaulted to False, as it duplicates checksumming for the vast majority of objects in repository (constituents).
        However, is an optional flag and check.
        '''
        if verify_constituents:
            # establish constituent section
            constituent_checks = {}
            # loop through consituents and verify their datastreams
            if len(self.constituents) > 0:
                for constituent in self.constituents:
                    obj = WSUDOR_ContentTypes.WSUDOR_Object(constituent)
                    constituent_verdict = obj.verify_checksums(log_to_premis=log_to_premis, verify_constituents=False)
                    constituent_checks[obj.pid] = constituent_verdict
            # analyze results
            constituent_fail_dict = { constituent:constituent_checks[constituent] for constituent in constituent_checks.keys() if not constituent_checks[constituent]['verdict']}
            verify_dict['constituents'] = {}
            if len(constituent_fail_dict.keys()) == 0:
                verify_dict['constituents']['verdict'] = True
            else:
                verify_dict['constituents']['verdict'] = False
                verify_dict['constituents']['offenders'] = constituent_fail_dict

        # return
        return verify_dict



    # expects True or False, sets as discoverability, and optionally reindexes
    def set_discoverability(self, discoverable, reindex=False):

        current_discoverability = self.ohandle.risearch.get_objects(self.ohandle.uri, 'http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable').next()
        logging.debug("Current discoverability is: %s, changing to %s" % (current_discoverability.split("/")[-1], discoverable))

        # purge old relationship
        fedora_handle.api.purgeRelationship(self.ohandle, self.ohandle.uri, 'http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable',current_discoverability)

        # add new relationship
        fedora_handle.api.addRelationship(self.ohandle, self.ohandle.uri, 'http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable',"info:fedora/%s" % str(discoverable))


    # base ingest method, that runs some pre-ingest work, and eventually fires WSUDOR Content Type specific .ingestBag()
    def ingest(self, indexObject=True):

        # add PID to indexer queue with 'hold' action to prevent indexing
        self.add_to_indexer_queue(action='hold')
        
        # run content-type specific ingest
        return self.ingestBag(indexObject=indexObject)


    # generic, simple ingest
    def ingestBag(self, indexObject=True):
        
        if self.object_type != "bag":
            raise Exception("WSUDOR_Object instance is not 'bag' type, aborting.")

        # ingest Volume object
        try:
            self.ohandle = fedora_handle.get_object(self.objMeta['id'],create=True)
            self.ohandle.save()

            # set base properties of object
            self.ohandle.label = self.objMeta['label']

            # write POLICY datastream (NOTE: 'E' management type required, not 'R')
            logging.debug("Using policy: %s" % self.objMeta['policy'])
            policy_suffix = self.objMeta['policy']
            policy_handle = eulfedora.models.DatastreamObject(self.ohandle,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
            policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
            policy_handle.label = "POLICY"
            policy_handle.save()

            # write objMeta as datastream
            objMeta_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
            objMeta_handle.label = "Ingest Bag Object Metadata"
            objMeta_handle.content = json.dumps(self.objMeta)
            objMeta_handle.save()

            # write explicit RELS-EXT relationships
            for relationship in self.objMeta['object_relationships']:
                logging.debug("Writing relationship: %s %s" % (str(relationship['predicate']),str(relationship['object'])))
                self.ohandle.add_relationship(str(relationship['predicate']),str(relationship['object']))

            # writes derived RELS-EXT
            content_type_string = "info:fedora/CM:"+self.objMeta['content_type'].split("_")[1]
            self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string)

            # write MODS datastream if MODS.xml exists
            if os.path.exists(self.Bag.path + "/data/MODS.xml"):
                MODS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
                MODS_handle.label = "MODS descriptive metadata"
                file_path = self.Bag.path + "/data/MODS.xml"
                MODS_handle.content = open(file_path)
                MODS_handle.save()

            else:
                # write generic MODS datastream
                MODS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
                MODS_handle.label = "MODS descriptive metadata"

                raw_MODS = '''
<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.4" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">
  <mods:titleInfo>
    <mods:title>%s</mods:title>
  </mods:titleInfo>
  <mods:identifier type="local">%s</mods:identifier>
  <mods:extension>
    <PID>%s</PID>
  </mods:extension>
</mods:mods>
                ''' % (self.objMeta['label'], self.objMeta['id'].split(":")[1], self.objMeta['id'])
                logging.debug("%s" % raw_MODS)
                MODS_handle.content = raw_MODS
                MODS_handle.save()

            # save and commit object before finishIngest()
            final_save = self.ohandle.save()

            # finish generic ingest
            return self.finishIngest(indexObject=indexObject)


        # exception handling
        except Exception,e:
            logging.debug("%s" % traceback.format_exc())
            logging.debug("Volume Ingest Error: %s" % e)
            return False


    # function that runs at end of ContentType ingestBag(), running ingest processes generic to ALL objects
    def finishIngest(self, indexObject=True, gen_manifest=False, contentTypeMethods=[]):

        # as object finishes ingest, it can be granted eulfedora methods, its 'ohandle' attribute
        if self.ohandle != None:
            self.ohandle = fedora_handle.get_object(self.objMeta['id'])

        # pull in BagIt metadata as BAG_META datastream tarball
        temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".tar"
        tar_handle = tarfile.open(temp_filename,'w')
        for bag_meta_file in ['bag-info.txt','bagit.txt','manifest-md5.txt','tagmanifest-md5.txt']:
            tar_handle.add(self.Bag.path + "/" + bag_meta_file, recursive=False, arcname=bag_meta_file)
        tar_handle.close()
        bag_meta_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "BAGIT_META", "BagIt Metadata Tarball", mimetype="application/x-tar", control_group='M')
        bag_meta_handle.label = "BagIt Metadata Tarball"
        bag_meta_handle.content = open(temp_filename)
        bag_meta_handle.save()
        os.system('rm %s' % (temp_filename))

        # Write all objects as isWSUDORObject 
        self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isWSUDORObject","True")

        # if gen_manifest set, generate IIIF Manifest
        if gen_manifest == True:
            try:
                self.genIIIFManifest(on_demand=True)
            except:
                logging.debug("failed on generating IIIF manifest")

        # register with OAI if content model permits
        if hasattr(self, 'OAIexposed') and self.OAIexposed:
            self.registerOAI()

        # the following methods are not needed when objects are "passing through"
        if indexObject:

            # calculate object size, but skip constituents, as they were likely calculated on ingest
            self.object_size(update_self=True, update_constituents=False)
            
            # run all ContentType specific methods that were passed here
            logging.debug("RUNNING ContentType methods...")
            for func in contentTypeMethods:
                func()

        else:
            logging.debug("skipping index of object")

        # CLEANUP
        # delete temp_payload, might be dir or symlink
        try:
            logging.debug("removing temp_payload directory")
            shutil.rmtree(self.temp_payload)
        except OSError, e:
            # might be symlink
            logging.debug("removing temp_payload symlink")
            os.unlink(self.temp_payload)

        # finally, remove 'hold' action in indexer queue and return
        if indexObject:
            self.alter_in_indexer_queue('index')
        else:
            self.alter_in_indexer_queue('forget')
            
        # finally, return
        return True


    # export datastreams based on DS ids and objMeta / requires (ds_id, full path filename) tuples to write them
    def writeDS(self, ds_id, ds_filepath):

        logging.debug("writing datastream: %s" % ds_id)

        ds_handle = self.ohandle.getDatastreamObject(ds_id)

        # skip if empty (might have been removed / condensed, as case with PDFs)
        if ds_handle.exists:

            # XML ds model
            if isinstance(ds_handle, eulfedora.models.XmlDatastreamObject) or isinstance(ds_handle, eulfedora.models.RdfDatastreamObject):
                logging.debug("FIRING XML WRITER")
                with open(ds_filepath,'w') as fhand:
                    fhand.write(ds_handle.content.serialize())

            # generic ds model (isinstance(ds_handle,eulfedora.models.DatastreamObject))
            else:
                logging.debug("FIRING GENERIC WRITER")
                with open(ds_filepath,'wb') as fhand:
                    for chunk in ds_handle.get_chunked_content():
                        fhand.write(chunk)

        else:
            logging.debug("Content was NONE for %s - skipping..." % ds_id)


    # export object
    def export(self, 
        job_package=False, 
        export_dir=localConfig.BAG_EXPORT_LOCATION, 
        preserve_relationships=True, 
        export_constituents=True, 
        is_constituent=False, 
        tarball=True, 
        overwrite_export=True):

        '''
        Target Example:
        .
        ├── bag-info.txt
        ├── bagit.txt
        ├── data
        │   ├── datastreams
        │   │   ├── roots.jpg
        │   │   └── trunk.jpg
        │   ├── MODS.xml
        │   ├── RELS-EXT.rdf (if preserving relationships)
        │   ├── RELS-INT.rdf (if preserving relationships)
        │   └── objMeta.json
        ├── manifest-md5.txt
        └── tagmanifest-md5.txt
        '''

        # working dir in /tmp
        working_dir = "/tmp/Ouroboros/export_bags"

        # create if doesn't exist
        if not os.path.exists("/tmp/Ouroboros/export_bags"):
            logging.debug("tmp export directory not found, creating...")
            os.mkdir("/tmp/Ouroboros/export_bags")

        # create directory stucture
        dir_structure = [working_dir, str(uuid.uuid4()), 'data', 'datastreams']
        bag_root = os.path.join(*dir_structure[:2])
        data_root = os.path.join(*dir_structure[:3])
        datastreams_root = os.path.join(*dir_structure[:4])
        os.makedirs(os.path.join(*dir_structure))
        print(bag_root, data_root, datastreams_root)

        # move bagit files to temp dir, and unpack
        bagit_ds_handle = self.ohandle.getDatastreamObject("BAGIT_META")
        if bagit_ds_handle.exists:
            bagit_files = bagit_ds_handle.content
            bagitIO = StringIO.StringIO(bagit_files)
            tar_handle = tarfile.open(fileobj=bagitIO)
            tar_handle.extractall(path=bag_root)

        # write original datastreams (relies on objMeta)
        for ds in self.objMeta['datastreams']:
            logging.debug("writing %s" % ds)
            self.writeDS(ds['ds_id'], os.path.join(*[datastreams_root, ds['filename']]))

        # include RELS and RELS-INT
        if preserve_relationships == True:
            logging.debug("preserving current relationships and writing to RELS-EXT and RELS-INT")
            for rels_ds in ['RELS-EXT','RELS-INT']:
                logging.debug("writing %s" % rels_ds)
                self.writeDS(rels_ds, os.path.join(*[data_root, "%s.rdf" % rels_ds]))

        ##########################################################################################
        # content-type specific export
        ##########################################################################################
        '''
        All content types optionally may contain an export_content_type() method
        EXPECTS: bag_root, data_root, datastreams_root, tarball
        '''
        if hasattr(self, 'export_content_type'):
            logging.debug('running content-type specific export')
            self.export_content_type(self.objMeta, bag_root, data_root, datastreams_root, tarball, preserve_relationships, overwrite_export)
        ##########################################################################################

        # write MODS 
        self.writeDS("MODS", os.path.join(*[data_root, "MODS.xml"]))

        # # write objMeta
        # self.writeDS("OBJMETA", os.path.join(*[data_root, "objMeta.json"]))

        # write and update objMeta.json
        '''
        If preserving relationships, then update objMeta
        Some aspects of objMeta are rewritten on the way out:
            - empty object_relationships[] in stored objMeta, and fill with current relationships
        '''
        # copy objMeta
        objMeta_copy = copy.deepcopy(self.objMeta)

        # iterate through current RELS and write
        if preserve_relationships:
            objMeta_copy['object_relationships'] = []
            for triple in self.ohandle.rels_ext.content:
                objMeta_copy['object_relationships'].append({
                    'predicate':str(triple[1]),
                    'object':str(triple[2])
                })

        # write to disk
        logging.debug("writing new objMeta to disk: %s" % objMeta_copy)
        with open(os.path.join(*[data_root, "objMeta.json"]),'w') as fhand:
            fhand.write(json.dumps(objMeta_copy))

        # rename dir
        named_dir = self.pid.replace(":","-")
        os.system("mv %s %s" % (bag_root, os.path.join(*[working_dir, named_dir])))
        orig_dir = os.getcwd()
        os.chdir(working_dir)
        
        # if tarball
        if tarball:
            os.system("tar -cvf %s.tar %s" % (named_dir, named_dir))
            os.system("rm -r %s" % os.path.join(*[working_dir, named_dir]))

            # check if target exists, and remove if overwrite_export=True
            if overwrite_export and os.path.exists(os.path.join(*[export_dir, "%s.tar" % named_dir])):
                logging.debug("overwrite_export True, and target found, removing...")
                os.remove(os.path.join(*[export_dir, "%s.tar" % named_dir]))

            # move to export directory
            os.system("mv %s.tar %s" % (named_dir, export_dir))

            # jump back to original working dir
            os.chdir(orig_dir)

            # return location or url
            return "%s/%s.tar" % (export_dir, named_dir)

        else:
            # check if target exists, and remove if overwrite_export=True
            if overwrite_export and os.path.exists(os.path.join(*[export_dir, named_dir])):
                logging.debug("overwrite_export True, and target found, removing...")
                shutil.rmtree(os.path.join(*[export_dir, named_dir]))

            # move to export directory
            os.system("mv %s %s" % (named_dir, export_dir))

            # jump back to original working dir
            os.chdir(orig_dir)

            # return location or url
            return "%s/%s" % (export_dir, named_dir)


    # reingest bag
    def reingestBag(self, removeTempExport=True, preserveRelationships=True):

      logging.debug("Roundrip Ingesting: %s" % self.pid)

      # export bag, returning the file structure location of tar file
      export_location = self.export(tarball=True)
      logging.debug("Location of export: %s" % export_location)

      # open bag
      bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(export_location, object_type='bag')

      # purge self
      if bag_handle != False:
          self.purge(override_state=True)
      else:
          logging.debug("exported object doesn't look good, aborting purge")

      # reingest exported tar file
      bag_handle.ingest()

      # delete exported tar
      if removeTempExport == True:
          logging.debug("Removing export tar...")
          os.remove(export_location)

      # return
      return self.pid, "Reingested."


    def previewSolrDict(self):
        '''
        Function to run current WSUDOR object through indexSolr() transforms
        '''
        try:
            return actions.solrIndexer.solrIndexer('modifyObject', self.pid, printOnly=True)
        except:
            logging.debug("Could not run indexSolr() transform.")
            return False


    # Solr Indexing
    def index(self, printOnly=False, commit_on_index=False, run_content_type_specific=True):

        # isntantiate SolrHumanHash (ssh) and retrieve currently stored human hash
        shh = models.SolrHumanHash()
        human_hash = shh.retrieve()

        # update Dublin Core
        try:
            self.DCfromMODS()
        except:
            logging.debug("could not re-derive DC from MODS")

        # initialize blank document and set pid
        self.SolrDoc.doc = helpers.BlankObject()
        self.SolrDoc.doc.id = self.pid

        #######################################################################################
        # Bulk of the indexing work on datastreams
        #######################################################################################

        # built-ins from ohandle
        self.SolrDoc.doc.obj_label = self.ohandle.label
        self.SolrDoc.doc.obj_createdDate = "%sZ" % (self.ohandle.created.strftime('%Y-%m-%dT%H:%M:%S.%f'))
        self.SolrDoc.doc.obj_modifiedDate = "%sZ" % (self.ohandle.modified.strftime('%Y-%m-%dT%H:%M:%S.%f'))

        # MODS
        try:
            for each in self.MODS_Solr_flat['fields']['field']:
                try:
                    if type(each['@name']) == unicode:              
                        fname = each['@name']
                        fvalue = each['#text'].rstrip()
                        if hasattr(self.SolrDoc.doc, fname) == False:
                            # create empty list
                            setattr(self.SolrDoc.doc, fname, [])
                        # append to list
                        getattr(self.SolrDoc.doc, fname).append(fvalue)
                except:
                    logging.debug("Could not add %s" % each)
        except:
            logging.debug("Could not find or index datastream MODS")

        # DC
        try:
            for each in self.DC_Solr_flat['fields']['field']:
                try:
                    if type(each['@name']) == unicode:              
                        fname = each['@name']
                        fvalue = each['#text'].rstrip()
                        if hasattr(self.SolrDoc.doc, fname) == False:
                            # create empty list
                            setattr(self.SolrDoc.doc, fname, [])
                        # append to list
                        getattr(self.SolrDoc.doc, fname).append(fvalue)
                except:
                    logging.debug("Could not add %s" % each)
        except:
            logging.debug("Could not find or index datastream DC")

        # RELS-EXT
        try:
            for each in self.RELS_EXT_Solr_flat['fields']['field']:
                try:
                    if type(each['@name']) == unicode:              
                        fname = each['@name']
                        fvalue = each['#text'].rstrip()
                        if hasattr(self.SolrDoc.doc, fname) == False:
                            # create empty list
                            setattr(self.SolrDoc.doc, fname, [])
                        # append to list
                        getattr(self.SolrDoc.doc, fname).append(fvalue)
                except:
                    logging.debug("Could not add %s" % each)
        except:
            logging.debug("Could not find or index datastream RELS-EXT")

        # Add object and datastream sizes
        try:
            logging.debug("indexing object size")
            size_dict = self.object_size()
            setattr(self.SolrDoc.doc, "obj_size_fedora_i", size_dict['fedora_total_size'][0] )
            setattr(self.SolrDoc.doc, "obj_size_fedora_human", size_dict['fedora_total_size'][1] )
            setattr(self.SolrDoc.doc, "obj_size_wsudor_i", size_dict['wsudor_total_size'][0] )
            setattr(self.SolrDoc.doc, "obj_size_wsudor_human", size_dict['wsudor_total_size'][1] )
        except:
            logging.debug("Could not determine object size, skipping")

        # Add list of datastreams as string to dynamic `admin_*` type
        setattr(self.SolrDoc.doc, "admin_datastreams", "|".join(self.ohandle.ds_list.keys()) )


        #######################################################################################
        # Here, we have the opportunity to do some cleanup, addition, and finagling of fields.
        #######################################################################################

        # derive human readable fields, 'human_*'
        collections = getattr(self.SolrDoc.doc, 'rels_isMemberOfCollection', False)
        if collections:
            logging.debug("deriving human collection names")
            logging.debug("%s" % collections)
            human_collections = []
            for pid in collections:
                pid = pid.split("/")[1]
                if pid in human_hash['collections']:
                    human_collections.append(human_hash['collections'][pid])
                else:
                    # udpate human hash, retry
                    logging.debug("Value not found in human_hash, updating in LMDB...")
                    human_hash = shh.update()
                    if pid in human_hash['collections']:
                        human_collections.append(human_hash['collections'][pid])
            # set list
            setattr(self.SolrDoc.doc, "human_isMemberOfCollection", human_collections)


        content_types = getattr(self.SolrDoc.doc, 'rels_hasContentModel', False)
        if content_types:
            logging.debug("deriving human content types")
            logging.debug("%s" % content_types)
            human_content_types = []
            for pid in content_types:
                pid = pid.split("/")[1]
                if pid in human_hash['content_types']:
                    human_content_types.append(human_hash['content_types'][pid])
                else:
                    # udpate human hash, retry
                    logging.debug("Value not found in human_hash, updating in LMDB...")
                    human_hash = shh.update()
                    if pid in human_hash['content_types']:
                        human_content_types.append(human_hash['content_types'][pid])
            # set list
            setattr(self.SolrDoc.doc, "human_hasContentModel", human_content_types)


        #######################################################################################
        # Run content-type specific indexing tasks
        #######################################################################################
        '''
        Content-types have optional `index_augment()` method that expects already started
        self.SolrDoc.doc that it can augment and add to before update
        '''
        if run_content_type_specific:
            if getattr(self,'index_augment',False):
                self.index_augment()


        #######################################################################################
        # Update in Solr
        #######################################################################################
        
        if printOnly == True:
            # print and return dicitonary, but do NOT update, commit, or replicate
            logging.debug("DEBUG: printing only")
            return self.SolrDoc.doc.__dict__

        #dc_title_sorting shim, force 0th value
        if hasattr(self.SolrDoc.doc,'dc_title') and len(self.SolrDoc.doc.dc_title) > 1:
            self.SolrDoc.doc.dc_title = [self.SolrDoc.doc.dc_title[0]]

        # update object, with commit decision based on size of document to insert
        if not commit_on_index:
            if len(str(self.SolrDoc.asDictionary())) > 10000:
                logging.debug("large SolrDoc detected, autocommiting")
                commit_on_index = True
            else:
                logging.debug("small SolrDoc detected, NOT autocommiting")
                commit_on_index = False
        
        result = self.SolrDoc.update(commit=commit_on_index)
        logging.debug("%s" % result.status)
        if result.status == 200:
            return True
        else:
            logging.debug("error indexing, status: %s" % result.status)
            logging.debug("%s" % result.raw_content)
            return False


    def prune(self):
        solr_handle.delete_by_key(self.pid)
        # prune constituents
        if len(self.constituents) > 0:
            for c in self.constituents:
                solr_handle.delete_by_key(c.pid)
        return True


    def add_to_indexer_queue(self, priority=1, username=None, action='index'):
        return IndexRouter.queue_object(self.pid, priority=priority, username=username, action=action)


    def alter_in_indexer_queue(self, action):
        return IndexRouter.alter_queue_action(self.pid, action)        


    # regnerate derivative JP2s
    def regenJP2(self, regenIIIFManifest=False, target_ds=None, clear_cache=True):
        '''
        Function to recreate derivative JP2s based on JP2DerivativeMaker class in inc/derivatives
        Operates with assumption that datastream ID "FOO_JP2" is derivative as datastream ID "FOO"
        '''

        # iterate through datastreams and look for JP2s
        if target_ds is None:
            jp2_ds_list = [ ds for ds in self.ohandle.ds_list if self.ohandle.ds_list[ds].mimeType == "image/jp2" ]
        else:
            jp2_ds_list = [target_ds]

        for i, ds in enumerate(jp2_ds_list):

            logging.debug("converting %s, %s / %s" % (ds,str(i+1),str(len(jp2_ds_list))))

            # jp2 handle
            jp2_ds_handle = self.ohandle.getDatastreamObject(ds)

            # get original ds_handle
            orig = ds.split("_JP2")[0]
            try:
                orig_ds_handle = self.ohandle.getDatastreamObject(orig)
            except:
                logging.debug("could not find original for %s" % orig)

            # write temp original and set as inPath
            guessed_ext = utilities.mimetypes.guess_extension(orig_ds_handle.mimetype)
            logging.debug("guessed extension for temporary orig handle: %s" % guessed_ext)
            temp_orig_handle = Derivative.write_temp_file(orig_ds_handle, suffix=guessed_ext)

            # # gen temp new jp2            
            jp2 = ImageDerivative(temp_orig_handle.name)
            jp2_result = jp2.makeJP2()

            if jp2_result:
                with open(jp2.output_handle.name) as fhand:
                    jp2_ds_handle.content = fhand.read()
                jp2_ds_handle.save()

                # cleanup
                jp2.output_handle.unlink(jp2.output_handle.name)
                temp_orig_handle.unlink(temp_orig_handle.name)
            else:
                # cleanup
                jp2.output_handle.unlink(jp2.output_handle.name)
                temp_orig_handle.unlink(temp_orig_handle.name)
                raise Exception("Could not create JP2")

            # if regenIIIFManifest
            if regenIIIFManifest:
                logging.debug("regenerating IIIF manifest")
                self.genIIIFManifest()

            if clear_cache:
                logging.debug("clearing cache")
                self.removeObjFromCache()

            return True


    def _checkJP2Codestream(self,ds):
        logging.debug("Checking integrity of JP2 with jpylyzer...")

        temp_filename = "/tmp/Ouroboros/%s.jp2" % uuid.uuid4()

        ds_handle = self.ohandle.getDatastreamObject(ds)
        with open(temp_filename, 'w') as f:
            for chunk in ds_handle.get_chunked_content():
                f.write(chunk)

        # wrap in try block to make sure we remove the file even if jpylyzer fails
        try:
            # open jpylyzer handle
            jpylyzer_handle = jpylyzer.checkOneFile(temp_filename)
            # check for codestream box
            codestream_check = jpylyzer_handle.find('properties/contiguousCodestreamBox')
            # remove temp file
            os.remove(temp_filename)
            # good JP2
            if type(codestream_check) == etpatch.Element:
                logging.debug("codestream found")
                return True
            elif type(codestream_check) == None:
                logging.debug("codestream not found")
                return False
            else:
                logging.debug("codestream check inconclusive, returning false")
                return False
        except:
            # remove temp file
            os.remove(temp_filename)
            logging.debug("codestream check inconclusive, returning false")
            return False


    # from Loris
    def _from_jp2(self,jp2):

        '''
        where 'jp2' is file-like object
        '''

        b = jp2.read(1)
        window =  deque([], 4)
        while ''.join(window) != 'ihdr':
            b = jp2.read(1)
            c = struct.unpack('c', b)[0]
            window.append(c)
        height = int(struct.unpack(">I", jp2.read(4))[0]) # height (pg. 136)
        width = int(struct.unpack(">I", jp2.read(4))[0]) # width
        return (width,height)


    # from Loris
    def _extract_with_pillow(self, fp):
        im = Image.open(fp)
        width,height = im.size
        return (width,height)


    def _imageOrientation(self,dimensions):
        if dimensions[0] > dimensions[1]:
            return "landscape"
        elif dimensions[1] > dimensions[0]:
            return "portrait"
        elif dimensions[0] == dimensions[1]:
            return "square"
        else:
            return False


    def _checkJP2Orientation(self,ds):
        logging.debug("Checking aspect ratio of JP2 with Loris")

        # check jp2
        logging.debug("checking jp2 dimensions...")
        ds_url = '%s/objects/%s/datastreams/%s/content' % (localConfig.REMOTE_REPOSITORIES['local']['FEDORA_ROOT'], self.pid, ds)
        logging.debug("%s" % ds_url)
        uf = urlopen(ds_url)
        jp2_dimensions = self._from_jp2(uf)
        logging.debug("JP2 dimensions:", jp2_dimensions, self._imageOrientation(jp2_dimensions))

        # check original
        logging.debug("checking original dimensions...")
        ds_url = '%s/objects/%s/datastreams/%s/content' % (localConfig.REMOTE_REPOSITORIES['local']['FEDORA_ROOT'], self.pid, ds.split("_JP2")[0])
        logging.debug("%s" % ds_url)
        uf = urlopen(ds_url)
        orig_dimensions = self._extract_with_pillow(uf)
        logging.debug("Original dimensions: %s %s" % (orig_dimensions, self._imageOrientation(orig_dimensions)))

        if self._imageOrientation(jp2_dimensions) == self._imageOrientation(orig_dimensions):
            logging.debug("same orientation")
            return True
        else:
            return False


    def _checkJP2OrientationAndSize(self, ds):
        logging.debug("Checking aspect ratio and size of %s with Loris" % ds)

        # check jp2
        logging.debug("checking jp2 dimensions...")
        ds_url = '%s/objects/%s/datastreams/%s/content' % (localConfig.REMOTE_REPOSITORIES['local']['FEDORA_ROOT'], self.pid, ds)
        logging.debug("%s" % ds_url)
        uf = urlopen(ds_url)
        jp2_dimensions = self._from_jp2(uf)
        logging.debug("JP2 dimensions: %s %s" % (jp2_dimensions, self._imageOrientation(jp2_dimensions)))

        # check original
        logging.debug("checking original dimensions...")
        ds_url = '%s/objects/%s/datastreams/%s/content' % (localConfig.REMOTE_REPOSITORIES['local']['FEDORA_ROOT'], self.pid, ds.split("_JP2")[0])
        logging.debug("%s" % ds_url)
        uf = urlopen(ds_url)
        orig_dimensions = self._extract_with_pillow(uf)
        logging.debug("Original dimensions: %s %s" % (orig_dimensions, self._imageOrientation(orig_dimensions)))

        # check orientation
        tests = True
        if self._imageOrientation(jp2_dimensions) == self._imageOrientation(orig_dimensions):
            logging.debug("same orientation")
            tests = True
        else:
            tests = False

        # check size
        if jp2_dimensions == orig_dimensions:
            logging.debug("same size")
            tests = True
        else:
            tests = False

        # return tests
        return tests


    # regnerate derivative JP2s
    def checkJP2(self, regenJP2_on_fail=True, tests=['all']):

        '''
        Function to check health and integrity of JP2s for object
        Uses jpylyzer library
        '''

        checks = []

        # iterate through datastreams and look for JP2s
        jp2_ds_list = [ ds for ds in self.ohandle.ds_list if self.ohandle.ds_list[ds].mimeType == "image/jp2" ]

        for i,ds in enumerate(jp2_ds_list):

            logging.debug("checking %s, %s / %s" % (ds,i,len(jp2_ds_list)))

            # check codesteram present
            if 'all' in tests or 'codestream' in tests:
                checks.append( self._checkJP2Codestream(ds) )

            # check aspect ratio
            if 'all' in tests or 'orientation' in tests:
                checks.append( self._checkJP2OrientationAndSize(ds) )

            logging.debug("Final checks: %s" % checks)

            # if regen on check fail
        if regenJP2_on_fail and False in checks:
            self.regenJP2(regenIIIFManifest=True, target_ds=ds)


    def fixJP2(self):

        '''
        Use checkJP2 to check, fire JP2 if bad
        '''

        logging.debug("Checking integrity of JP2 with jpylyzer...")

        if not self.checkJP2():
            self.regenJP2()


    # remove object from Loris, Varnish, and other caches
    def removeObjFromCache(self):

        results = {}

        # remove from Loris
        results['loris'] = self._removeObjFromLorisCache()

        # remove from Varnish
        results['varnish'] = self._removeObjFromVarnishCache()

        # return results dictionary
        return results


    # ban image from varnish cache
    def _removeObjFromVarnishCache(self):

        # main pid
        os.system('varnishadm -S /etc/varnish/secret -T localhost:6082 "ban req.url ~ %s"' % self.pid)

        # check constituents
        if len(self.constituents) > 0:
            for constituent in self.constituents:
                os.system('varnishadm -S /etc/varnish/secret -T localhost:6082 "ban req.url ~ %s"' % constituent.pid)

        return  True


    # remove from Loris cache
    def _removeObjFromLorisCache(self):

        for ds in self.ohandle.ds_list:
            self._removeDatastreamFromLorisCache(self.pid, ds)

        # check constituents        
        if len(self.constituents) > 0:
            for constituent in self.constituents:
                try:
                    for ds in constituent.ds_list:
                        self._removeDatastreamFromLorisCache(constituent.pid, ds)
                except:
                    logging.debug("could not remove constituent %s from cache, possible already purged" % constituent)

        return True


    # remove from Loris cache
    def _removeDatastreamFromLorisCache(self, pid, ds):

        '''
        As we now use Varnish for caching tiles and client<->Loris requests,
        we cannot ascertain as well the file path of the Loris<->Fedora cache.

        Now, requires datastream to purge from cache.
        '''

        logging.debug("Removing object from Loris caches...")

        # read config file for Loris
        data = StringIO.StringIO('\n'.join(line.strip() for line in open('/etc/loris2/loris2.conf')))
        config = ConfigParser.ConfigParser()
        config.readfp(data)

        # get cache location(s)
        image_cache = config.get('img.ImageCache','cache_dp').replace("'","")
        if image_cache.endswith('/'):
            image_cache = image_cache[:-1]

        # craft ident
        ident = "fedora:%s|%s" % (pid, ds)

        # clear from fedora resolver cache
        try:
            logging.debug("removing instance: %s" % ident)
            file_structure = ''
            ident_hash = hashlib.md5(quote_plus(ident)).hexdigest()
            file_structure_list = [ident_hash[0:2]] + [ident_hash[i:i+3] for i in range(2, len(ident_hash), 3)]
            for piece in file_structure_list:
                file_structure = os.path.join(file_structure, piece)
                final_file_structure = "%s/fedora/wayne/%s" % ( image_cache, file_structure )
            logging.debug("removing dir: %s" % final_file_structure)
            shutil.rmtree(final_file_structure)
            return True
        except:
            logging.debug("could not remove from fedora resolver cache")
            return False


    # refresh object
    def refresh(self):

        '''
        Method to refresh object.  Default behavior includes:
            - queue for indexing in Solr
            - removing from Varnish cache
            - calculating object size

        Additionally, content-types may run additional refresh activities under an optional
        content-type specific method: self.refresh_content_type

        '''
        
        logging.debug("-------------------- firing objectRefresh --------------------")

        # update object size in Solr
        self.object_size(update_self=True, update_constituents=True)

        # remove object from Loris cache
        self.removeObjFromCache()

        # check for object type specific tasks
        if getattr(self, 'refresh_content_type', False):
            self.refresh_content_type()

        # finally, (re)index in Solr
        self.add_to_indexer_queue()

        return True


    # method to send object to remote repository
    def sendObject(self, 
        dest_repo, 
        export_context='archive', 
        overwrite=False, 
        show_progress=False, 
        refresh_remote=False, 
        omit_checksums=True, 
        skip_constituents=False, 
        refresh_remote_constituents=False):

        '''
        dest_repo = string key from localConfig for remote repositories credentials
        '''

        # handle string or eulfedora handle
        logging.debug("%s %s" % (dest_repo,type(dest_repo)))
        if type(dest_repo) == str or type(dest_repo) == unicode:
            dest_repo_handle = fedoraHandles.remoteRepo(dest_repo)
        elif type(dest_repo) == eulfedora.server.Repository:
            dest_repo_handle = dest_repo
        else:
            logging.debug("destination eulfedora not found, try again")
            return False
            
        # generate list of objects to send
        '''
        This is important if objects have constituent objects, need to send them too
        '''
        
        # init list
        sync_list = [self.pid]
        
        # if not skipping constituents, check for them
        if not skip_constituents:
            constituents = fedora_handle.risearch.spo_search(None, "fedora-rels-ext:isConstituentOf", "info:fedora/%s" % self.pid)
            if len(constituents) > 0:
                for constituent in constituents:
                    # add to sync list
                    logging.debug("adding %s to sync list" % constituent[0])
                    sync_list.append(constituent[0].split("/")[-1])
                    
        # iterate and send
        for i,pid in enumerate(sync_list):
            logging.debug("sending %s, %d/%d..." % (pid, i+1, len(sync_list)))

            # remove IIIF manifest
            logging.debug("removing IIIF Manifest before transfer")
            fedora_handle.api.purgeDatastream(self.ohandle,'IIIF_MANIFEST')

            # use syncutil
            result = syncutil.sync_object(
                fedora_handle.get_object(pid),
                dest_repo_handle,
                export_context=export_context,
                overwrite=overwrite,
                show_progress=show_progress,
                omit_checksums=omit_checksums)
                
        # refresh remote objects
        # refresh object in remote repo (requires refreshObject() method in remote Ouroboros)
        if type(dest_repo) == str or type(dest_repo) == unicode:
            
            # indexing both
            if refresh_remote and refresh_remote_constituents:
                for i,pid in enumerate(sync_list):
                    logging.debug("refreshing remote object in remote repository %s, %d/%d..." % (pid, i+1, len(sync_list)))
                    refresh_remote_url = '%s/tasks/objectRefresh/%s' % (localConfig.REMOTE_REPOSITORIES[dest_repo]['OUROBOROS_BASE_URL'], pid)
                    logging.debug("%s" % refresh_remote_url)
                    r = requests.get( refresh_remote_url )
                    logging.debug("%s" % r.content)
            
            # index self pid only
            elif refresh_remote and not refresh_remote_constituents:
                logging.debug("refreshing remote object in remote repository %s, 1/1..." % (self.pid))
                refresh_remote_url = '%s/tasks/objectRefresh/%s' % (localConfig.REMOTE_REPOSITORIES[dest_repo]['OUROBOROS_BASE_URL'], self.pid)
                logging.debug("%s" % refresh_remote_url)
                r = requests.get( refresh_remote_url )
                logging.debug("%s" % r.content)
                
            else:
                logging.debug("skipping remote refresh")
                
        # cannot refresh
        else:
            logging.debug("Cannot refresh remote.  It is likely you passed an Eulfedora Repository object.  To refresh remote, please provide string of remote repository that aligns with localConfig")



    # enrich metadata from METS file
    def enrichMODSFromMETS(self, METS_handle, DMDID_prefix="UP00", auto_commit=True):

        '''
        1) read <mods:extension>/<orig_filename>
        2) look for DMDID_prefix + orig_filename
        3) if found, grab MODS from METS
        4) update object MODS
        5) recreate <mods:extension>/<orig_filename> if lost
        '''

        # METS root
        METS_root = METS_handle.getroot()

        # MODS handle
        MODS_handle = self.ohandle.getDatastreamObject('MODS')

        # 1) read <mods:extension>/<orig_filename>
        orig_filename = MODS_handle.content.node.xpath('//mods:extension/orig_filename', namespaces=METS_root.nsmap)
        logging.debug("%s" % orig_filename)
        if len(orig_filename) == 1:
            orig_filename = orig_filename[0].text
        elif len(orig_filename) > 1:
            logging.debug("multiple orig_filename elements found, aborting")
            return False
        elif len(orig_filename) == 0:
            logging.debug("no orig_filename elements found, aborting")
            return False
        else:
            logging.debug("could not determine orig_filename")
            return False

        '''
        Need to determine if orig_filename ends with file extension, which we would strip
        or is other.

        Probably safe to assume that file extensions are not *entirely* numbers, which the following
        checks for.
        '''

        # check if orig_filename contains file extension, if so, strip
        full_orig_filename = orig_filename
        parts = orig_filename.split('.')
        try:
            int(parts[-1])
            file_ext_present = False
            logging.debug("assuming NOT file extension - keeping orig_filename")
        except:
            file_ext_present = True
            logging.debug("assuming file extension present - stripping")
            orig_filename = ".".join(parts[:-1])


        # 2) look for DMDID_prefix + orig_filename
        dmd = METS_root.xpath('//mets:dmdSec[@ID="%s%s"]' % (DMDID_prefix, orig_filename), namespaces=METS_root.nsmap)
        logging.debug("%s" % dmd)
        if len(dmd) == 1:
            logging.debug("one DMD section found!")
        elif len(dmd) > 1:
            logging.debug("multiple DMD sections found, aborting")
            return False
        elif len(dmd) == 0:
            logging.debug("no DMD sections found, aborting")
            return False


        # 3) if found, grab MODS from METS
        enriched_MODS = dmd[0].xpath('.//mods:mods',namespaces=METS_root.nsmap)
        logging.debug("%s" % enriched_MODS)
        if len(enriched_MODS) == 1:
            logging.debug("MODS found")
        elif len(enriched_MODS) > 1:
            logging.debug("multiple MODS found, aborting")
            return False
        elif len(enriched_MODS) == 0:
            logging.debug("no MODS found, aborting")
            return False


        # 4) update object MODS
        MODS_handle.content = etree.tostring(enriched_MODS[0])
        MODS_handle.save()


        # 5) recreate <mods:extension>/<orig_filename> if lost (taken from MODS export)
        logging.debug("ensuring that <orig_filename> endures")

        # reinit MODS and ohandle
        self.ohandle = fedora_handle.get_object(self.pid)
        MODS_handle = self.ohandle.getDatastreamObject('MODS')

        # does <PID> element already exist?
        orig_filename = MODS_handle.content.node.xpath('//mods:extension/orig_filename', namespaces=MODS_handle.content.node.nsmap)

        # if not, continue with checks
        if len(orig_filename) == 0:

            # check for <mods:extension>, if not present add
            extension_check = MODS_handle.content.node.xpath('//mods:extension', namespaces=MODS_handle.content.node.nsmap)

            # if absent, create with <PID> subelement
            if len(extension_check) == 0:
                #serialize and replace
                MODS_content = MODS_handle.content.serialize()
                # drop original full filename back in here
                MODS_content = MODS_content.replace("</mods:mods>","<mods:extension><orig_filename>%s</orig_filename></mods:extension></mods:mods>" % full_orig_filename)

            # <mods:extension> present, but no PID subelement, create
            else:
                orig_filename_elem = etree.SubElement(extension_check[0],"orig_filename")
                orig_filename_elem.text = full_orig_filename
                #serialize
                MODS_content = MODS_handle.content.serialize()

        # overwrite with PID
        else:
            orig_filename_elem = orig_filename[0]
            orig_filename_elem.text = full_orig_filename

            #serialize
            MODS_content = MODS_handle.content.serialize()

        # finall, write content back to MODS
        MODS_handle.content = MODS_content
        MODS_handle.save()



    # add isSensitive relationship
    def isSensitive(self):
        '''
        Function to add isSensitive relationship to Object in Fedora.
        A quick way to handle objects flagged internally or externally for having initially shocking material
        '''

        # Check if to see that doesn't have sensitive flag
        s = list(self.ohandle.risearch.get_objects(self.ohandle.uri,'http://digital.library/.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isSensitive'))
        if not s:
            # else
            self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isSensitive","True")
            self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isSensitiveContent","True")
        return True


    # add OAI identifers and set memberships
    def registerOAI(self):
        # generate OAI identifier
        logging.debug("%s" % self.ohandle.add_relationship("http://www.openarchives.org/OAI/2.0/itemID", "oai:digital.library.wayne.edu:%s" % (self.pid)))
        logging.debug("created OAI identifier")

        # affiliate with collection set(s)
        try:
            collections = self.isMemberOfCollections
            for collection in collections:
                logging.debug("%s %s" % (self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet", collection)))
                logging.debug("registered with collection %s" % collection)
        except:
            logging.debug("could not affiliate with collection")


    # add OAI identifers and set memberships
    def deregisterOAI(self):
        logging.debug("deregistering from OAI exposure")
        logging.debug("%s" % self.ohandle.purge_relationship("http://www.openarchives.org/OAI/2.0/itemID", "oai:digital.library.wayne.edu:%s" % (self.pid)))

        # affiliate with collection set(s)
        try:
            collections = self.isMemberOfCollections
            for collection in collections:
                logging.debug("%s %s" % (self.ohandle.purge_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet", collection)))
                logging.debug("deregistered with collection %s" % collection)
        except:
            logging.debug("could not de-affiliate with collection")


    # send Object to Problem Object staging space (i.e. in user_pids table)
    def reportProb(self, data):
        try:
            probData = dict(data)
            PID = probData['pid']
            probData.pop('pid')
            probData.pop('to')
            probData['from'] = probData.pop('from')
            probData['name'] = probData.pop('name')
            probData['message'] = probData.pop('msg')
            form_notes = json.dumps(probData)
            problemPID = models.user_pids(PID,"problemBot",1,"userReportedPIDs",form_notes)
            db.session.add(problemPID)
            db.session.commit()
            response = True
        except:
            response = False

        return response


    # purge object
    def purge(self, override_state=False):

        if self.ohandle.state != "D" and override_state == False:
            raise Exception("Skipping, object state not 'Deleted (D)'")

        else:

            # purge constituent objets
            logging.debug("purging Constituents if present")
            if getattr(self, 'purgeConstituents', None):
                self.purgeConstituents()

            # purge Readux virtual objects if present
            if hasattr(self, 'purgeReaduxVirtualObjects'):
                self.purgeReaduxVirtualObjects()

            # remove from Loris and Varnish cache
            self.removeObjFromCache()

            # remove from Solr
            logging.debug("purging from solr")
            solr_handle.delete_by_key(self.pid)

            # purge object
            logging.debug("purging from fedora")
            fedora_handle.purge_object(self.pid)

            return True


    # default previewImage return
    def previewImage(self):

        '''
        Return image/loris params for API to render
            - pid, datastream, region, size, rotation, quality, format
        '''
        return (self.pid, 'PREVIEW', 'full', 'full', 0, 'default', 'jpg')


    # return object hierarchy
    def object_hierarchy(self, overwrite=False):

        '''
        Returns object hierarchy from models.ObjHierarchy
        '''
        return models.ObjHierarchy(self.pid, self.SolrDoc.asDictionary()['dc_title'][0]).load_hierarchy(overwrite=overwrite)


    # return timeline
    def timeline(self):

        # closure to organize the timeline creation process
        def _initialize_timeline(self):
            # get dates
            initial_ingest = str(fedora_handle.get_object(self.pid).getProfile().created)
            fedora = str(fedora_handle.get_object(self.pid).getProfile().modified)
            search_string = "id:" + self.pid.replace(":", "\:")
            solr = solr_handle.search(**{"q": search_string}).documents[0]['solr_modifiedDate']
            varnish = urlopen("https://" + localConfig.PUBLIC_HOST + "/item/" + self.pid, context=ssl._create_unverified_context()).headers['date']
            # standardize dates
            initial_ingest = parser.parse(initial_ingest)
            fedora = parser.parse(fedora)
            solr = parser.parse(solr)
            varnish = parser.parse(varnish)
            # organize dates
            timeline = [("initial_ingest", initial_ingest), ("fedora", fedora), ("solr", solr), ("varnish", varnish)]
            # sort list of tuples according to each second tuple value (aka timestamp)
            timeline = sorted(timeline, key=lambda x: x[1])

            return timeline

        # Make the dates a bit more human readable
        def _make_human_readable(timeline):
            human_readable_dates = []
            human_readable_names = []

            def i():
                return "Ingested into Fedora Commons"

            def f():
                return "Last Modified in Fedora"

            def s():
                return "Indexed in Solr"

            def v():
                return "Cached in Varnish"

            names = {"initial_ingest": i,
                     "fedora": f,
                     "solr": s,
                     "varnish": v, }

            for each in timeline:
                human_readable_dates.append((each[0], each[1].ctime()))
                human_readable_names.append((names[each[0]](), each[1].ctime()))

            human_readable = {'events': human_readable_dates, 'human': human_readable_names}
            return human_readable

        # check order and let us know if it's as it should be
        def _check_order(timeline):
            preferred_order = [("initial_ingest", 0), ("fedora", 1), ("solr", 2), ("varnish", 3)]
            actual_order = timeline['events']
            order = [x[0] for x, y in zip(preferred_order, actual_order) if x[0] == y[0]]
            if order == ['initial_ingest', 'fedora', 'solr', 'varnish']:
                health = True
                message = "Nothing to Report. Everything looks good."
            else:
                health = False
                message = "Something is amiss. Cache or index might need to be updated."

            # append messages
            timeline = {"events": actual_order, "healthy": health, "message": message, 'human': timeline['human']}
            return timeline

        # PREMIS -- future work to add the ability to convert and append PREMIS events to the timeline
        # def _append_Premis_events(timeline):

        # make basic timeline structure
        timeline = _initialize_timeline(self)

        # handle the formatting of the dates so it's more human readable and also make a front-end ready data set
        human_readable = _make_human_readable(timeline)

        # check order
        checked = _check_order(human_readable)

        # output activity dates for fedora, solr, and varnish along with a message about caching/indexing status
        return checked


    # Cache object
    def cacheInVarnish(self, remove_from_cache=True, targets=['thumbnail','item_page']):
        
        # return dict
        stime = time.time()
        return_dict = {}

        # remove from varnish cache
        if remove_from_cache:
            logging.debug("removing object from varnish cache")
            return_dict['remove'] = self._removeObjFromVarnishCache()
        
        # recache
        if 'item_page' in targets:
            logging.debug("caching item page in varnish")
            r = requests.get("https://%s/item/%s" % (localConfig.PUBLIC_HOST, self.pid))
            return_dict['item_page'] = r.headers
        if 'thumbnail' in targets:
            logging.debug("caching thumbnail in varnish")
            r = requests.get("https://%s/item/%s/thumbnail" % (localConfig.PUBLIC_HOST, self.pid))
            return_dict['thumbnail'] = r.headers
        
        # return
        return_dict['elapsed'] = time.time()-stime
        return return_dict


    ################################################################
    # Consider moving
    ################################################################
    # derive DC from MODS
    def DCfromMODS(self, print_only=False):

        # retrieve MODS
        MODS_handle = self.ohandle.getDatastreamObject('MODS')
        XMLroot = etree.fromstring(MODS_handle.content.serialize())

        # transform downloaded MODS to DC with LOC stylesheet
        logging.debug("XSLT Transforming: %s" % (self.pid))
        # Saxon transformation
        XSLhand = open('inc/xsl/MODS_to_DC.xsl','r')
        xslt_tree = etree.parse(XSLhand)
        transform = etree.XSLT(xslt_tree)
        DC = transform(XMLroot)

        # scrub duplicate, identical elements from DC
        DC = utilities.delDuplicateElements(DC)

        # save to DC datastream
        if not print_only:          
            DS_handle = self.ohandle.getDatastreamObject("DC")
            old_DC = DS_handle.content
            # only update if different:
                # do here
            DS_handle.content = str(DC)
            derive_results = DS_handle.save()
            logging.debug("DCfromMODS result: %s" % derive_results)
            return derive_results

        else:
            return str(DC)


    # regen RDF
    def regenRDF(self):

        '''
        Why is this needed?

        Eulfedora has the potential for interacting with RDF -- via the RELS-EXT and RELS-INT datastreams -- in a couple of different ways.
            
            1) using the native Fedora REST API
                - e.g. fedora_handle.api.addRelationship()
                - does NOT create namespace prefixes, but embeds each predicate namespace in the triple
                - THIS IS THE STYLE WE USE

            2) interacting with the RELS-EXT relationships as a graph, via python's rdflib
                - object.rels_ext.content is a RDFLib graph object
                - firing object.rels_ext.content.save() rewrites the RELS-EXT datastream with namespace prefixes

            While both are valid, and the system generally responds to both formats equally, it hurts processes downstream that don't expect prefixes if the second style fires for any reason.  At the time of this writing, the Readux Virtual Objects *do* use the second style, but they are somewhat isolated and unique, that might be okay.

            This WSUDOR object method, regardless of which style the RELS-EXT is currently serialized as, will take the triples and re-write them as "styles #1", with no prefixes, that is used across Ouroboros.
        '''

        triples = self.rdf_triples

        # purge all
        logging.debug("PURGING ALL RELATIONSHIPS")
        for triple in triples:
            logging.debug("%s" % str(triple))
            if type(triple[2]) == rdflib.term.Literal:
                isLit = True
            else:
                isLit = False
            self.ohandle.api.purgeRelationship(self.ohandle, *triple, isLiteral=isLit)
        
        # re-add
        logging.debug("RE-ADDING ALL RELATIONSHIPS")
        for triple in triples:
            logging.debug("%s" % str(triple))
            if type(triple[2]) == rdflib.term.Literal:
                isLit = True
            else:
                isLit = False
            self.ohandle.api.addRelationship(self.ohandle, *triple, isLiteral=isLit)


    # In truth, this method is about identifying what datastreams are versioned and worthy of preservation and what's not (aka derivatives, etc).
    # It's also a handy list method you can use without diving into eulfedora's ohandle.ds_list method, and is also a bit more curated data set than ohandle.ds_list
    def wsudor_ds_list(self):

        # get all the original datastreams from ObjMeta
        dsList = []
        for ds in self.objMeta['datastreams']:
            dsList.append({'id':ds['ds_id'], 'role':'preserved'})

        # There are usually datastreams that are needed from each specific object according to content type
        if hasattr(self, 'uniqueVersionableDatastreams'):
            dsList.append(self.uniqueVersionableDatastreams())

        # and then some loose ones that ObjMeta nevers picks up, like the MODS datastream
        dsList.append({'id':'MODS', 'role':'preserved'})
        dsList.append({'id':'RELS-EXT', 'role':'preserved'})
        dsList.append({'id':'RELS-INT', 'role':'preserved'})

        # now let's add all the other datastreams that are derivatives, etc, and are going to be versioned
        allDS = self.ohandle.ds_list
        for key in allDS.iterkeys():
            if not any(d['id'] == key for d in dsList):
                dsList.append({'id':key, 'role':'derivative'})

        return dsList











