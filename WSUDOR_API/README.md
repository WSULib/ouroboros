## WSUDOR API



### Architecture

`WSUDOR_API` is an umbrella Flask app (specifically, `WSUDOR_API_app` as initialized in `/WSUDOR_API/__init__.py`) for for various versions of the API ecosystem.  Each version is responsible for "registering" its various views, routes, and handlers, in the form of Flfask **blueprints** with `WSUDOR_API_app`.

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

