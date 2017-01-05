# API v2 Documentation

## Routes

### Generic

**Root / Identify**<br>
  * `/`
  * *Method*: `GET`
  * *Description*:
    * General information about the API, links to documentation

### Items

**Single Item metadata**<br>
  * `/api/item/<pid>`
  * *Method*: `GET`
  * *Description*:
    * returns all metadata needed to render front-end view, including:
      * Solr document
      * what collections it belongs to
      * hiearchical relationships
      * related learning objects
      * etc.

**Streaming file from Item**

  * `/api/item/<pid>/file/<datastream>`
  * *Method*: `GET`
  * *Parameters*:
    * `key=SECRET_KEY`
      * Defined in `localConfig.py`, this key will allow access and token generation
    * `token=abcd1234` or `token=request`
      * If set to `request`, response will be `JSON` and include tokens for future, one-use downloads.  These tokens are stored in Redis, and revoked after one use.
      * If set as actual token, will result in access / download of file
    * `download=true`
      * If set to `true`, will set download headers
  * *Description*:
    * Streams file from digital object
    * Accepts `key` parameter

### Collections

**All Collections metadata**<br>
  * `/collections`
  * *Method*: `GET`
  * *Description*:
    * returns metadata about all collections

**Single Collection metadata**<br>
  * `/collection/<pid>`
  * *Method*: `GET`
  * *Description*:
    * returns metadata about a single collection

**Search within a collection**<br>
  * `/collection/<pid>/search`
  * *Method*: `GET`
  * *Description*:
    * performs a normal search (with same syntax), confined to items within a given collection

### Search

**Search**<br>
  * `/search?[args]`
  * *Method*: `GET`
  * *Description*:
    * Generic, full search endpoint.
    * Responds to quite a few get parameters, including the following and their defaults:
      * `q`: `*:*`
        * accepts string query, with optional advanced solr syntax
        * escape special characters (see below)
      * `sort`: None
        * order to sort by, can provide name of solr field such as `dc_date`
      * `start`: 0
        * cursor for return, page 3 with 10 results per page would be `20`
      * `rows`: 10
        * how many records to return per page
      * `fq`: `[]``
        * **repeatable**
        * filter query: used primarily for facets, or otherwise refining search
      * `fl`: `[ "id", "mods*", "dc*", "rels*", "obj*", "last_modified"]`
        * **repeatable**
        * solr fields to return in response
        * e.g. to override and return only PIDs of items, `fl=id`
      * `facet`: `false`
        * whether or not to include facets
      * `facet.mincount`: `1`
        * minimum number of documents that satisfy facet to be returned in facets
      * `facet.limit`: `-1`
        * number of facets per solr field returned (`-1` is unlimited)
      * `facet.field`: `[]`
        * **repeatable**
        * solr fields to return as facets 
      * `wt`: `json`
        * format for solr response, options include: `json`, `xml`, `csv`, and more
      * `skip_defaults`: `false`
        * If true, all defaults suggested here are removed, sets solr parameters to basically nothing.  Not recommended save advanced queries
      * `field_skip_escape`: `false` 
        * **repeatable**
        * accepts specific solr field to escape, e.g. `field_skip_escape:q` would escape only the `q` field in the query, while `field_skip_escape:q&field_skip_escape:fq` would escape all `fq` as well.



### Users

**Root / Identify**<br>
  * `/user/<username>/whoami`
  * *Method*: `GET`
  * *Description*:
    * Expects `username`, then checks Ouroboros's user database
      * if found, returns `200` status and information about user, including roles
      * else, returns `404` status and `exists=False`
  * *Sample response*:<br>
```
{
    header: {
        api_response_time: 0.0012500286102294922
    },
    response: {
        exists: true,
        roles: "admin,metadata",
        username: "foobar"
    }
}
```

### Search

In a general sense, search is performed by querying Solr.  This is performed with the python binding, [mysolr](https://pypi.python.org/pypi/mysolr/) (which, ominously, appears to be deprecated as of 1/5/2016).

#### Character Escaping

Querying solr for the diverse range of possible query strings, coupled with particular characters and syntax for more advanced queries, makes for some complexity with regards to character escaping.  Solr uses the following special characters for query syntax: `+ - && || ! ( ) { } [ ] ^ " ~ * ? : \`.  However, it's possible -- likely -- that these will end up in query strings as well.

Because this API powers multiple search interfaces, of which we have little control over the incoming search strings, first priority is to make sure the vast majority of queries perform successfully.  To this end, queries containg the special characters above are escaped with some helper functions in [utilities.py](utilities.py).

However, using these special characters for advanced Solr searching is still possible through the API by including the flag, `skip_escape=true` in an API call.  This skips escaping, and trundles through exactly as entered.  The only catch, the client is required to manually escape any strings themselves.

e.g. to search the `id` field for the PID, `wayne:vnc14515` would have the following syntax:

```
http://HOST/api/search?q=id:wayne\:vmc14515&skip_escape=true
```

This opens up the door for quite advanced queries such as date ranges for when the object was created (ingested) in WSUDOR:

```
http://HOST/api/search?q=obj_modifiedDate:[NOW-1MONTH TO NOW]&skip_escape=true
```

















