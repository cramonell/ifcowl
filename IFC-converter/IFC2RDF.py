import ifcopenshell
import ifcopenshell.geom
from rdflib import Graph, Namespace, Literal, URIRef
import json
import os
import pathlib

script_dir = pathlib.Path(__file__).parent
config_path = (script_dir / 'config.json').resolve()
resource_path = (script_dir / 'schema_structure/resources.json').resolve()
domain_path = (script_dir / 'schema_structure/domain.json').resolve()
shared_path = (script_dir / 'schema_structure/shared.json').resolve()
core_path = (script_dir / 'schema_structure/core.json').resolve()

### PARAMETERS
with open(config_path, 'r',encoding='utf-8') as fp:
    params =json.load(fp)

file_path = params['ifc-file-path']

if params['rdf-output']['output-name']: asset_name = params['rdf-output']['output-name']
else: asset_name = file_path.split('/')[-1].split('.')[0]

if params['rdf-output']['output-path'].endswith('/'): save_path = params['rdf-output']['output-path'] + asset_name
else: save_path = params['rdf-output']['output-path'] + '/' + asset_name
print(save_path)

output_format = params['rdf-output']['output-format']

# load IFC file
file = ifcopenshell.open(file_path)
file_info = os.stat(file_path)
file_size_bytes = file_info.st_size
# load the IFC schema (EXPRESS)
schema_name = str(file.schema)
schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(file.schema)

#ontology ref specification
base_ifc_ref = "https://w3id.org/ifc/"
if schema_name.upper() == "IFC4X3": 
    ref_name = "IFC4X3_ADD2"
    base_url = "https://cramonell.github.io/ifc/ifcowl/IFC4X3_ADD2/actual/ontology.ttl"
elif schema_name.upper() == "IFC4X3_RC3":
    ref_name = "IFC4X3_ADD2"
    base_url = "https://cramonell.github.io/ifc/ifcowl/IFC4X3_ADD2/actual/ontology.ttl"
elif schema_name.upper() == "IFC4X3_ADD2":  
    ref_name = "IFC4X3_ADD2"
    base_url = "https://cramonell.github.io/ifc/ifcowl/IFC4X3_ADD2/actual/ontology.ttl"
elif schema_name.upper() == "IFC4": 
    ref_name = "IFC4"
    base_url = "https://pi.pauwel.be/evoc/ifc_W3ID/20151211/IFC4.ttl"
elif schema_name.upper() == "IFC2X3": 
    ref_name = "IFC2X3_TC1"
    base_url = "https://pi.pauwel.be/evoc/ifc_W3ID/20151211/IFC2X3_TC1.ttl"

if params['rdf-output']['base-url'].endswith('/'): asset_base_ref = params['rdf-output']['base-url'] + asset_name + '/'
else: asset_base_ref = params['rdf-output']['output-path'] + '/' + asset_name + '/'
asset_ref =  URIRef(asset_base_ref)
ifc_ref =  URIRef(base_ifc_ref +ref_name+"#")
print(ifc_ref)

#load ifcOwl ontology
ifc_graph = Graph()
ifc_graph.parse(base_url , format = 'turtle')

#filters
avoid_entities=params['filters']['entities']
avoid_resources = params['filters']['resource']
avoid_domains = params['filters']['domain']
avoid_shared = params['filters']['shared']
avoid_core = params['filters']['core']

with open(resource_path, 'r') as fp:
    resources =json.load(fp)
with open(shared_path, 'r') as fp:
    shared =json.load(fp)
with open(domain_path, 'r') as fp:
    domains =json.load(fp)
with open(core_path, 'r') as fp:
    core =json.load(fp)

if not params['geometry-output']['convert']:
    avoid_resources += [
    'IfcGeometricConstraintResource',
    'IfcGeometricModelResource',
    'IfcGeometryResource',
    'IfcPresentationOrganizationResource',
    'IfcPresentationAppearanceResource',
    'IfcTopologyResource',
    'IfcRepresentationResource'
]
elif params['geometry-output']['convert'] and not params['geometry-output']['in-graph']:
    avoid_resources += [
    'IfcGeometricConstraintResource',
    'IfcGeometricModelResource',
    'IfcGeometryResource',
    'IfcPresentationOrganizationResource',
    'IfcPresentationAppearanceResource',
    'IfcTopologyResource',
    'IfcRepresentationResource'
]

