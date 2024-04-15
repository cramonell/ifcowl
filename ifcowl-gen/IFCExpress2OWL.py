from ifcopenshell import ifcopenshell_wrapper
import json
from rdflib import Graph, Namespace, Literal, URIRef, BNode 
import datetime
import os
import pathlib

script_dir = pathlib.Path(__file__).parent
config_path = (script_dir / 'config.json').resolve()

### PARAMETERS
with open(config_path, 'r',encoding='utf-8') as fp:
    params =json.load(fp)

schema_name = params['ifc-schema']
output_path = params['output-path']
output_format = params['output-format']

# load the express IFC schema
schema = ifcopenshell_wrapper.schema_by_name(schema_name)

# define functions to create lists and list restrictions depending on the lists bounds.
def create_list_restriction(bound:int,  entity_type) -> BNode:
    bn = BNode()
    if bound > 1:
        g.add((bn, RDF.type, OWL.Restriction))
        g.add((bn, OWL.onProperty, LIST.hasNext))
        g.add((bn, OWL.someValuesFrom, create_list_restriction(bound-1, entity_type)))
        
    elif bound ==1:
        g.add((bn, RDF.type, OWL.Restriction))
        g.add((bn, OWL.onProperty, LIST.hasNext))
        g.add((bn, OWL.someValuesFrom, entity_type))
    
    return bn        

def create_empty_list_restriction(bound:int, entity_type) -> BNode:
    bn = BNode()
    if bound > 1:
        g.add((bn, RDF.type, OWL.Restriction))
        g.add((bn, OWL.onProperty, LIST.hasNext))
        g.add((bn, OWL.allValuesFrom, create_empty_list_restriction(bound-1,entity_type)))
        
    elif bound == 1:
        g.add((bn, RDF.type, OWL.Restriction))
        g.add((bn, OWL.onProperty, LIST.hasNext))
        g.add((bn, OWL.qualifiedCardinality, Literal(1, datatype=XSD.nonNegativeInteger)))
        g.add((bn, OWL.onClass, entity_type))
    
    return bn

def create_list(ifc_type, entity_type, bound1, bound2):
    g.add((ifc_type, RDF.type, OWL.Class))
    g.add((ifc_type, RDFS.subClassOf, entity_type))
    if bound1 != 0:
        g.add((ifc_type, RDFS.subClassOf, create_list_restriction(bound1, entity_type)))
    if bound2  != -1:
        div = entity_type.split('_')
        if len(div)>2:
            entity_type = URIRef(div[0] + '_'+ div[1] +'_EmptyList')
        else:
            entity_type = URIRef(div[0] +'_EmptyList')
        g.add((ifc_type, RDFS.subClassOf, create_empty_list_restriction(bound2,entity_type)))

def create_named_type_list_entity(ifctype):
    name =ifctype + '_List'
    bn1 = BNode()
    bn2 = BNode()
    bn3 = BNode()

    g.add((bn1, RDF.type, OWL.Restriction))
    g.add((bn1, OWL.onProperty, LIST.hasContents))
    g.add((bn1, OWL.allValuesFrom, IFC[ifctype]))

    g.add((bn2, RDF.type, OWL.Restriction))
    g.add((bn2, OWL.onProperty, LIST.hasNext))
    g.add((bn2, OWL.allValuesFrom, IFC[name]))

    g.add((bn3, RDF.type, OWL.Restriction))
    g.add((bn3, OWL.onProperty, LIST.isFollowedBy))
    g.add((bn3, OWL.allValuesFrom, IFC[name]))

    g.add((IFC[name], RDF.type, OWL.Class))
    g.add((IFC[name], RDFS.subClassOf, LIST.OWLList))
    g.add((IFC[name], RDFS.subClassOf, bn1))
    g.add((IFC[name], RDFS.subClassOf, bn2))
    g.add((IFC[name], RDFS.subClassOf, bn3))

def create_named_type_empty_list_entity(ifctype, list_name):
    name = ifctype + '_EmptyList'
    g.add((IFC[name], RDF.type, OWL.Class))
    g.add((IFC[name], RDFS.subClassOf, LIST.EmptyList))
    g.add((IFC[name], RDFS.subClassOf, IFC[list_name]))

