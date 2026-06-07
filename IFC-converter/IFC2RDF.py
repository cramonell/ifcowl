import ifcopenshell
import ifcopenshell.geom
from rdflib import Graph, Namespace, Literal, URIRef
import json
import os
import pathlib
import argparse
import logging
import time
import subprocess
import numpy as np
import trimesh

script_dir = pathlib.Path(__file__).parent
config_path = (script_dir / 'config.json').resolve()
resource_path = (script_dir / 'schema_structure/resources.json').resolve()
domain_path = (script_dir / 'schema_structure/domain.json').resolve()
shared_path = (script_dir / 'schema_structure/shared.json').resolve()
core_path = (script_dir / 'schema_structure/core.json').resolve()

### PARAMETERS
with open(config_path, 'r', encoding='utf-8') as fp:
    params = json.load(fp)

_cli = argparse.ArgumentParser(description='Convert an IFC file to RDF/Turtle.')
_cli.add_argument('input', nargs='?', help='Path to IFC file (overrides config)')
_cli.add_argument('--log-level', default='INFO',
                  choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                  help='Logging verbosity (default: INFO)')
_cli_args = _cli.parse_args()

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=getattr(logging, _cli_args.log_level))
log = logging.getLogger('ifc2rdf')

_t0 = time.perf_counter()

file_path = _cli_args.input or params['ifc-file-path']

if params['rdf-output']['output-name']:
    asset_name = params['rdf-output']['output-name']
else:
    asset_name = pathlib.Path(file_path).stem

if params['rdf-output']['output-path'].endswith('/'):
    save_path = params['rdf-output']['output-path'] + asset_name
else:
    save_path = params['rdf-output']['output-path'] + '/' + asset_name

output_format = params['rdf-output']['output-format']

# --- Load IFC file and EXPRESS schema ---
file = ifcopenshell.open(file_path)
file_info = os.stat(file_path)
file_size_bytes = file_info.st_size
schema_name = str(file.schema)
schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(file.schema)

# --- Ontology namespace resolution ---
# Maps ifcopenshell schema names to their canonical ref_name under https://w3id.org/ifc/
# Ontology files are served via content-negotiation at https://w3id.org/ifc/{ref_name}
SCHEMA_REGISTRY = {
    # IFC4X3 family — https://w3id.org/ifc/IFC4X3_ADD2
    "IFC4X3":       "IFC4X3_ADD2",
    "IFC4X3_RC3":   "IFC4X3_ADD2",
    "IFC4X3_ADD2":  "IFC4X3_ADD2",
    # IFC4 family — https://w3id.org/ifc/IFC4  and  https://w3id.org/ifc/IFC4_ADD1
    "IFC4":         "IFC4",
    "IFC4_ADD1":    "IFC4_ADD1",
    # IFC2X3 family — https://w3id.org/ifc/IFC2X3_TC1  and  https://w3id.org/ifc/IFC2X3_Final
    "IFC2X3":       "IFC2X3_TC1",
    "IFC2X3_TC1":   "IFC2X3_TC1",
    "IFC2X3_FINAL": "IFC2X3_Final",
}

base_ifc_ref = "https://w3id.org/ifc/"
ref_name = SCHEMA_REGISTRY.get(schema_name.upper())
if ref_name is None:
    ref_name = schema_name.upper()
    log.warning("Unknown schema '%s', using fallback namespace", schema_name)

if params['rdf-output']['base-url'].endswith('/'):
    asset_base_ref = params['rdf-output']['base-url'] + asset_name + '/'
else:
    asset_base_ref = params['rdf-output']['base-url'] + '/' + asset_name + '/'
asset_ref = URIRef(asset_base_ref)
ifc_ref = URIRef(base_ifc_ref + ref_name + "#")

log.info("File   : %s  (%d bytes)", file_path, file_size_bytes)
log.info("Schema : %s → %s", schema_name, ifc_ref)
log.info("Output : %s.%s", save_path, output_format)
log.info("Load   : %.2f s", time.perf_counter() - _t0)