avoid = []
if avoid_resources: 
    for resource in avoid_resources:
        avoid+= resources[resource]['Entities']
if avoid_domains: 
    for domain in avoid_domains:
        avoid+= resources[resource]['Entities']
if avoid_shared: 
    for shrd in avoid_shared:
        avoid+= resources[shrd]['Entities']
if avoid_core: 
    for cr in avoid_core:
        avoid+= resources[cr]['Entities']

avoid += avoid_entities

# gets object property uris with label X of the entity class and its supertypes
def get_attr_object_property(entity, attr_name): 
    attr_query = """
        SELECT ?property WHERE {{
            {{ ?property rdfs:domain ?superclass .
            <{}> rdfs:subClassOf* ?superclass .
            ?property rdfs:label "{}" .}}
        }}""".format(entity, attr_name)
    
    print(entity, attr_name)
    # Execute the query
    results = ifc_graph.query(attr_query)
    # Print the results
    result  =  [item[0] for item in results]
    return result[0]


# Instantiate  empty  graph for the asset
g  = Graph()

# Create a namespaces
IFC = Namespace(ifc_ref)
INST = Namespace(asset_ref)
EXPRESS = Namespace('https://w3id.org/express#')
LIST = Namespace("https://w3id.org/list#")
OMG = Namespace("https://w3id.org/omg#")
FOG = Namespace("https://w3id.org/fog#")
GOM = Namespace("https://w3id.org/gom#")
DCE = Namespace("http://purl.org/dc/elements/1.1/")
VANN = Namespace("http://purl.org/vocab/vann/")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")

# Bind your custom prefix
g.bind("ifc", IFC)
g.bind('inst', INST)
g.bind('rdf', RDF)
g.bind('rdfs', RDFS)
g.bind('owl', OWL)
g.bind('vann', VANN)
g.bind('dce', DCE)
g.bind('xsd', XSD)
g.bind('express',EXPRESS)
g.bind('list', LIST)
g.bind('omg', OMG)
g.bind('fog', FOG)
g.bind('gom', GOM)

g.add((asset_ref, RDF.type, OWL.Ontology ))
g.add((asset_ref, OWL.imports, ifc_ref ))

created_types = {}
created_entities = {}
created_sets = []

# non-geometrical information
        
def untangle_named_type_declaration(attr_declared_type):
    last_declared_type = attr_declared_type.declared_type()
    if last_declared_type.declared_type().declared_type().as_named_type():
        untangle_named_type_declaration(last_declared_type.declared_type())
    else:
        return last_declared_type.declared_type().declared_type()

def process_named_aggregation_type(declared_list_type_name, declared_empty_list_type_name, attr_declaration, attr_value):

    declared_type =  attr_declaration.declared_type()
    
    type_of_element = declared_type.type_of_element()
    type_of_aggregation = declared_type.type_of_aggregation()
    bound1 = declared_type.bound1()
    bound2 = declared_type.bound2()
    
    try:
        attr_value = attr_value.wrappedValue
    except: pass

    declared_type_instance_uri = create_list(declared_list_type_name, declared_empty_list_type_name, bound1, bound2,  IFC[declared_list_type_name], IFC[declared_empty_list_type_name], type_of_element, attr_value)

    return declared_type_instance_uri

def process_named_simple_type(attr_instance_uri, attr_declared_type, attr_value):
    
    if isinstance(attr_value, ifcopenshell.entity_instance): 
        attr_value = attr_value.wrappedValue

    # Add express dataproperty depending on the declared type
    if attr_declared_type.declared_type() == 'string': g.add((attr_instance_uri, EXPRESS.hasString, Literal(attr_value)))
    elif attr_declared_type.declared_type() == 'binary': g.add((attr_instance_uri, EXPRESS.hasHexBinary, Literal(attr_value)))
    elif attr_declared_type.declared_type() == 'boolean': g.add((attr_instance_uri, EXPRESS.hasBoolean, Literal(attr_value)))
    elif attr_declared_type.declared_type() == 'integer': g.add((attr_instance_uri, EXPRESS.hasInteger, Literal(attr_value, datatype=XSD.integer)))
    elif attr_declared_type.declared_type() in ['number', 'real']: g.add((attr_instance_uri, EXPRESS.hasDouble, Literal(attr_value, datatype=XSD.double)))

