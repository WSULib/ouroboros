<?xml version="1.0" encoding="UTF-8"?>
<!--RELS-EXT datastream-->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:mods="http://www.loc.gov/mods/v3" exclude-result-prefixes="mods"
    xmlns:foxml="info:fedora/fedora-system:def/foxml#"
    xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" xmlns:fedora="info:fedora/fedora-system:def/relations-external#" xmlns:myns="http://www.nsdl.org/ontologies/relationships#">
    <xsl:template name="RELS-EXT" match="/">        
        <xsl:param name="RELSroot"
            select="//rdf:RDF/rdf:Description"/>        

        <!-- wrap -->
        <fields>

        <xsl:for-each select="$RELSroot/*">     
            
            <field> 
                <xsl:attribute name="name"> 
                    <xsl:value-of select="concat('rels_', name())"/> 
                </xsl:attribute> 
                <!-- grab URI's if prsent as rdf:resource,
                    otherwise grab as string literal -->
                <xsl:choose>
                    <xsl:when test="@rdf:resource">
                        <xsl:value-of select="@rdf:resource"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="."/>
                    </xsl:otherwise>
                </xsl:choose>
            </field> 
        </xsl:for-each>  

    	</fields>

    </xsl:template>
</xsl:stylesheet>