# --- Filters ---
avoid_entities = params['filters']['entities']
avoid_resources = params['filters']['resource']
avoid_domains = params['filters']['domain']
avoid_shared = params['filters']['shared']
avoid_core = params['filters']['core']

with open(resource_path, 'r') as fp:
    resources = json.load(fp)
with open(shared_path, 'r') as fp:
    shared = json.load(fp)
with open(domain_path, 'r') as fp:
    domains = json.load(fp)
with open(core_path, 'r') as fp:
    core = json.load(fp)

if not params['geometry-output']['convert']:
    avoid_resources += [
        'IfcGeometricConstraintResource',
        'IfcGeometricModelResource',
        'IfcGeometryResource',
        'IfcPresentationOrganizationResource',
        'IfcPresentationAppearanceResource',
        'IfcTopologyResource',
        'IfcRepresentationResource',
    ]
elif params['geometry-output']['convert'] and not params['geometry-output']['in-graph']:
    avoid_resources += [
        'IfcGeometricConstraintResource',
        'IfcGeometricModelResource',
        'IfcGeometryResource',
        'IfcPresentationOrganizationResource',
        'IfcPresentationAppearanceResource',
        'IfcTopologyResource',
        'IfcRepresentationResource',
    ]

avoid = set()
for resource in avoid_resources:
    avoid.update(resources[resource]['Entities'])
for domain in avoid_domains:
    avoid.update(domains[domain]['Entities'])
for shrd in avoid_shared:
    avoid.update(shared[shrd]['Entities'])
for cr in avoid_core:
    avoid.update(core[cr]['Entities'])
avoid.update(avoid_entities)

# --- Attribute URI cache (keyed by entity class name) ---
_attrs_cache = {}

def get_attributes_from_schema(entity_schema):
    """Build {attr_label: property_URI} from EXPRESS schema, following the ifcOWL naming convention.
    Results are cached per entity class name."""
    name = entity_schema.name()
    if name in _attrs_cache:
        return _attrs_cache[name]

    attrs = {}

    # Forward attributes: walk supertype chain; each attr is attributed to its declaring entity
    current = entity_schema
    while current:
        ename = current.name()
        for attr in current.attributes():
            label = attr.name()
            if label not in attrs:
                attrs[label] = IFC[label[0].lower() + label[1:] + '_' + ename]
        current = current.supertype()

    # Inverse attributes: walk chain from root to entity;
    # first ancestor to expose an inverse attr is its declaring entity
    chain = []
    current = entity_schema
    while current:
        chain.append(current)
        current = current.supertype()
    chain.reverse()

    seen_inv = set()
    for ancestor in chain:
        ename = ancestor.name()
        for inv in ancestor.all_inverse_attributes():
            label = inv.name()
            if label not in seen_inv:
                seen_inv.add(label)
                attrs[label] = IFC[label[0].lower() + label[1:] + '_' + ename]

    _attrs_cache[name] = attrs
    return attrs

# --- RDF graph and namespaces ---
g = Graph()

IFC = Namespace(ifc_ref)
INST = Namespace(asset_ref)
EXPRESS = Namespace('https://w3id.org/express#')
LIST = Namespace("https://w3id.org/list#")
OMG = Namespace("http://w3id.org/omg#")
FOG = Namespace("https://w3id.org/fog#")
GOM = Namespace("https://w3id.org/gom#")
DCE = Namespace("http://purl.org/dc/elements/1.1/")
VANN = Namespace("http://purl.org/vocab/vann/")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")

g.bind("ifc", IFC)
g.bind('inst', INST)
g.bind('rdf', RDF)
g.bind('rdfs', RDFS)
g.bind('owl', OWL)
g.bind('vann', VANN)
g.bind('dce', DCE)
g.bind('xsd', XSD)
g.bind('express', EXPRESS)
g.bind('list', LIST)
g.bind('omg', OMG)
g.bind('fog', FOG)
g.bind('gom', GOM)

g.add((asset_ref, RDF.type, OWL.Ontology))
g.add((asset_ref, OWL.imports, ifc_ref))