def create_simple_type_attribute(instance_uri, object_property_uri, declared_type, attr_value):
    # create object URIs
    name =  declared_type.upper()
    if name not in created_types.keys(): created_types[name]=0
    declared_type_instance_uri = INST[name + '_' + str(created_types[name])]
    created_types[name] += 1
    declared_type_uri = EXPRESS[name]

    # Create triple for intanced declared type:
    g.add((declared_type_instance_uri, RDF.type, declared_type_uri))

    #create triple that links to the instanced ifc entity
    g.add((instance_uri, object_property_uri, declared_type_instance_uri))

    # Add express dataproperty depending on the declared type
    if declared_type == 'string': g.add((declared_type_instance_uri, EXPRESS.hasString, Literal(attr_value,datatype=XSD.string)))
    elif declared_type == 'binary': g.add((declared_type_instance_uri, EXPRESS.hasHexBinary, Literal(attr_value)))
    elif declared_type == 'boolean': g.add((declared_type_instance_uri, EXPRESS.hasBoolean, Literal(attr_value)))
    elif declared_type == 'integer': g.add((declared_type_instance_uri, EXPRESS.hasInteger, Literal(attr_value, datatype=XSD.integer)))
    elif declared_type in ['number', 'real']: g.add((declared_type_instance_uri, EXPRESS.hasDouble, Literal(attr_value, datatype=XSD.double)))

def create_named_type_attribute(instance_uri, object_property_uri, attr_declaration, attr_value):

    if attr_declaration.as_type_declaration():
        
        # create object URIs
        name = attr_declaration.name()
        if name not in created_types.keys(): created_types[name]=0

        # read type of attribute
        attr_declared_type = attr_declaration.declared_type()

        if attr_declared_type.as_aggregation_type():

            declared_list_type_name = name
            declared_empty_list_type_name = name + '_Empty'
            
            declared_type_instance_uri=process_named_aggregation_type(declared_list_type_name, declared_empty_list_type_name, attr_declaration, attr_value)         

            #create property triple
            g.add((instance_uri, object_property_uri, declared_type_instance_uri))

        elif attr_declared_type.as_simple_type():
            
            attr_instance_uri = INST[name + '_' + str(created_types[name])]
            created_types[name] += 1
            declared_type_uri = IFC[name]

            # Create triple for instanced declared type:
            g.add((attr_instance_uri, RDF.type, declared_type_uri))

            #create triple that links to the instanced ifc entity
            g.add((instance_uri, object_property_uri, attr_instance_uri))

            process_named_simple_type(attr_instance_uri, attr_declared_type, attr_value)

        elif attr_declared_type.as_named_type(): 

            attr_instance_uri = INST[name + '_' + str(created_types[name])]
            created_types[name] += 1
            declared_type_uri = IFC[name]

            last_declared_type = untangle_named_type_declaration(attr_declaration)

            if last_declared_type.as_simple_type():
                # Create triple for instanced declared type:
                g.add((attr_instance_uri, RDF.type, declared_type_uri))

                #create triple that links to the instanced ifc entity
                g.add((instance_uri, object_property_uri, attr_instance_uri))

                process_named_simple_type(attr_instance_uri, last_declared_type, attr_value)

            elif last_declared_type.as_aggregation_type():

                declared_list_type_name = name
                declared_empty_list_type_name = name + '_Empty'
                declared_type_instance_uri = process_named_aggregation_type(declared_list_type_name, declared_empty_list_type_name, last_declared_type, attr_value)
                #create property triple
                g.add((instance_uri, object_property_uri, declared_type_instance_uri))

    elif attr_declaration.as_enumeration_type() and attr_value != None:
        #check that if the value is part of an enumeration it fits  to the  prescribed enumeration values
        if attr_value not in attr_declaration.enumeration_items():
            print("\033[91mThe entity {} is malformed: {} of {} is not part an enumeration individual \033[0m".format(instance_uri, attr_value, object_property_uri))
        else:  g.add((instance_uri, object_property_uri, IFC[attr_value])) 

    elif attr_declaration.as_select_type()  and attr_value != None:
        entity_schema = schema.declaration_by_name(attr_value.is_a())
        create_named_type_attribute(instance_uri, object_property_uri, entity_schema, attr_value)
 
    elif attr_declaration.as_entity() and attr_value != None:
        
        if attr_value.is_a() not in avoid:
            property_item_uri = create_entity(attr_value)
            g.add((instance_uri, object_property_uri, property_item_uri)) 