def create_set(ifc_type, list_entity_type, bound1,bound2):
    bn1 = BNode()
    bn2 = BNode()
    bn3 = BNode()
    
    g.add((bn1, RDF.type, OWL.Restriction))
    g.add((bn1, OWL.onProperty, EXPRESS.hasSet))
    g.add((bn1, OWL.allValuesFrom, list_entity_type))
    
    if bound1 > 0:
        g.add((bn2, RDF.type, OWL.Restriction))
        g.add((bn2, OWL.onProperty, EXPRESS.hasSet))
        g.add((bn2, OWL.minQualifiedCardinality,  Literal(bound1, datatype=XSD.nonNegativeInteger)))
        g.add((bn2, OWL.onClass, list_entity_type))
    
    if bound2 != -1:      
        g.add((bn3, RDF.type, OWL.Restriction))
        g.add((bn3, OWL.onProperty, EXPRESS.hasSet))
        g.add((bn3, OWL.qualifiedCardinality,  Literal(bound2, datatype=XSD.nonNegativeInteger)))
        g.add((bn3, OWL.onClass, list_entity_type)) 
    

    g.add((ifc_type, RDF.type, OWL.Class))
    g.add((ifc_type, RDFS.subClassOf, bn1))
    g.add((ifc_type, RDFS.subClassOf, bn2))

def iterate_subtypes_inverse_attrs(entity, inverse_attributes):
    sup_inv_attrs =  [sup_inv_attr.name() for sup_inv_attr in entity.all_inverse_attributes()]
    for subtype in entity.subtypes():
        inverse_attributes[subtype.name()]=[inv_attr.name() for inv_attr in subtype.all_inverse_attributes() if inv_attr.name() not in sup_inv_attrs]
        iterate_subtypes_inverse_attrs(subtype,inverse_attributes)

def add_simple_type_attr(entity_name, attr_name, type_of_attr, optional):
    #create blank nodes to add restrictions
    bnode_value = BNode()
    bnode_cardinality = BNode()

    #add range to the attribute class
    range_name = type_of_attr.declared_type().upper()
    g.add((IFC[attr_name], RDFS.range,  EXPRESS[range_name]))

    #define as functional property
    g.add((IFC[attr_name], RDF.type,  OWL.FunctionalProperty))

    #add black value and cardinality restrictions to the entity class
    g.add((IFC[entity_name], RDFS.subClassOf, bnode_value))
    g.add((IFC[entity_name], RDFS.subClassOf, bnode_cardinality))

    #Specify value restriction
    g.add((bnode_value, RDF.type, OWL.Restriction))
    g.add((bnode_value, OWL.onProperty, IFC[attr_name]))
    g.add((bnode_value, OWL.allValuesFrom, EXPRESS[range_name]))

    #Specify cardinality restriction
    g.add((bnode_cardinality, RDF.type, OWL.Restriction))
    g.add((bnode_cardinality, OWL.onProperty, IFC[attr_name]))
    if optional:g.add((bnode_cardinality, OWL.maxQualifiedCardinality,  Literal(1, datatype=XSD.nonNegativeInteger)))
    else:g.add((bnode_cardinality, OWL.qualifiedCardinality,  Literal(1, datatype=XSD.nonNegativeInteger)))
    g.add((bnode_cardinality, OWL.onClass, EXPRESS[range_name]))

def add_named_type_attr(entity_name, attr_name, type_of_attr, optional):
    
    #create blank nodes to add restrictions
    bnode_value = BNode()
    bnode_cardinality = BNode()

    #add range to the attribute class
    range_name = type_of_attr.declared_type().name()
    g.add((IFC[attr_name], RDFS.range,  IFC[range_name]))

    #define as functional property
    g.add((IFC[attr_name], RDF.type,  OWL.FunctionalProperty))
    
    #Specify value restriction
    g.add((IFC[entity_name], RDFS.subClassOf, bnode_value))
    g.add((bnode_value, RDF.type, OWL.Restriction))
    g.add((bnode_value, OWL.onProperty, IFC[attr_name]))
    g.add((bnode_value, OWL.allValuesFrom, IFC[range_name]))

    #Specify cardinality restriction
    g.add((IFC[entity_name], RDFS.subClassOf, bnode_cardinality))
    g.add((bnode_cardinality, RDF.type, OWL.Restriction))
    g.add((bnode_cardinality, OWL.onProperty, IFC[attr_name]))
    if optional: g.add((bnode_cardinality, OWL.maxQualifiedCardinality,  Literal(1, datatype=XSD.nonNegativeInteger)))
    else: g.add((bnode_cardinality, OWL.qualifiedCardinality,  Literal(1, datatype=XSD.nonNegativeInteger)))
    g.add((bnode_cardinality, OWL.onClass, IFC[range_name]))    

