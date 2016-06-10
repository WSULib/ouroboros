# bitStream

bitStream is a routing proxy to backend services such as Fedora, Loris, Solr, etc.

## Fedora Datastreams
bitStream can be used to access Fedora datastreams when given an object PID and datastream ID.  Some datastreams are open to the public, so-called "unblocked" datastreams, while other require a key or token to acccess.

Example usage for open datastream:<br>
`http://192.168.42.4/WSUAPI/bitStream/wayne:vmc10/MODS`

A `403` status will be returned if the datastream is not available without a key or token.

Example:<br>
`http://192.168.42.4/WSUAPI/bitStream/wayne:vmc10/POLICY`

A `key` can be provided as a get parameter to access any Fedora datastream.  This key is secret and meant to be used only by administrators.

Example usage:<br>
`http://192.168.42.4/WSUAPI/bitStream/wayne:vmc10/POLICY?key=SECRET_KEY_HERE`

A token can be requested, when also passing the secret key, that will allow for a one-time download for any user, without the secret key.

Request token example:<br>
`http://192.168.42.4/WSUAPI/bitStream/wayne:vmc10/POLICY?key=SECRET_KEY_HERE&token=request`

Response will look similar to the following, with a token included:<br>
```{
    response: {
        token: "7a1f4033-e556-4740-8c6e-75cbbbe194c3"
    }
}```

Using that token, access will be permitted for one download of that datastream.

Example:<br>
`http://192.168.42.4/WSUAPI/bitStream/wayne:vmc10/POLICY?token=7a1f4033-e556-4740-8c6e-75cbbbe194c3`


## Loris Proxy


