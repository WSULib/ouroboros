## DPLA API

This DPLA has a nicely organized and documented API, here are some of their routes from their [documentation](https://dp.la/info/developers/codex/requests/):

### Items

	http://api.dp.la/v2/items

To search items, use `/item` route, with additional parameters:

	http://api.dp.la/v2/items?q=kittens

For specific fields, dot notation with `sourceResource`, e.g.:

	sourceResource.title=”old+victorian”

Sorting, uses abstracted out `sort_by`:

	http://api.dp.la/v2/items?q=yodeling&sort_by=sourceResource.title

These are nice conventions, but for our purposes, it may be reasonable to assume we can use more native Solr fields and maintain a 1:1 with WSUDOR_API and Solr parameters.  This is helpful for building complex queries later.

Facets, abstracting out which facets to return:

	http://api.dp.la/v2/items?facets=sourceResource.publisher,sourceResource.creator

Though we understand the search / browse page might always need a particular set of facets, it might not hurt to use this syntax.  The request coming from the front-end would then include something like the above, explicitly asking for a group of facets.  In this way, **we keep the API un-opinionated about the front-end, and let models in the front-end dictate what facets are requested and shown**.  We did this previously, but we could abstract these out a bit more in this way.  Or not: if we leave the more 1:1 with Solr fields, we can accomplish the same.

### Collections

	http://api.dp.la/v2/collections

### Thoughts

Interestingly, the above is really suited for search / browse.  What about API calls for a single item's metadata and relationships?  We previously had a `singleObjectPackage` that would run a bunch of sub-functions and aggregate that information.  Each sub-function was indicated in the API call with a `functions[]=` that was parsed by Twisted.

Their documentation begins to unpack this a bit with information about their [Responses](https://dp.la/info/developers/codex/responses/) and [structure of objects](https://dp.la/info/developers/codex/responses/object-structure/).

It's conceivable that a search / browse response would be a bunch of individual records -- unsurprisingly -- **but that those records would be identical to what is returned for a single item**.  This would depart from our current mode, as it would require a BUNCH of, in our previous approach, sub-queries and calls that would slow down search/browse.  

How do they do this?  Are these relationships stored statically when an item is indexed?  