# Counters and dedup trackers
created_types = {}
created_entities = {}   # instance_uri → set of property URIs already written
created_sets = set()    # set of object_property_uris already used as set-type properties


def untangle_named_type_declaration(attr_declared_type):
    inner = attr_declared_type.declared_type()
    inner2 = inner.declared_type()
    inner3 = inner2.declared_type()
    if inner3.as_named_type():
        return untangle_named_type_declaration(inner2)
    return inner3


def process_named_aggregation_type(declared_list_type_name, declared_empty_list_type_name, attr_declaration, attr_value):
    declared_type = attr_declaration.declared_type()
    type_of_element = declared_type.type_of_element()
    bound1 = declared_type.bound1()
    bound2 = declared_type.bound2()

    try:
        attr_value = attr_value.wrappedValue
    except Exception:
        pass

    return create_list(declared_list_type_name, declared_empty_list_type_name, bound1, bound2,
                       IFC[declared_list_type_name], IFC[declared_empty_list_type_name],
                       type_of_element, attr_value)


def process_named_simple_type(attr_instance_uri, attr_declared_type, attr_value):
    if isinstance(attr_value, ifcopenshell.entity_instance):
        attr_value = attr_value.wrappedValue

    dt = attr_declared_type.declared_type()
    if dt == 'string':
        g.add((attr_instance_uri, EXPRESS.hasString, Literal(attr_value)))
    elif dt == 'binary':
        g.add((attr_instance_uri, EXPRESS.hasHexBinary, Literal(attr_value)))
    elif dt == 'boolean':
        g.add((attr_instance_uri, EXPRESS.hasBoolean, Literal(attr_value)))
    elif dt == 'integer':
        g.add((attr_instance_uri, EXPRESS.hasInteger, Literal(attr_value, datatype=XSD.integer)))
    elif dt in ('number', 'real'):
        g.add((attr_instance_uri, EXPRESS.hasDouble, Literal(attr_value, datatype=XSD.double)))


def create_simple_type_attribute(instance_uri, object_property_uri, declared_type, attr_value):
    name = declared_type.upper()
    if name not in created_types:
        created_types[name] = 0
    declared_type_instance_uri = INST[name + '_' + str(created_types[name])]
    created_types[name] += 1

    g.add((declared_type_instance_uri, RDF.type, EXPRESS[name]))
    g.add((instance_uri, object_property_uri, declared_type_instance_uri))

    if declared_type == 'string':
        g.add((declared_type_instance_uri, EXPRESS.hasString, Literal(attr_value, datatype=XSD.string)))
    elif declared_type == 'binary':
        g.add((declared_type_instance_uri, EXPRESS.hasHexBinary, Literal(attr_value)))
    elif declared_type == 'boolean':
        g.add((declared_type_instance_uri, EXPRESS.hasBoolean, Literal(attr_value)))
    elif declared_type == 'integer':
        g.add((declared_type_instance_uri, EXPRESS.hasInteger, Literal(attr_value, datatype=XSD.integer)))
    elif declared_type in ('number', 'real'):
        g.add((declared_type_instance_uri, EXPRESS.hasDouble, Literal(attr_value, datatype=XSD.double)))