def create_list(list_type_name, empty_list_type_name, bound1, bound2, declared_list_type_uri, declared_empty_list_type_uri, content_declared_type, value):
    if bound2 == -1 : bound2 = len(value)

    previous = None
    return_IRI = None

    for i in range(bound2):

        if i <= len(value)-1:
            
            if value[i] != None  :
                #add to created types and initialize counter
                if list_type_name not in created_types.keys(): created_types[list_type_name]=0
                list_instance_uri  = INST[list_type_name + '_' + str(created_types[list_type_name])]
                created_types[list_type_name] += 1

                # add hasnext property to the previous item
                if previous: g.add((previous, LIST.hasNext, list_instance_uri))
                if i == 0: return_IRI = list_instance_uri

                #add list as ifc type
                g.add((list_instance_uri, RDF.type, declared_list_type_uri))
                previous = list_instance_uri

            
                #create and add contents to the list
                if content_declared_type.as_named_type():
                    create_named_type_attribute(list_instance_uri, LIST.hasContents, content_declared_type.declared_type(),value[i])

                elif content_declared_type.as_simple_type():
                    create_simple_type_attribute(list_instance_uri, LIST.hasContents,content_declared_type.declared_type(), value[i])

            else:
                # #add to created types and initialize counter
                if empty_list_type_name not in created_types.keys(): created_types[empty_list_name]=0
                empty_list_instance_uri = INST[empty_list_type_name + '_' + str(created_types[empty_list_name])]
                created_types[empty_list_name]+=1

                # add hasnext property to the previous item
                if previous : g.add((previous, LIST.hasNext, empty_list_instance_uri))
                if i == 0: return_IRI = empty_list_instance_uri

                #add list as ifc type
                g.add((empty_list_instance_uri, RDF.type, declared_empty_list_type_uri))
                previous = empty_list_instance_uri       
        
        else:
            empty_list_name = list_type_name.split('_')[0] + '_EmptyList'
            if empty_list_name not in created_types.keys(): created_types[empty_list_name]=0
            empty_list_instance_uri = INST[empty_list_name + '_' + str(created_types[empty_list_name])]
            created_types[empty_list_name]+=1

            if previous : g.add((previous, LIST.hasNext, empty_list_instance_uri))
            if i == 0: return_IRI = empty_list_instance_uri

            g.add((empty_list_instance_uri, RDF.type, declared_empty_list_type_uri))
            previous = empty_list_instance_uri

    return return_IRI

def create_list_list(list_type_name, empty_list_type_name, bound1, bound2, declared_list_type_uri, declared_empty_list_type_uri, value):
    if bound2 == -1 : bound2 = len(value)

    previous = None
    return_IRI = None

    for i in range(bound2):
        if i <= len(value)-1:
            if value[i] != None  :
                if list_type_name not in created_types.keys(): created_types[list_type_name]=0
                list_instance_uri  = INST[list_type_name + '_' + str(created_types[list_type_name])]
                created_types[list_type_name] += 1

                if previous: g.add((previous, LIST.hasNext, list_instance_uri))
                if i == 0: return_IRI = list_instance_uri

                g.add((list_instance_uri, RDF.type, declared_list_type_uri))
                previous = list_instance_uri

                #create and add contents to the list
                g.add((list_instance_uri, LIST.hasContents, value[i]))            
                g.add((list_instance_uri, LIST.hasContents, value[i]))

            else:
                if empty_list_type_name not in created_types.keys(): created_types[empty_list_type_name]=0
                empty_list_instance_uri = INST[empty_list_type_name + '_' + str(created_types[empty_list_type_name])]
                created_types[empty_list_type_name]+=1

                if previous : g.add((previous, LIST.hasNext, empty_list_instance_uri))
                if i == 0: return_IRI = empty_list_instance_uri

                g.add((empty_list_instance_uri, RDF.type, declared_empty_list_type_uri))
                previous = empty_list_instance_uri       

        else:
            if empty_list_type_name not in created_types.keys(): created_types[empty_list_type_name]=0
            empty_list_instance_uri = INST[empty_list_type_name + '_' + str(created_types[empty_list_type_name])]
            created_types[empty_list_type_name]+=1

            if previous : g.add((previous, LIST.hasNext, empty_list_instance_uri))
            if i == 0: return_IRI = empty_list_instance_uri

            g.add((empty_list_instance_uri, RDF.type, declared_empty_list_type_uri))
            previous = empty_list_instance_uri

    return return_IRI

