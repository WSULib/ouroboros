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

### Search

### Users

**Root / Identify**<br>
  * `/user/[USERNAME]/whoami`
  * *Method*: `GET`
  * *Description*:
    * Expects `USERNAME`, then checks Ouroboros's user database
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
http://HOST/api/search?q=obj_modifiedDate:[NOW-1MONTH TO NOW]
```

