def create_named_type_attribute(instance_uri, object_property_uri, attr_declaration, attr_value):

    if attr_declaration.as_type_declaration():
        name = attr_declaration.name()
        if name not in created_types:
            created_types[name] = 0

        attr_declared_type = attr_declaration.declared_type()

        if attr_declared_type.as_aggregation_type():
            declared_type_instance_uri = process_named_aggregation_type(
                name, name + '_Empty', attr_declaration, attr_value)
            g.add((instance_uri, object_property_uri, declared_type_instance_uri))

        elif attr_declared_type.as_simple_type():
            attr_instance_uri = INST[name + '_' + str(created_types[name])]
            created_types[name] += 1
            g.add((attr_instance_uri, RDF.type, IFC[name]))
            g.add((instance_uri, object_property_uri, attr_instance_uri))
            process_named_simple_type(attr_instance_uri, attr_declared_type, attr_value)

        elif attr_declared_type.as_named_type():
            attr_instance_uri = INST[name + '_' + str(created_types[name])]
            created_types[name] += 1
            last_declared_type = untangle_named_type_declaration(attr_declaration)

            if last_declared_type.as_simple_type():
                g.add((attr_instance_uri, RDF.type, IFC[name]))
                g.add((instance_uri, object_property_uri, attr_instance_uri))
                process_named_simple_type(attr_instance_uri, last_declared_type, attr_value)

            elif last_declared_type.as_aggregation_type():
                declared_type_instance_uri = process_named_aggregation_type(
                    name, name + '_Empty', last_declared_type, attr_value)
                g.add((instance_uri, object_property_uri, declared_type_instance_uri))

    elif attr_declaration.as_enumeration_type() and attr_value is not None:
        if attr_value not in attr_declaration.enumeration_items():
            log.warning("Enumeration mismatch: %s on %s is not a valid individual for %s",
                        attr_value, instance_uri, object_property_uri)
        else:
            g.add((instance_uri, object_property_uri, IFC[attr_value]))

    elif attr_declaration.as_select_type() and attr_value is not None:
        entity_schema = schema.declaration_by_name(attr_value.is_a())
        create_named_type_attribute(instance_uri, object_property_uri, entity_schema, attr_value)

    elif attr_declaration.as_entity() and attr_value is not None:
        if attr_value.is_a() not in avoid:
            property_item_uri = create_entity(attr_value)
            g.add((instance_uri, object_property_uri, property_item_uri))


def create_list(list_type_name, empty_list_type_name, bound1, bound2,
                declared_list_type_uri, declared_empty_list_type_uri, content_declared_type, value):
    if bound2 == -1:
        bound2 = len(value)

    previous = None
    return_IRI = None

    for i in range(bound2):

        if i <= len(value) - 1:

            if value[i] is not None:
                if list_type_name not in created_types:
                    created_types[list_type_name] = 0
                list_instance_uri = INST[list_type_name + '_' + str(created_types[list_type_name])]
                created_types[list_type_name] += 1

                if previous:
                    g.add((previous, LIST.hasNext, list_instance_uri))
                if i == 0:
                    return_IRI = list_instance_uri

                g.add((list_instance_uri, RDF.type, declared_list_type_uri))
                previous = list_instance_uri

                if content_declared_type.as_named_type():
                    create_named_type_attribute(list_instance_uri, LIST.hasContents,
                                                content_declared_type.declared_type(), value[i])
                elif content_declared_type.as_simple_type():
                    create_simple_type_attribute(list_instance_uri, LIST.hasContents,
                                                 content_declared_type.declared_type(), value[i])

            else:
                if empty_list_type_name not in created_types:
                    created_types[empty_list_type_name] = 0
                empty_list_instance_uri = INST[empty_list_type_name + '_' + str(created_types[empty_list_type_name])]
                created_types[empty_list_type_name] += 1

                if previous:
                    g.add((previous, LIST.hasNext, empty_list_instance_uri))
                if i == 0:
                    return_IRI = empty_list_instance_uri

                g.add((empty_list_instance_uri, RDF.type, declared_empty_list_type_uri))
                previous = empty_list_instance_uri

        else:
            empty_list_name = empty_list_type_name
            if empty_list_name not in created_types:
                created_types[empty_list_name] = 0
            empty_list_instance_uri = INST[empty_list_name + '_' + str(created_types[empty_list_name])]
            created_types[empty_list_name] += 1

            if previous:
                g.add((previous, LIST.hasNext, empty_list_instance_uri))
            if i == 0:
                return_IRI = empty_list_instance_uri

            g.add((empty_list_instance_uri, RDF.type, declared_empty_list_type_uri))
            previous = empty_list_instance_uri

    return return_IRI


