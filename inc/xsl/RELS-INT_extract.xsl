<?xml version="1.0" encoding="UTF-8"?>
<!--RELS-INT datastream-->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:mods="http://www.loc.gov/mods/v3" exclude-result-prefixes="mods"
    xmlns:foxml="info:fedora/fedora-system:def/foxml#"
    xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" xmlns:fedora="info:fedora/fedora-system:def/relations-external#" xmlns:myns="http://www.nsdl.org/ontologies/relationships#">
    <xsl:template name="RELS-INT">        
        <xsl:param name="RELSroot"
            select="/foxml:digitalObject/foxml:datastream[@ID='RELS-INT']/foxml:datastreamVersion[last()]/foxml:xmlContent/rdf:RDF/rdf:Description"/>        
        <xsl:for-each select="$RELSroot/*">     
            
            <field> 
                <xsl:attribute name="name"> 
                    <xsl:value-of select="concat('rels_int_', name())"/> 
                </xsl:attribute> 
                <!-- grab URI's if prsent as rdf:resource,
                    otherwise grab as string literal -->
                
                <!-- build subject / object of triple, predicate is the field name -->
                <!-- begin list -->
                <xsl:text>[</xsl:text>

                <!-- subject -->
                <xsl:value-of select="../@rdf:about"/> 

                <!-- delimiting comma -->
                <xsl:text>,</xsl:text> 

                <!-- object -->
                <xsl:choose>
                    <xsl:when test="@rdf:resource">
                        <xsl:value-of select="@rdf:resource"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="."/>
                    </xsl:otherwise>
                </xsl:choose>

                <!-- close list -->
                <xsl:text>]</xsl:text>

            </field> 
        </xsl:for-each>        
    </xsl:template>
</xsl:stylesheet>