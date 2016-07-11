Views
=========
Handles all the routing of requests through WSUDOR_Manager flask app. When using web interface, requires login to use (handled by the ```@login_required``` decorator).  Redirects you to ```/userPage``` when successfully authenticated.

Major sub-sections
```/contentModels```
```MODSedit```
```/datastreamManagement```
```/objectManagement```
```/WSUDORManagement```

/contentModels
---------------------
Links to list of all current and some future objects models accepted in Fedora/Ouroboros. Some description of content models under each heading.

/MODSedit
-------------
Series of MODS editing abilities. MODS is the primary descriptive datastream for our Fedora objects; Dublin Core (DC) -- required by Fedora -- can be derived from MODS here, as well.

 - Batch import/export
	 - [```/tasks/MODSexport```](WSUDOR_Manager/actions/MODSexport)
 - Find and replace MODS
 	 - [```/tasks/editDSRegex```](WSUDOR_Manager/actions/editDSRegex)
 - Derive Dublin Core
	 - [```/tasks/DCfromMODS```](WSUDOR_Manager/actions/DCfromMODS)

/objectManagement
------------------------
Bulk object handler.



Miscellaneous
------------------

###**Page Searcher**

Page searcher is an effort to make the many pages of Ouroboros more easily found. Instead of clicking through numerous levels of links, you can search for the name of the page in a search box. Found in the header, this box is powered by an ajax call that asks /routeIndexer for a curated list of urls. This data is then stored in HTML5 local storage to cut down on extraneous queries. Note: adding a new page/route will require you to clear local storage object to update search box.

#### **Delete local storage search index**
```localStorage.removeItem("pageSearch");```

Found under ```routeIndexer()``` in [views.py](WSUDOR_Manager/views.py), the searcher indexer is powered by ```app.url_map``` which is an automatically created index of all routes specified in the Flask app. After retrieval, the route index is curated and pushed as JSON back to ajax, where it is parsed and displayed.