def create_list_list(list_type_name, empty_list_type_name, bound1, bound2,
                     declared_list_type_uri, declared_empty_list_type_uri, value):
    if bound2 == -1:
        bound2 = len(value)

    previous = None
    return_IRI = None

    for i in range(bound2):
        if i <= len(value) - 1:
            if value[i] is not None:
                if list_type_name not in created_types:
                    created_types[list_type_name] = 0
                list_instance_uri = INST[list_type_name + '_' + str(created_types[list_type_name])]
                created_types[list_type_name] += 1

                if previous:
                    g.add((previous, LIST.hasNext, list_instance_uri))
                if i == 0:
                    return_IRI = list_instance_uri

                g.add((list_instance_uri, RDF.type, declared_list_type_uri))
                previous = list_instance_uri
                g.add((list_instance_uri, LIST.hasContents, value[i]))

            else:
                if empty_list_type_name not in created_types:
                    created_types[empty_list_type_name] = 0
                empty_list_instance_uri = INST[empty_list_type_name + '_' + str(created_types[empty_list_type_name])]
                created_types[empty_list_type_name] += 1

                if previous:
                    g.add((previous, LIST.hasNext, empty_list_instance_uri))
                if i == 0:
                    return_IRI = empty_list_instance_uri

                g.add((empty_list_instance_uri, RDF.type, declared_empty_list_type_uri))
                previous = empty_list_instance_uri

        else:
            if empty_list_type_name not in created_types:
                created_types[empty_list_type_name] = 0
            empty_list_instance_uri = INST[empty_list_type_name + '_' + str(created_types[empty_list_type_name])]
            created_types[empty_list_type_name] += 1

            if previous:
                g.add((previous, LIST.hasNext, empty_list_instance_uri))
            if i == 0:
                return_IRI = empty_list_instance_uri

            g.add((empty_list_instance_uri, RDF.type, declared_empty_list_type_uri))
            previous = empty_list_instance_uri

    return return_IRI


def create_aggregation_type(instance_uri, object_property_uri, declared_type, attr_value):
    type_of_element = declared_type.type_of_element()
    type_of_aggregation = declared_type.type_of_aggregation()
    bound1 = declared_type.bound1()
    bound2 = declared_type.bound2()

    if type_of_aggregation in (declared_type.array_type, declared_type.list_type):

        if type_of_element.as_simple_type():
            content_declared_type_name = type_of_element.declared_type().upper()
            declared_list_type_name = content_declared_type_name + '_List'
            declared_empty_list_type_name = content_declared_type_name + '_EmptyList'
            declared_type_instance_uri = create_list(
                declared_list_type_name, declared_empty_list_type_name, bound1, bound2,
                EXPRESS[declared_list_type_name], EXPRESS[declared_empty_list_type_name],
                type_of_element, attr_value)
            g.add((instance_uri, object_property_uri, declared_type_instance_uri))

        elif type_of_element.as_named_type():
            content_declared_type_name = type_of_element.declared_type().name()
            declared_list_type_name = content_declared_type_name + '_List'
            declared_empty_list_type_name = content_declared_type_name + '_EmptyList'
            declared_type_instance_uri = create_list(
                declared_list_type_name, declared_empty_list_type_name, bound1, bound2,
                IFC[declared_list_type_name], IFC[declared_empty_list_type_name],
                type_of_element, attr_value)
            g.add((instance_uri, object_property_uri, declared_type_instance_uri))

        elif type_of_element.as_aggregation_type():
            nested_type_of_element = type_of_element.type_of_element()
            nested_bound1 = type_of_element.bound1()
            nested_bound2 = type_of_element.bound2()

            content_declared_type_name = nested_type_of_element.declared_type().name()
            declared_nested_list_type_name = content_declared_type_name + '_List'
            declared_nested_empty_list_type_name = content_declared_type_name + '_EmptyList'
            declared_list_type_name = declared_nested_list_type_name + '_List'
            declared_empty_list_type_name = declared_nested_list_type_name + '_EmptyList'

            nested_lists_list = [
                create_list(declared_nested_list_type_name, declared_nested_empty_list_type_name,
                            nested_bound1, nested_bound2,
                            IFC[declared_nested_list_type_name], IFC[declared_nested_empty_list_type_name],
                            nested_type_of_element, nested_list)
                for nested_list in attr_value
            ]
            declared_type_instance_uri = create_list_list(
                declared_list_type_name, declared_empty_list_type_name, bound1, bound2,
                IFC[declared_list_type_name], IFC[declared_empty_list_type_name], nested_lists_list)
            g.add((instance_uri, object_property_uri, declared_type_instance_uri))

    elif type_of_aggregation == declared_type.set_type:
        created_sets.add(object_property_uri)

        for value in attr_value:
            if type_of_element.as_simple_type():
                content_name = type_of_element.declared_type().upper()
                if content_name not in created_types:
                    created_types[content_name] = 0
                content_uri = INST[content_name + '_' + str(created_types[content_name])]
                created_types[content_name] += 1

                g.add((content_uri, RDF.type, EXPRESS[content_name]))
                process_named_simple_type(content_uri, type_of_element, value)
                g.add((instance_uri, object_property_uri, content_uri))

            elif type_of_element.as_named_type():
                create_named_type_attribute(instance_uri, object_property_uri,
                                            type_of_element.declared_type(), value)

    elif type_of_aggregation == declared_type.bag_type:
        # BAG allows duplicates; in RDF both bag and set are represented as repeated assertions
        created_sets.add(object_property_uri)
        for value in attr_value:
            if type_of_element.as_simple_type():
                content_name = type_of_element.declared_type().upper()
                if content_name not in created_types:
                    created_types[content_name] = 0
                content_uri = INST[content_name + '_' + str(created_types[content_name])]
                created_types[content_name] += 1
                g.add((content_uri, RDF.type, EXPRESS[content_name]))
                process_named_simple_type(content_uri, type_of_element, value)
                g.add((instance_uri, object_property_uri, content_uri))
            elif type_of_element.as_named_type():
                create_named_type_attribute(instance_uri, object_property_uri,
                                            type_of_element.declared_type(), value)


