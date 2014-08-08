<?xml version="1.0" encoding="UTF-8"?>
<!--RELS-EXT datastream-->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:mods="http://www.loc.gov/mods/v3" exclude-result-prefixes="mods"
    xmlns:foxml="info:fedora/fedora-system:def/foxml#"
    xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" xmlns:fedora="info:fedora/fedora-system:def/relations-external#" xmlns:myns="http://www.nsdl.org/ontologies/relationships#">
    <xsl:template name="RELS-EXT">        
        <xsl:param name="RELSroot"
            select="/foxml:digitalObject/foxml:datastream[@ID='RELS-EXT']/foxml:datastreamVersion[last()]/foxml:xmlContent/rdf:RDF/rdf:Description"/>        
        <xsl:for-each 
            select="$RELSroot/*">            
            <field> 
                <xsl:attribute name="name"> 
                    <xsl:value-of select="concat('rels_', name())"/> 
                </xsl:attribute> 
                <xsl:value-of select="@rdf:resource"/> 
            </field> 
        </xsl:for-each>        
    </xsl:template>
</xsl:stylesheet>