def create_aggregation_type(instance_uri, object_property_uri, declared_type, attr_value):
    type_of_element = declared_type.type_of_element()
    type_of_aggregation = declared_type.type_of_aggregation()
    bound1 = declared_type.bound1()
    bound2 = declared_type.bound2()

    if type_of_aggregation in [declared_type.array_type, declared_type.list_type]:        
        if type_of_element.as_simple_type(): #significa que lalista es el propiotipo.  no es necesario hacer _List
            
            content_declared_type_name  = type_of_element.declared_type().upper() 
            declared_list_type_name = content_declared_type_name + '_List'
            declared_empty_list_type_name = content_declared_type_name + '_EmptyList'
            
            declared_type_instance_uri = create_list(declared_list_type_name, declared_empty_list_type_name, bound1, bound2,  EXPRESS[declared_list_type_name], EXPRESS[declared_empty_list_type_name], type_of_element, attr_value)

            #create property triple
            g.add((instance_uri, object_property_uri, declared_type_instance_uri))
        
        elif type_of_element.as_named_type():
            content_declared_type_name = type_of_element.declared_type().name()
            declared_list_type_name = content_declared_type_name + '_List'
            declared_empty_list_type_name = content_declared_type_name + '_EmptyList'

            declared_type_instance_uri = create_list(declared_list_type_name, declared_empty_list_type_name, bound1, bound2,  IFC[declared_list_type_name], IFC[declared_empty_list_type_name], type_of_element, attr_value)
            
            #create property triple
            g.add((instance_uri, object_property_uri, declared_type_instance_uri))
        
        elif type_of_element.as_aggregation_type():
            
            # get element type in the list
            nested_type_of_element = type_of_element.type_of_element()

            #get bounds of the nested lists
            nested_bound1 = type_of_element.bound1()
            nested_bound2 = type_of_element.bound2()

            # create names for the list type and nested list type
            content_declared_type_name = nested_type_of_element.declared_type().name()
            declared_nested_list_type_name = content_declared_type_name + '_List'
            declared_nested_empty_list_type_name = content_declared_type_name + '_EmptyList'
            declared_list_type_name = declared_nested_list_type_name + '_List'
            declared_empty_list_type_name = declared_nested_list_type_name + '_EmptyList'
            
            nested_lists_list  =  []
            
            for nested_list in attr_value:
                nested_lists_list.append(create_list(declared_nested_list_type_name, declared_nested_empty_list_type_name,nested_bound1, nested_bound2, IFC[declared_nested_list_type_name], IFC[declared_nested_empty_list_type_name], nested_type_of_element, nested_list))
            
            declared_type_instance_uri =  create_list_list(declared_list_type_name, declared_empty_list_type_name, bound1, bound2,  IFC[declared_list_type_name], IFC[declared_empty_list_type_name], nested_lists_list)
            
            #create property triple
            g.add((instance_uri, object_property_uri, declared_type_instance_uri))


    elif type_of_aggregation == declared_type.set_type:

        if object_property_uri not in created_sets: created_sets.append(object_property_uri)

        for value in attr_value:

            if type_of_element.as_simple_type():
                content_name  = type_of_element.declared_type().upper()
                if content_name not in created_types.keys(): created_types[content_name]=0
                content_uri = INST[content_name + '_' + str(created_types[content_name])]
                created_types[content_name] += 1
                content_type_uri = EXPRESS[content_name]

                #create triple to instance the content type
                g.add((content_uri, RDF.type, content_type_uri))  

                create_simple_type_attribute(content_uri, type_of_element, type_of_element.declared_type(), value)
                
                #create property triple
                g.add((instance_uri, object_property_uri, content_uri))

            elif type_of_element.as_named_type():
                create_named_type_attribute(instance_uri, object_property_uri, type_of_element.declared_type(), value)
            

    elif type_of_aggregation == declared_type.bag_type:
        pass

    else: pass