def create_entity(entity) -> URIRef:
    entity_schema = schema.declaration_by_name(entity.is_a())
    entity_name = entity_schema.name()
    instance_name = entity_name + '_' + str(entity.id())
    entity_uri = IFC[entity_name]
    instance_uri = INST[instance_name]

    log.debug("Processing %s", instance_uri)

    if instance_uri not in created_entities:
        created_entities[instance_uri] = set()

        g.add((instance_uri, RDF.type, entity_uri))
        attr_count = entity_schema.attribute_count()
        attrs = get_attributes_from_schema(entity_schema)

        for i in range(attr_count):
            attr = entity_schema.attribute_by_index(i)

            try:
                attr_value = entity[i]
            except RuntimeError:
                log.warning("Entity %s#%d malformed: attribute '%s' does not exist in file",
                            entity.is_a(), entity.id(), entity.attribute_name(i))
                continue

            if not attr_value:
                if not attr.optional():
                    log.warning("Entity %s#%d malformed: non-optional attribute '%s' is missing",
                                entity.is_a(), entity.id(), entity.attribute_name(i))
                continue

            attr_name = attr.name()
            attr_type = attr.type_of_attribute()

            if attr_name not in attrs:
                log.warning("Attribute '%s' has no property URI for %s — skipped", attr_name, entity_uri)
                continue
            object_property_uri = attrs[attr_name]

            if attr_type.as_simple_type():
                created_entities[instance_uri].add(object_property_uri)
                create_simple_type_attribute(instance_uri, object_property_uri,
                                             attr_type.declared_type(), attr_value)

            elif attr_type.as_named_type():
                created_entities[instance_uri].add(object_property_uri)
                create_named_type_attribute(instance_uri, object_property_uri,
                                            attr_type.declared_type(), attr_value)

            elif attr_type.as_aggregation_type():
                if object_property_uri not in created_entities[instance_uri]:
                    created_entities[instance_uri].add(object_property_uri)
                    create_aggregation_type(instance_uri, object_property_uri, attr_type, attr_value)

        # Inverse attributes
        for inv_attr in entity_schema.all_inverse_attributes():
            inv_attr_name = inv_attr.name()
            if inv_attr_name not in attrs:
                log.warning("Inverse attribute '%s' has no property URI for %s — skipped",
                            inv_attr_name, entity_uri)
                continue
            inv_attr_uri = attrs[inv_attr_name]
            content = getattr(entity, inv_attr_name)
            if content:
                for item in content:
                    if item.is_a() not in avoid:
                        item_uri = INST[item.is_a() + '_' + str(item.id())]
                        g.add((instance_uri, inv_attr_uri, item_uri))

    return instance_uri