def add_aggregation_type_attr(entity_name, attr_name, type_of_attr,optional):
    type_of_aggregation = type_of_attr.type_of_aggregation()
    aggregation_element_type = type_of_attr.type_of_element()
    bound1 = type_of_attr.bound1()
    bound2 = type_of_attr.bound2()

    if type_of_aggregation in [type_of_attr.array_type, type_of_attr.list_type]:
        
        #define as functional property
        g.add((IFC[attr_name], RDF.type,  OWL.FunctionalProperty))

        if aggregation_element_type.as_simple_type():
            
            list_entity_name = aggregation_element_type.declared_type().upper()
            list_name = list_entity_name + '_List'
            empty_list_name = list_entity_name + '_EmptyList'

            #add range to the attribute class
            g.add((IFC[attr_name], RDFS.range,  IFC[list_name]))

            if bound1 != 0:
                g.add((IFC[entity_name], RDFS.subClassOf, create_list_restriction(bound1, EXPRESS[list_name])))

            if bound2  != -1:
                g.add((IFC[entity_name], RDFS.subClassOf, create_empty_list_restriction(bound2, EXPRESS[empty_list_name])))

        elif aggregation_element_type.as_named_type():

            bnode_list = BNode()
            bnode_cardinality =  BNode()
            bnode_value = BNode()

            #get the name of entity  listed
            list_entity_type = aggregation_element_type.declared_type()
            list_entity_name = list_entity_type.name() 

            #create the name of the list entity
            list_name = list_entity_name + '_List'
            empty_list_name =  list_entity_name + '_EmptyList'

            #add range to the attribute class
            g.add((IFC[attr_name], RDFS.range,  IFC[list_name]))

            #Create list type entity if not created
            if list_name not in type_entities_List: 
                type_entities_List.append(list_name)
                create_named_type_list_entity(list_entity_name)
            #Create its empty list counterpart
            if empty_list_name not in type_entities_EmptyList:
                type_entities_EmptyList.append(empty_list_name)
                create_named_type_empty_list_entity(list_entity_name, list_name)
            
            #create list restrictions
            if bound1 > 0:
                g.add((IFC[entity_name], RDFS.subClassOf, bnode_list))
                g.add((bnode_list, RDF.type, OWL.Restriction))
                g.add((bnode_list, OWL.onProperty, IFC[attr_name]))
                g.add((bnode_list, OWL.allValuesFrom, create_list_restriction(bound1, IFC[list_name])))
                
            ##if there is upper bound, restrict using Empty_List entities to 
            if bound2  != -1:
                bnode_empty_list = BNode()
                g.add((IFC[entity_name], RDFS.subClassOf, bnode_empty_list))
                g.add((bnode_empty_list, RDF.type, OWL.Restriction))
                g.add((bnode_empty_list, OWL.onProperty, IFC[attr_name]))
                g.add((bnode_empty_list, OWL.allValuesFrom, create_empty_list_restriction(bound2, IFC[empty_list_name])))
            
            # if bound1 and bound2 areequal, then create new restriction: all values are the list entity
            if bound1 == bound2:
                bnode_value=BNode()
                g.add((IFC[entity_name], RDFS.subClassOf, bnode_value))
                g.add((bnode_value, RDF.type, OWL.Restriction))
                g.add((bnode_value, OWL.onProperty, IFC[attr_name]))
                g.add((bnode_value, OWL.allValuesFrom, IFC[list_name]))
            
            #Specify cardinality restriction
            g.add((IFC[entity_name], RDFS.subClassOf, bnode_cardinality))
            g.add((bnode_cardinality, RDF.type, OWL.Restriction))
            g.add((bnode_cardinality, OWL.onProperty, IFC[attr_name]))
            if optional: g.add((bnode_cardinality, OWL.maxQualifiedCardinality,  Literal(1, datatype=XSD.nonNegativeInteger)))
            else: g.add((bnode_cardinality, OWL.qualifiedCardinality,  Literal(1, datatype=XSD.nonNegativeInteger)))
            g.add((bnode_cardinality, OWL.onClass, IFC[list_name])) 

            #specify value restriction
            g.add((IFC[entity_name], RDFS.subClassOf, bnode_value))
            g.add((bnode_value, RDF.type, OWL.Restriction))
            g.add((bnode_value, OWL.onProperty, IFC[attr_name]))
            g.add((bnode_value, OWL.allValuesFrom, IFC[list_name]))

                
        
        elif aggregation_element_type.as_aggregation_type():

            #get the aggreagation element type of the nested list
            aggregation_element_type = aggregation_element_type.type_of_element()

            #create blank nodes to add restriction to the  list and its  nested list
            bnode_list = BNode()
            bnode_cardinality = BNode()
            bnode_value = BNode()

            #get the name of the entity listed (e.g. IfcCartesianPoint)
            list_enitity_name = aggregation_element_type.declared_type().name() 

            #create the name of the nested list entity(e.g. IfcCartesianPoint_List)
            nested_list_name = list_enitity_name + '_List'
            nested_empty_list_name = list_enitity_name + '_EmptyList'

            #create the name of the list entity (e.g.  IfcCartesianPoint_List_List)
            list_name = nested_list_name + '_List'
            empty_list_name =  nested_list_name +'_EmptyList'

            #add range to the attribute class(e.g. the range of the attr is IfcCartesianPoint_List_List)
            g.add((IFC[attr_name], RDFS.range,  IFC[list_name]))

            #Create both list types if  they have not been created
            if list_name not in type_entities_List: 
                type_entities_List.append(list_name)
                create_named_type_list_entity(nested_list_name)

            if nested_list_name not in type_entities_List: 
                type_entities_List.append(nested_list_name)
                create_named_type_list_entity(list_enitity_name)
            
            #Create both empty list counterparts
            if nested_empty_list_name not in type_entities_EmptyList:
                type_entities_EmptyList.append(empty_list_name)
                create_named_type_empty_list_entity(list_enitity_name, nested_list_name)
            
            if empty_list_name not in type_entities_EmptyList:
                type_entities_EmptyList.append(empty_list_name)
                create_named_type_empty_list_entity(nested_list_name, list_name)
            
            #create list restrictions            
            if bound1 > 0:
                g.add((IFC[entity_name], RDFS.subClassOf, bnode_list))
                g.add((bnode_list, RDF.type, OWL.Restriction))
                g.add((bnode_list, OWL.onProperty, IFC[attr_name]))
                g.add((bnode_list, OWL.allValuesFrom, create_list_restriction(bound1, IFC[list_name])))

            if bound2  != -1:
                bnode_empty_list = BNode()
                g.add((IFC[entity_name], RDFS.subClassOf, bnode_empty_list))
                g.add((bnode_empty_list, RDF.type, OWL.Restriction))
                g.add((bnode_empty_list, OWL.onProperty, IFC[attr_name]))
                g.add((bnode_empty_list, OWL.allValuesFrom, create_empty_list_restriction(bound2, IFC[empty_list_name])))
                
            
            # if bound1 and bound2 are equal, then create new restriction: all values are the list entity
            if bound1 == bound2:
                bnode_value=BNode()
                g.add((IFC[entity_name], RDFS.subClassOf, bnode_value))
                g.add((bnode_value, RDF.type, OWL.Restriction))
                g.add((bnode_value, OWL.onProperty, IFC[attr_name]))
                g.add((bnode_value, OWL.allValuesFrom, IFC[list_name]))
            
            #Specify cardinality restriction
            g.add((IFC[entity_name], RDFS.subClassOf, bnode_cardinality))
            g.add((bnode_cardinality, RDF.type, OWL.Restriction))
            g.add((bnode_cardinality, OWL.onProperty, IFC[attr_name]))
            if optional: g.add((bnode_cardinality, OWL.maxQualifiedCardinality,  Literal(1, datatype=XSD.nonNegativeInteger)))
            else: g.add((bnode_cardinality, OWL.qualifiedCardinality,  Literal(1, datatype=XSD.nonNegativeInteger)))
            g.add((bnode_cardinality, OWL.onClass, IFC[list_name])) 

            #specify value restriction
            g.add((IFC[entity_name], RDFS.subClassOf, bnode_value))
            g.add((bnode_value, RDF.type, OWL.Restriction))
            g.add((bnode_value, OWL.onProperty, IFC[attr_name]))
            g.add((bnode_value, OWL.allValuesFrom, IFC[list_name]))


    elif type_of_aggregation == type_of_attr.set_type:

        bnode_value = BNode()
        bnode_min_cardinality = BNode()
        bnode_max_cardinality = BNode()

        set_enitity_name = aggregation_element_type.declared_type().name()

        #add range to the attribute class
        g.add((IFC[attr_name], RDFS.range,  IFC[set_enitity_name]))

        #add restrictions to  the entity class
        g.add((IFC[entity_name], RDFS.subClassOf, bnode_value))
        g.add((bnode_value, RDF.type, OWL.Restriction))
        g.add((bnode_value, OWL.onProperty, IFC[attr_name]))
        g.add((bnode_value, OWL.allValuesFrom, IFC[set_enitity_name]))

        if bound1 > 0 and not optional:
            g.add((IFC[entity_name], RDFS.subClassOf, bnode_min_cardinality))
            g.add((bnode_min_cardinality, RDF.type, OWL.Restriction))
            g.add((bnode_min_cardinality, OWL.onProperty, IFC[attr_name]))
            g.add((bnode_min_cardinality, OWL.minQualifiedCardinality,  Literal(bound1, datatype=XSD.nonNegativeInteger)))
            g.add((bnode_min_cardinality, OWL.onClass, IFC[set_enitity_name]))
        
        if bound2 != -1:      
            g.add((IFC[entity_name], RDFS.subClassOf, bnode_max_cardinality))
            g.add((bnode_max_cardinality, RDF.type, OWL.Restriction))
            g.add((bnode_max_cardinality, OWL.onProperty,IFC[attr_name]))
            g.add((bnode_max_cardinality, OWL.maxQualifiedCardinality,  Literal(bound2, datatype=XSD.nonNegativeInteger)))
            g.add((bnode_max_cardinality, OWL.onClass, IFC[set_enitity_name]))
        
    elif type_of_aggregation == type_of_attr.bag_type:
        pass


