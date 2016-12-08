# WSUDOR API

## Architecture

`WSUDOR_API` is an umbrella Flask app (specifically, `WSUDOR_API_app` as initialized in `/WSUDOR_API/__init__.py`) for various versions of the API ecosystem.  Each version is responsible for "registering" its various views, routes, and handlers, in the form of Flfask **blueprints** with `WSUDOR_API_app`.

Here is a general outline of the directory structure of `WSUDOR_API`:
```
├── __init__.py
├── __init__.pyc
├── README.md
├── v1
│   ├── __init__.py
│   ├── ...
│   └── ...
└── v2    
│   ├── __init__.py
│   ├── ...    
│   └── ...
```

The `init` file in each version directory imports and registers its associated it various blueprints with the umbrella `WSUDOR_API_app`. This has multiple benefits:

* `/WSUDOR_API/__init__.py` is kept relatively simple, agnostic of version quirks
* each version sets its prefix, based on `WSUDOR_APP_PREFIX` from `localConfig`, and the `API_VERSION` number that accompanies each version `init` file.

**Note:** Flask blueprint names cannot be duplicated, even across different versions.  This could be rectified by giving them a dynamic name, but for the time being, we're going with the convention, `bitStream_blueprint_v1`, `bitStream_blueprint_v2`, etc.

## Routes

### Generic

**Root / Identify**<br>
  * *url*: `/`
  * *Method*: `GET`
  * *Description*:
    * General information about the API, links to documentation

### Items

**Single Item metadata**<br>
  * *url*: `/api/item/<pid>`
  * *Method*: `GET`
  * *Description*:
    * returns all metadata needed to render front-end view, including:
      * Solr document
      * what collections it belongs to
      * hiearchical relationships
      * related learning objects
      * etc.

**Streaming file from Item**

  * *url*: `/api/item/<pid>/file/<datastream>`
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










