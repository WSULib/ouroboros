# bitStream

bitStream is a flask proxy to Fedora datastreams, allowing for more fine grained access and restrictions.

## Fedora Datastreams
bitStream can be used to access Fedora datastreams when given an object PID and datastream ID.  Some datastreams are open to the public, so-called "unrestricted" datastreams, while other require a key or token to acccess.

Example usage for unrestricted datastream:<br>
`http://hostname/WSUAPI/bitStream/wayne:vmc10/MODS`

If the datastream is restricted, a `403` status will be returned if the request does not include a key or token.

Restricted example:<br>
`http://hostname/WSUAPI/bitStream/wayne:vmc10/POLICY`

Response:
<pre><code>{
    response: "datastream is blocked"
}
</code></pre>

## Keys and Tokens

A `key` can be provided as a get parameter to access any Fedora datastream.  This key is secret and meant to be used only by administrators.

Example usage:<br>
`http://hostname/WSUAPI/bitStream/wayne:vmc10/POLICY?key=SECRET_KEY_HERE`

A token can be requested, when also passing the secret key, that will allow for a one-time download for any user, without the secret key.

Request token example:<br>
`http://hostname/WSUAPI/bitStream/wayne:vmc10/POLICY?key=SECRET_KEY_HERE&token=request`

Response will look similar to the following, with a token included:<br>
<pre><code>{
    response: {
        token: "7a1f4033-e556-4740-8c6e-75cbbbe194c3"
    }
}</code></pre>

Using that token, access will be permitted for one download of that datastream.

Example:<br>
`http://hostname/WSUAPI/bitStream/wayne:vmc10/POLICY?token=7a1f4033-e556-4740-8c6e-75cbbbe194c3`