# Create a new graph
g = Graph()

#ontology ref specification
base_ref = "https://w3id.org/ifc/"
if schema_name == "IFC4X3": ref_name = "IFC4X3"
elif schema_name == "IFC4X3_rc3":  ref_name = "IFC4X3_RC3"
elif schema_name == "IFC4X3_Add2":  ref_name = "IFC4X3_ADD2"
elif schema_name == "IFC4X3_Add1":  ref_name = "IFC4X3_ADD1"
elif schema_name == "IFC4": ref_name = "IFC4/ADD2_TC1/OWL"
elif schema_name == "IFC2X3": ref_name = "IFC2_3/OWL"
ref = URIRef(base_ref +ref_name+"#")

# Create a namespaces for the ontology
IFC = Namespace(ref)
EXPRESS = Namespace('https://w3id.org/express#')
CC = Namespace('http://creativecommons.org/ns#')
LIST = Namespace("https://w3id.org/list#")
DCE = Namespace("http://purl.org/dc/elements/1.1/")
VANN = Namespace("http://purl.org/vocab/vann/")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")

# Bind your custom prefix
g.bind("ifc", IFC)
g.bind('rdf', RDF)
g.bind('rdfs', RDFS)
g.bind('owl', OWL)
g.bind('vann', VANN)
g.bind('xsd', XSD)
g.bind('express',EXPRESS)
g.bind('cc', CC)
g.bind('list', LIST)
g.bind('dce', DCE)