def create_entity(entity)-> URIRef:
    print(len(created_entities.keys()))
    
    # get the  IFC definition of the entity
    entity_schema = schema.declaration_by_name(entity.is_a())

    entity_name = entity_schema.name()
    instance_name = entity_name + '_' + str(entity.id())

    entity_uri = IFC[entity_name]
    instance_uri = INST[instance_name]

    if instance_uri not in created_entities.keys(): 
        created_entities[instance_uri] = []

        #create instance
        g.add((instance_uri, RDF.type, entity_uri))
        #create instance attributes
        attr_count = entity_schema.attribute_count()

        for i in range(attr_count):

            attr =  entity_schema.attribute_by_index(i)

            # check that the object referenced and the attribute exists
            try:
                attr_value = entity[i]
            except RuntimeError:
                print("\033[91mThe entity of type {} with id #{} is malformed: referenced {} does not exist in file or is also malformed\033[0m".format(entity.is_a(), entity.id(), entity.attribute_name(i)))
                continue
            
            if not attr_value:
                if not attr.optional():
                    print("\033[91mThe entity of type {} with id #{} is malformed: referenced {} does not exist in file or is also malformed, and is not an optional attribute.\033[0m".format(entity.is_a(), entity.id(), entity.attribute_name(i)))
                    continue
                else: pass
            else:
                attr_name = attr.name()
                attr_type = attr.type_of_attribute()
                
                #get object property uri
                object_property_uri = get_attr_object_property(entity_uri, attr_name)

                if attr_type.as_simple_type():
                       
                    if object_property_uri not in created_entities[instance_uri]:
                        #add property to entity dict
                        created_entities[instance_uri].append(object_property_uri)
                        
                    create_simple_type_attribute(instance_uri, object_property_uri, attr_type.declared_type(), attr_value)

                elif attr_type.as_named_type():
                
                    if object_property_uri not in created_entities[instance_uri]:
                        #add property to entity dict
                        created_entities[instance_uri].append(object_property_uri)
                    
                    #create attr_type
                    create_named_type_attribute(instance_uri, object_property_uri, attr_type.declared_type(), attr_value)

                elif attr_type.as_aggregation_type():

                    if object_property_uri not in created_entities[instance_uri]:

                        #add property to entity dic
                        created_entities[instance_uri].append(object_property_uri)

                        #create attr_type
                        create_aggregation_type(instance_uri, object_property_uri, attr_type, attr_value)

        # get the inverse attributes 
        inverse_attributes =  entity_schema.all_inverse_attributes()
        for inv_attr  in inverse_attributes:

            inv_attr_name = inv_attr.name()
            inv_attr_uri = get_attr_object_property(entity_uri, inv_attr_name)

            content = getattr(entity, inv_attr.name())
            
            if content:
                for item in content:
                    if item.is_a() not in avoid:
                        item_name = item.is_a() + '_' + str(item.id())
                        item_uri = INST[item_name]
                        g.add((instance_uri, inv_attr_uri, item_uri))

    return instance_uri

## geometrical information TODO (still testing)

settings = ifcopenshell.geom.settings()

def create_geometry(entity, format,  output_path, output_name, file_size): #TODO other geometry formats
    go = output_path + output_name +"."+ format
    if hasattr(entity, 'Representation'):
        representation = entity.Representation
        geom_instance = INST['geom_'+ str(entity.id())]
        entity_instance = INST[entity.is_a()[3:]+ '_' + str(entity.id())]
        g.add((entity_instance, OMG.hasGeometry, geom_instance))
        g.add((geom_instance, RDF.type, GOM.MeshGeometry))
        g.add((geom_instance, GOM.hasFileSize, Literal(file_size, datatype=XSD.integer)))
        g.add((geom_instance, FOG['asIfc'], Literal(go, datatype = XSD.anyURI)))
        g.add((geom_instance, FOG['hasIfcId-guid'], Literal(entity.GlobalId, datatype = XSD.string)))

for entity in file:
    if entity.is_a() not in avoid:
        create_entity(entity)
        if params['geometry-output']['convert']: 
            create_geometry(entity, params['geometry-output']['output-format'], params['geometry-output']['output-path'], params['rdf-output']['output-name'],  file_size_bytes) 

# Save rdf asset
g.serialize(destination= save_path + '.' + output_format, format ='turtle')