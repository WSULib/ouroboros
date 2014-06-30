<?xml version="1.0" encoding="UTF-8"?>
<!--DC datastream-->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:mods="http://www.loc.gov/mods/v3" exclude-result-prefixes="mods"
    xmlns:foxml="info:fedora/fedora-system:def/foxml#" 
    xmlns:dc="http://purl.org/dc/elements/1.1/" 
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
    xmlns:fedora="info:fedora/fedora-system:def/relations-external#"
    xmlns:myns="http://www.nsdl.org/ontologies/relationships#"
    xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/">
    <xsl:template name="DC">
        <xsl:param name="prefix">dc_</xsl:param>
        <xsl:param name="suffix">_ms</xsl:param> 

        <xsl:param name="DCroot"
            select="/foxml:digitalObject/foxml:datastream[@ID='DC']/foxml:datastreamVersion[last()]/foxml:xmlContent/oai_dc:dc"/>

        <xsl:for-each select="$DCroot/*">
            <field>
                <xsl:attribute name="name">
                    <xsl:value-of select="concat($prefix, local-name())"/>
                </xsl:attribute>
                <xsl:value-of select="text()"/>
            </field>
        </xsl:for-each>
    </xsl:template>
</xsl:stylesheet>