#add ontology header triples
g.add((ref, RDF.type, OWL.Ontology))
g.add((ref, DCE.creator, Literal('Pieter Pauwels (pipauwel.pauwels@ugent.be)')))
g.add((ref, DCE.creator, Literal('Walter Terkaj (walter.terkaj@itia.cnr.it)')))
g.add((ref, DCE.creator, Literal('Carlos Ramonell Cazador (carlos.ramonell@upc.edu)')))
g.add((ref, DCE.contributor, Literal('Jakob Beetz (j.beetz@tue.nl)')))
g.add((ref, DCE.contributor, Literal('María Poveda Villalón (mpoveda@fi.upm.es)')))
g.add((ref, DCE.contributor, Literal('Aleksandra Sojic (aleksandra.sojic@itia.cnr.it)')))
g.add((ref, DCE.date, Literal(datetime.datetime.today().strftime('%Y/%m/%d'))))
g.add((ref, DCE.title, Literal(schema_name.upper())))
g.add((ref, DCE.description, Literal("OWL ontology for the IFC conceptual data schema and exchange file format for Building Information Model (BIM) data. Release 4X3 ADD2.")))
g.add((ref, DCE.identifier, Literal(schema_name.upper())))
g.add((ref, DCE.language, Literal('en')))
g.add((ref, DCE.abstract, Literal(f"This ifcOWL ontology is automatically generated from the EXPRESS schema '{schema_name.upper()}' using the 'IFCExpress2OWL' converter developed by Carlos Ramonell (carlos.ramonell@upc.edu). The ontology is identical to the ontology that is generated from the EXPRESS schema '{schema_name.upper()}.exp' using the 'IFC-to-RDF' converter developed by Pieter Pauwels (pipauwel.pauwels@ugent.be)")))
g.add((ref, VANN.preferredNamespacePrefix, Literal('ifc')))
g.add((ref, VANN.preferredNamespaceUri, Literal(ref)))
g.add((ref, OWL.imports, URIRef('https://w3id.org/express')))
g.add((ref, OWL.versionIRI, ref))
g.add((ref, OWL.versionInfo, Literal('1.0')))
g.add((ref, OWL.priorVersion, Literal('https://pi.pauwel.be/evoc/ifc_W3ID/20151211/IFC4_ADD1/index.html')))
g.add((ref, CC.license, Literal('http://creativecommons.org/licenses/by/3.0/')))