# --- Geometry ---

_geom_settings = ifcopenshell.geom.settings()
_geom_settings.set(_geom_settings.USE_WORLD_COORDS, True)

# Maps output-format → FOG property URI
FOG_PROPERTY = {
    'ifc':     FOG['asIfc'],
    'obj':     FOG['asObj'],
    'glb':     FOG['asGltf'],
    'gltf':    FOG['asGltf'],
    'stl':     FOG['asStl'],
    'ply':     FOG['asPly'],
    'collada': FOG['asCollada'],
    'dae':     FOG['asCollada'],
}

def _shape_to_trimesh(shape):
    verts = np.array(shape.geometry.verts).reshape(-1, 3)
    faces = np.array(shape.geometry.faces).reshape(-1, 3)
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)

def _add_geometry_triples(entity, file_uri, fmt, mesh=None):
    """Write OMG/FOG/GOM triples for one entity using the three-node OMG pattern."""
    fog_prop       = FOG_PROPERTY.get(fmt, FOG['asIfc'])
    entity_uri     = INST[entity.is_a() + '_' + str(entity.id())]
    geom_uri       = INST['geom_'      + str(entity.id())]
    geom_state_uri = INST['geomState_' + str(entity.id())]

    g.add((entity_uri,     OMG.hasGeometry,     geom_uri))
    g.add((geom_uri,       RDF.type,             GOM.MeshGeometry))
    g.add((geom_uri,       OMG.hasGeometryState, geom_state_uri))
    g.add((geom_state_uri, RDF.type,             OMG.CurrentGeometryState))
    g.add((geom_state_uri, fog_prop,             Literal(file_uri, datatype=XSD.anyURI)))

    if hasattr(entity, 'GlobalId'):
        g.add((geom_uri, FOG['hasIfcId-guid'], Literal(entity.GlobalId, datatype=XSD.string)))

    if mesh is not None:
        g.add((geom_state_uri, GOM.hasVertices,
               Literal(len(mesh.vertices), datatype=XSD.nonNegativeInteger)))
        g.add((geom_state_uri, GOM.hasFaces,
               Literal(len(mesh.faces), datatype=XSD.nonNegativeInteger)))
        if os.path.exists(file_uri):
            g.add((geom_state_uri, GOM.hasFileSize,
                   Literal(os.path.getsize(file_uri), datatype=XSD.nonNegativeInteger)))

