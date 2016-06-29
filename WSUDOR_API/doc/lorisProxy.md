# lorisProxy

Proxy for Loris server that puts a middleware between the Loris API and our own internal API.  

Why?  This was we can catch objects and datastreams, and determine what kind of size or access restrictions (if any) may exist.  Particularly, more complex RDF queries of Fedora objects.

The order of operations is as follows:
<pre><code>Client Loris Request (e.g. http://server/loris/image_id/full/full/0/default.jpg) --> Apache
Apache Reverse Proxy --> WSUAPI's lorisProxy
lorisProxy python requests --> Loris server
Loris server --> stream back to lorisProxy
lorisProxy stream return  --> reverse proxy through Apache
--> streams to Client
</code></pre>

Uses the [IIIFImageClient](https://github.com/emory-libraries/readux/blob/master/readux/books/iiif.py#L3-L110) from [Emory University's Readux platform](https://github.com/emory-libraries/readux).