# anotation properties
g.add((DCE.creator, RDF.type, OWL.AnnotationProperty))
g.add((DCE.contributor, RDF.type, OWL.AnnotationProperty))
g.add((DCE.date, RDF.type, OWL.AnnotationProperty))
g.add((DCE.title, RDF.type, OWL.AnnotationProperty))
g.add((DCE.description, RDF.type, OWL.AnnotationProperty))
g.add((DCE.identifier, RDF.type, OWL.AnnotationProperty))
g.add((DCE.language, RDF.type, OWL.AnnotationProperty))

# create empty list to filter different types of declarations
simple_types = []
named_types = []
aggregation_types = []
enumerations = []
selects = []
entities = []

#create  list of type_List to avoid list repetitions. Same for type_EmptyList
type_entities_List = []
type_entities_EmptyList = []

# split the declarations of the schema to proceed to an ordered tranformation: first types, then entities.
for declaration in schema.declarations():
    
    if declaration.as_type_declaration():

        declared_type = declaration.declared_type()

        if declared_type.as_simple_type():
            simple_types.append(declaration)
            
        elif declared_type.as_named_type():
            named_types.append(declaration)

        elif declared_type.as_aggregation_type():
            aggregation_types.append(declaration)

        else: print('NOT IDENTIFIED TYPE: ' + str(declared_type))    
        
    elif declaration.as_enumeration_type():
        enumerations.append(declaration)

    elif declaration.as_select_type():
        selects.append(declaration)
    
    elif declaration.as_entity():
        entities.append(declaration)
    
    else: print('NOT IDENTIFIED DECLARATION: ' + str(declaration))

# create select classes. create inverse dictionary to assign the selects as supertypes to the entities/types they refer to.
inverse_selects = {}
for declaration in selects:

    select_name = declaration.name()
    g.add((IFC[select_name], RDF.type, OWL.Class))
    g.add((IFC[select_name], RDFS.subClassOf, EXPRESS.SELECT))

    for item in declaration.select_list():

        item_name = item.name()
        if item_name not in inverse_selects.keys(): inverse_selects[item_name]= []
        inverse_selects[item_name].append(select_name)

# iterate again over selects to assign as parent classes selects that list selects 
for declaration in selects:
    select_name = declaration.name()
        #assign as parent classes the selects tha list the type
    try:
        for select in inverse_selects[select_name]:
            g.add((IFC[select_name], RDFS.subClassOf, IFC[select]))
    except: pass

# create simple types
for declaration in simple_types:

    name = declaration.name()
    declared_type = declaration.declared_type()
    type_name = declared_type.declared_type().upper()
    g.add((IFC[name], RDF.type, OWL.Class))
    g.add((IFC[name], RDFS.subClassOf, EXPRESS[type_name]))

    #assign as parent classes the selects tha list the type
    try:
        for select in inverse_selects[name]:
            g.add((IFC[name], RDFS.subClassOf, IFC[select]))
    except: pass

# create named types
for declaration in named_types:
    name = declaration.name()
    declared_type_name = declaration.declared_type().declared_type().name()

    g.add((IFC[name], RDF.type, OWL.Class))
    g.add((IFC[name], RDFS.subClassOf, IFC[declared_type_name]))

    # assign as parent classes the selects that list the type
    try:
        for select in inverse_selects[name]:
            g.add((IFC[name], RDFS.subClassOf, IFC[select]))
    except: pass

