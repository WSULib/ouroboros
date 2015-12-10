Ouroboros
========

Goal:
"Given an instance of Fedora Commons and Apache Solr, and a front-end interface capable of communicating with an HTTP / JSON API, the goal of this middleware is to be capable of ingesting objects, managing their preservation, and providing access, with minimal configuration to the applications it glues together. It does this by imposing descriptive and structural conventions for objects, and chaining disparate tasks together in a way that effectively unites these content-agnostic systems."

Digital Collections Infrastructure
<img src="https://dl.dropboxusercontent.com/u/41044/digital_collections_infrastructure_7-17_wgraph_tri.png"/>

## Installation

### Dependencies

* OS dependencies
 * `apt-get install libxml2-dev libxslt1-dev python-dev`
* python modules 
 * `pip install requirements.txt`
* Redis
 * `apt-get install redis-server`
* Add supervisor task to supervisor (sample below)
 * <pre><code>[program:Ouroboros]
command=python runserver.py
directory=/opt/ouroboros
# command=/etc/init.d/ouroboros start
autostart=true
autorestart=true
stderr_logfile=/var/log/ouroboros.err.log
stdout_logfile=/var/log/ouroboros.out.log
startsecs=20</code></pre>