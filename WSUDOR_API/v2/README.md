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

### Search

### Users

**Root / Identify**<br>
  * `/user/[USERNAME]/whoami`
  * *Method*: `GET`
  * *Description*:
    * Accepts username, checks Ouroboros's user database, returns information if found (username, Ouroboros roles, etc.)
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


