# Create aggregation types
for declaration in aggregation_types:
    
    #data
    name =  declaration.name()
    declared_type = declaration.declared_type()
    type_of_aggregation = declared_type.type_of_aggregation()
    aggregation_element_type = declared_type.type_of_element()
    bound1 = declared_type.bound1()
    bound2 = declared_type.bound2()

    try:
        for select in inverse_selects[name]:
            g.add((IFC[name], RDFS.subClassOf, IFC[select]))
    except: pass

    if type_of_aggregation in [declared_type.array_type, declared_type.list_type]:

        if aggregation_element_type.as_simple_type():
            element_type_name = aggregation_element_type.declared_type().upper() + '_List'
            create_list(IFC[name], EXPRESS[element_type_name], bound1, bound2)

        elif aggregation_element_type.as_named_type():
            
            list_enitity_name = aggregation_element_type.declared_type().name() 
            list_name = list_enitity_name + '_List'

            if list_name not in type_entities_List: 
                type_entities_List.append(list_name)
                create_named_type_list_entity(list_enitity_name)

            create_list(IFC[name], IFC[list_name] , bound1, bound2)

    elif type_of_aggregation == declared_type.set_type:

        list_enitity_name = aggregation_element_type.declared_type().name()
        create_set(IFC[name], IFC[list_enitity_name],bound1, bound2)

    elif type_of_aggregation == declared_type.bag_type:
        pass

    else: pass

inverse_enumerations = {}

# Create enumerations
for declaration in enumerations:
    name = declaration.name()

    g.add((IFC[name], RDF.type, OWL.Class))
    g.add((IFC[name], RDFS.subClassOf, EXPRESS.ENUMERATION))

    for item in declaration.enumeration_items():
        if item not in inverse_enumerations.keys(): inverse_enumerations[item]= []
        inverse_enumerations[item].append(name)

##create named individuals for enumeration items
for individual in inverse_enumerations.keys():
    g.add((IFC[individual], RDF.type, OWL.NamedIndividual))
    for enumeration in inverse_enumerations[individual]:
        g.add((IFC[individual], RDF.type, IFC[enumeration]))
    g.add((IFC[individual], RDFS.label, Literal(individual)))      

inverse_attributes ={}
#create inverse attributes dictionary
for entity in entities:
    if not entity.supertype():
        inverse_attributes[entity.name()]=[inv_attr.name() for inv_attr in entity.all_inverse_attributes()]
        iterate_subtypes_inverse_attrs(entity, inverse_attributes)

