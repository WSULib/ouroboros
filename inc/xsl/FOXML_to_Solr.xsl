<?xml version="1.0" encoding="UTF-8"?>
<!-- Basic MODS -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:mods="http://www.loc.gov/mods/v3" exclude-result-prefixes="mods"
    xmlns:foxml="info:fedora/fedora-system:def/foxml#" 
    xmlns:dc="http://purl.org/dc/elements/1.1/" 
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
    xmlns:fedora="info:fedora/fedora-system:def/relations-external#"
    xmlns:myns="http://www.nsdl.org/ontologies/relationships#"
    xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/">
    <xsl:output method="xml" indent="yes"/>

    <!--includes-->
    <xsl:include href="MODS_extract.xsl"/>
    <xsl:include href="RELS-EXT_extract.xsl"/>    
    <xsl:include href="DC_extract.xsl"/>

    <!--get PID from FOXML file-->
    <xsl:variable name="PID" select="/foxml:digitalObject/@PID"/>

    <xsl:template match="/">
        <!-- The following allows only active FedoraObjects to be indexed. -->
        <xsl:if
            test="foxml:digitalObject/foxml:objectProperties/foxml:property[@NAME='info:fedora/fedora-system:def/model#state' and @VALUE='Active']">
            <xsl:if
                test="not(foxml:digitalObject/foxml:datastream[@ID='METHODMAP'] or foxml:digitalObject/foxml:datastream[@ID='DS-COMPOSITE-MODEL'])">
                <xsl:if test="starts-with($PID,'')">
                    <xsl:apply-templates mode="activeFedoraObject"/>
                </xsl:if>
            </xsl:if>
        </xsl:if>
        <!-- The following allows inactive FedoraObjects to be deleted from the index. -->
        <xsl:if
            test="foxml:digitalObject/foxml:objectProperties/foxml:property[@NAME='info:fedora/fedora-system:def/model#state' and @VALUE='Inactive']">
            <xsl:if
                test="not(foxml:digitalObject/foxml:datastream[@ID='METHODMAP'] or foxml:digitalObject/foxml:datastream[@ID='DS-COMPOSITE-MODEL'])">
                <xsl:if test="starts-with($PID,'')">
                    <xsl:apply-templates mode="inactiveFedoraObject"/>
                </xsl:if>
            </xsl:if>
        </xsl:if>
    </xsl:template>

    <!--for active documents-->
    <xsl:template match="/foxml:digitalObject" mode="activeFedoraObject">
        <add>
            <doc>
                <!--Internal-->
                <field name="id">
                    <xsl:value-of select="$PID"/>
                </field>
                <field name="last_modified">NOW</field>
                
                <!--objectProperties-->
                <field name="obj_label">
                    <xsl:value-of select="/foxml:digitalObject/foxml:objectProperties/foxml:property[@NAME='info:fedora/fedora-system:def/model#label']/@VALUE" />
                </field>
                <field name="obj_createdDate">
                    <xsl:value-of select="/foxml:digitalObject/foxml:objectProperties/foxml:property[@NAME='info:fedora/fedora-system:def/model#createdDate']/@VALUE" />
                </field>
                <field name="obj_modifiedDate">
                    <xsl:value-of select="/foxml:digitalObject/foxml:objectProperties/foxml:property[@NAME='info:fedora/fedora-system:def/view#lastModifiedDate']/@VALUE" />
                </field>
                

                <!--RELS-EXT-->
                <xsl:call-template name="RELS-EXT"/>

                <!--MODS-->
                <xsl:call-template name="MODS"/>
                
                <!--DC-->
                <xsl:call-template name="DC"/>

            </doc>
        </add>
    </xsl:template>

    <!--remove inactive documents from Solr index-->
    <xsl:template match="/foxml:digitalObject" mode="inactiveFedoraObject">
        <delete>
            <id>
                <xsl:value-of select="$PID"/>
            </id>
        </delete>
    </xsl:template>


    


</xsl:stylesheet>