def _run_external_converter(converter, args):
    cmd = [converter] + args
    log.debug("External geometry converter: %s", ' '.join(cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            log.warning("Converter exited %d: %s", r.returncode, r.stderr.strip())
    except FileNotFoundError:
        log.error("Geometry converter '%s' not found — skipping file export", converter)
    except subprocess.TimeoutExpired:
        log.warning("Geometry converter timed out")

def export_geometry_batch(ifc_file_obj, ifc_path, entities_with_repr,
                          fmt, output_path, output_name, converter):
    """Export all element geometry to one file; write RDF triples for each entity."""
    os.makedirs(output_path, exist_ok=True)
    out_file = os.path.join(output_path, output_name + '.' + fmt)

    if fmt == 'ifc':
        out_file = ifc_path       # the IFC file itself is the geometry source
    elif converter:
        _run_external_converter(converter, [ifc_path, out_file])
    else:
        scene = trimesh.Scene()
        it = ifcopenshell.geom.iterator(_geom_settings, ifc_file_obj)
        if it.initialize():
            while True:
                shape = it.get()
                mesh = _shape_to_trimesh(shape)
                scene.add_geometry(mesh, node_name=str(shape.id))
                if not it.next():
                    break
        scene.export(out_file)

    for entity in entities_with_repr:
        _add_geometry_triples(entity, out_file, fmt)
    log.info("Geometry (batch): %d entities → %s", len(entities_with_repr), out_file)

def export_geometry_split(ifc_file_obj, ifc_path, entity, fmt, output_path, converter):
    """Export geometry for one entity to its own file; write RDF triples."""
    if not hasattr(entity, 'GlobalId'):
        return
    os.makedirs(output_path, exist_ok=True)
    out_file = os.path.join(output_path, entity.GlobalId + '.' + fmt)
    mesh = None

    if fmt == 'ifc':
        out_file = ifc_path
    elif converter:
        _run_external_converter(converter, [ifc_path, out_file,
                                            '--include', 'attribute', 'GlobalId', entity.GlobalId])
    else:
        try:
            shape = ifcopenshell.geom.create_shape(_geom_settings, entity)
            mesh = _shape_to_trimesh(shape)
            mesh.export(out_file)
        except Exception as e:
            log.warning("Geometry extraction failed for %s#%d: %s",
                        entity.is_a(), entity.id(), e)
            return

    _add_geometry_triples(entity, out_file, fmt, mesh=mesh)


# --- Main conversion loop ---
_t1 = time.perf_counter()
_total_in_file = 0
_filtered_count = 0
_main_loop_count = 0
_type_counts = {}
_expected_uris = set()

for entity in file:
    _total_in_file += 1
    etype = entity.is_a()
    _type_counts[etype] = _type_counts.get(etype, 0) + 1

    if etype not in avoid:
        _main_loop_count += 1
        _expected_uris.add(INST[etype + '_' + str(entity.id())])
        create_entity(entity)
        if _main_loop_count % 500 == 0:
            log.info("Progress: %d entities processed (%d triples so far)", _main_loop_count, len(g))
    else:
        _filtered_count += 1

_t2 = time.perf_counter()
log.info("Process: %.2f s  (%d entities, %d triples)", _t2 - _t1, _main_loop_count, len(g))

# --- Geometry export (post-loop) ---
_geom_cfg  = params['geometry-output']
_geom_fmt  = _geom_cfg['output-format']
_geom_path = _geom_cfg['output-path']
_geom_split = _geom_cfg.get('split', False)
_geom_conv  = _geom_cfg.get('converter', '')

if _geom_cfg['convert'] and not _geom_cfg['in-graph']:
    _repr_entities = [e for e in file
                      if e.is_a() not in avoid
                      and hasattr(e, 'Representation') and e.Representation]
    if _geom_split:
        for _e in _repr_entities:
            export_geometry_split(file, file_path, _e, _geom_fmt, _geom_path, _geom_conv)
    else:
        export_geometry_batch(file, file_path, _repr_entities,
                              _geom_fmt, _geom_path, asset_name, _geom_conv)

# --- Serialise ---
g.serialize(destination=save_path + '.' + output_format, format='turtle')
_t3 = time.perf_counter()
log.info("Serial : %.2f s  → %s.%s", _t3 - _t2, save_path, output_format)
log.info("Total  : %.2f s", _t3 - _t0)

# --- Summary ---
_converted_count = len(created_entities)
log.info("─" * 60)
log.info("File total     : %d entities", _total_in_file)
log.info("Filtered       : %d (excluded by config)", _filtered_count)
log.info("Top-level sent : %d", _main_loop_count)
log.info("Total created  : %d (incl. referenced entities)", _converted_count)
log.info("Triples        : %d", len(g))

# --- DEBUG: per-type breakdown and missing-entity audit ---
if log.isEnabledFor(logging.DEBUG):
    log.debug("─── Entity type breakdown ───")
    for etype in sorted(_type_counts):
        status = 'FILTERED' if etype in avoid else 'INCLUDED'
        log.debug("  [%s]  %-45s  %d", status, etype, _type_counts[etype])

    missing = _expected_uris - set(created_entities.keys())
    if missing:
        log.debug("─── %d top-level entities not created ───", len(missing))
        for uri in sorted(str(u) for u in missing):
            log.debug("  MISSING: %s", uri)
    else:
        log.debug("─── All top-level entities created successfully ───")