# Create entities
for entity  in entities:

    #store entity data
    abstract = entity.is_abstract()
    derived =entity.derived()
    entity_name = entity.name()
    supertype =  entity.supertype()
    subtypes = [subtype.name() for subtype in entity.subtypes()]
    g.add((IFC[entity_name], RDF.type, OWL.Class))
    
    #create dijsoint condition with all classes that share supertype
    if supertype: 
        g.add((IFC[entity_name], RDFS.subClassOf, IFC[supertype.name()]))
        disjoint = [subtype.name() for subtype in supertype.subtypes()]
        for disjoint_entity in disjoint: # ONE OF restriction in express applied to the subclasses of the superclass of the processed entity.
            if disjoint_entity != entity_name: g.add((IFC[entity_name], OWL.disjointWith, IFC[disjoint_entity]))

    # if it is an abstract supertype declare the class a subclass of the union of its subclasses (??)
    if abstract: 
        abstract_node = BNode()
        collection_node =BNode()
        item1 = collection_node
        item2 = BNode()
        g.add((abstract_node, RDF.type, OWL.Class))
        for i  in range(len(subtypes)):
            g.add((item1, RDF.first, IFC[subtypes[i]]))
            g.add((item1, RDF.rest, item2))
            item1 = item2
            if i == len(subtypes)-2: item2 = RDF.nil
            else: item2 = BNode()
            #g.add((abstract_node, OWL.unionOf, IFC[subtype]))
        g.add((abstract_node, OWL.unionOf, collection_node))
        
        g.add((IFC[entity_name], RDFS.subClassOf, abstract_node))
    
    # assign select as parent if required
    try:
        for select in inverse_selects[entity_name]:
            g.add((IFC[entity_name], RDFS.subClassOf, IFC[select]))
    except: pass

    # Add attributes
    attrs = entity.attributes()
    for attr in attrs:
        attr_label = attr.name()
        attr_name = attr_label[0].lower() + attr_label[1:] + '_' + entity_name

        #as object property
        g.add((IFC[attr_name], RDF.type,  OWL.ObjectProperty))
        #set label
        g.add((IFC[attr_name], RDFS.label,  Literal(attr_label)))
        #define domain
        g.add((IFC[attr_name], RDFS.domain,  IFC[entity_name]))
        
        type_of_attr = attr.type_of_attribute()
        optional = attr.optional()

        if type_of_attr.as_simple_type():

            add_simple_type_attr(entity_name, attr_name, type_of_attr, optional)

        elif type_of_attr.as_named_type():
            
            add_named_type_attr(entity_name, attr_name, type_of_attr, optional) 

        elif type_of_attr.as_aggregation_type():
            
            add_aggregation_type_attr(entity_name, attr_name, type_of_attr, optional)

    #add inverse attributes
    inv_attrs = entity.all_inverse_attributes()
    for inv_attr in inv_attrs:
        #only  process the inverse attributes assigned specifically to  the entity
        if inv_attr.name() in inverse_attributes[entity.name()]:

            #create blank nodes to add restrictions
            bnode_value =  BNode()
            bnode_cardinality = BNode()

            inverse_attr_label = inv_attr.name()
            inverse_attr_name = inverse_attr_label[0].lower() + inverse_attr_label[1:] + '_' + entity_name
            bound1 = inv_attr.bound1()
            bound2 = inv_attr.bound2()

            reference_entity_name = inv_attr.entity_reference().name()
            inverse_of_attr = inv_attr.attribute_reference()
            inverse_of_attr_type = inverse_of_attr.type_of_attribute()
            inverse_of_attr_label = inverse_of_attr.name() #inverse attribute
            inverse_of_attr_name = inverse_of_attr_label[0].lower() + inverse_of_attr_label[1:] + '_' + reference_entity_name

            #add inverse attribure type, label, domain, range, and inverse.
            g.add((IFC[inverse_attr_name], RDF.type,  OWL.ObjectProperty))
            g.add((IFC[inverse_attr_name], RDFS.label,  Literal(inverse_attr_label)))
            g.add((IFC[inverse_attr_name], RDFS.domain,  IFC[entity_name]))
            g.add((IFC[inverse_attr_name], RDFS.range,  IFC[reference_entity_name]))

            #add value restriction
            g.add((IFC[entity_name], RDFS.subClassOf, bnode_value))
            g.add((bnode_value, RDF.type, OWL.Restriction))
            g.add((bnode_value, OWL.onProperty, IFC[inverse_attr_name]))
            g.add((bnode_value, OWL.allValuesFrom, IFC[reference_entity_name]))

            if inv_attr.type_of_aggregation() != inv_attr.set_type: 
                
                #set as functional property if the type is not a set.
                g.add((IFC[inverse_attr_name], RDF.type,  OWL.FunctionalProperty))
               
                #set cardinality restriction exactly equal to 1
                g.add((IFC[entity_name], RDFS.subClassOf, bnode_cardinality))
                g.add((bnode_cardinality, RDF.type, OWL.Restriction))
                g.add((bnode_cardinality, OWL.onProperty, IFC[inverse_attr_name]))
                g.add((bnode_cardinality, OWL.qualifiedCardinality,  Literal(1, datatype=XSD.nonNegativeInteger)))
                g.add((bnode_cardinality, OWL.onClass, IFC[reference_entity_name]))

            else:
                
                if bound2 != -1:
                    #set max  cardinality restriction if the set is upper-bounded
                    g.add((IFC[entity_name], RDFS.subClassOf, bnode_cardinality))
                    g.add((bnode_cardinality, RDF.type, OWL.Restriction))
                    g.add((bnode_cardinality, OWL.onProperty, IFC[inverse_attr_name]))
                    g.add((bnode_cardinality, OWL.maxQualifiedCardinality,  Literal(bound2, datatype=XSD.nonNegativeInteger)))
                    g.add((bnode_cardinality, OWL.onClass, IFC[reference_entity_name]))
                
                if bound2 == 1:
                    #set as functional property if the upper bound == 1.
                    g.add((IFC[inverse_attr_name], RDF.type,  OWL.FunctionalProperty))
                
                if bound1 !=0:
                    bnode_min_cardinality =BNode()
                    g.add((IFC[entity_name], RDFS.subClassOf, bnode_min_cardinality))
                    g.add((bnode_min_cardinality, RDF.type, OWL.Restriction))
                    g.add((bnode_min_cardinality, OWL.onProperty, IFC[inverse_attr_name]))
                    g.add((bnode_min_cardinality, OWL.minQualifiedCardinality,  Literal(bound1, datatype=XSD.nonNegativeInteger)))
                    g.add((bnode_min_cardinality, OWL.onClass, IFC[reference_entity_name]))

            # Assign inverseOf attributes
            g.add((IFC[inverse_attr_name], OWL.inverseOf,  IFC[inverse_of_attr_name]))
            g.add((IFC[inverse_of_attr_name], OWL.inverseOf,  IFC[inverse_attr_name]))    


path = output_path+schema_name.upper() + '.' + output_format
print(schema_name.upper())
g.serialize(destination= path , format =output_format)
