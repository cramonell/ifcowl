# IFC to OWL Conversion Tools

[IFC](https://www.buildingsmart.org/standards/bsi-standards/industry-foundation-classes/) (Industry Foundation Classes) is the open standard for exchanging building and infrastructure models in the AEC industry. [IfcOWL](https://technical.buildingsmart.org/standards/ifc/ifc-formats/ifcowl/) is its representation as an OWL ontology, enabling IFC data to be stored and queried as part of a semantic knowledge graph using standard web technologies (RDF, SPARQL, OWL).

This repository provides two Python tools that bridge IFC and the semantic web:

| Tool | Folder | What it does |
|---|---|---|
| **IFCExpress2OWL** | `ifcowl-gen/` | Generates an OWL ontology from an IFC EXPRESS schema definition |
| **IFC2RDF** | `IFC-converter/` | Converts an IFC building model file into an RDF graph conforming to ifcOWL |

**Key terms for readers new to semantic web:**
- **RDF** (Resource Description Framework) — a graph data model where everything is expressed as subject–predicate–object triples.
- **OWL** (Web Ontology Language) — a language for defining classes, properties, and rules on top of RDF.
- **Turtle** (`.ttl`) — a compact human-readable text format for writing RDF graphs.
- **SPARQL** — the query language for RDF graphs, analogous to SQL for relational databases.

Both tools use [ifcopenshell](https://ifcopenshell.org/) to parse IFC schemas and files, and [rdflib](https://rdflib.readthedocs.io/) to build and serialise RDF graphs.

---

## Requirements

- Python ≥ 3.9
- [ifcopenshell](https://ifcopenshell.org/) ≥ 0.7
- [rdflib](https://rdflib.readthedocs.io/) == 7.0.0

```bash
pip install -r requirements.txt
```

---

## IFC2RDF — Convert an IFC file to RDF

Reads an IFC instance file and produces an RDF graph (Turtle, N-Triples, or RDF/XML) whose individuals, types, and properties follow the ifcOWL ontology. Every IFC entity (walls, slabs, spaces, systems, materials, etc.) becomes a named node in the graph; every attribute becomes an RDF triple.

### Usage

```bash
cd IFC-converter/
python IFC2RDF.py path/to/model.ifc [--log-level LEVEL]
```

| Argument | Description | Default |
|---|---|---|
| `input` | Path to the IFC file. Overrides `ifc-file-path` in `config.json`. | — |
| `--log-level` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

**Example INFO output:**
```
2024-01-15 10:23:01 [INFO] File   : model.ifc  (1024000 bytes)
2024-01-15 10:23:01 [INFO] Schema : IFC4 → https://w3id.org/ifc/IFC4#
2024-01-15 10:23:01 [INFO] Output : ../tests/model.ttl
2024-01-15 10:23:01 [INFO] Load   : 0.21 s
2024-01-15 10:23:03 [INFO] Georeferencing (IFC4+): IfcMapConversion → EPSG:28992  origin (123456.789, 234567.890, 10.000)
2024-01-15 10:23:03 [INFO] Process: 2.14 s  (1840 entities, 18730 triples)
2024-01-15 10:23:03 [INFO] Serial : 0.31 s  → ../tests/model.ttl
2024-01-15 10:23:03 [INFO] Total  : 2.66 s
2024-01-15 10:23:03 [INFO] ────────────────────────────────────────────────────────────
2024-01-15 10:23:03 [INFO] File total     : 5240 entities
2024-01-15 10:23:03 [INFO] Filtered       : 3400 (excluded by config)
2024-01-15 10:23:03 [INFO] Top-level sent : 1840
2024-01-15 10:23:03 [INFO] Total created  : 1840 (incl. referenced entities)
2024-01-15 10:23:03 [INFO] Triples        : 18730
```

Use `--log-level DEBUG` to see a per-entity-type breakdown and a missing-entity audit after conversion.

### Configuration — `IFC-converter/config.json`

```jsonc
{
    "ifc-file-path": "",              // Path to IFC file. Leave empty and supply via CLI.
    "rdf-output": {
        "output-path": "../tests/",   // Directory where the .ttl output is saved
        "output-name": "",            // Output filename stem. Leave empty to auto-derive from IFC filename.
        "output-format": "ttl",       // Serialisation format: ttl | nt | rdf/xml
        "base-url": "https://example.org/assets/"  // Base URL for all instance URIs in the graph.
                                                   // Each entity gets a URI like <base-url>/<model-name>/<EntityType>_<id>
    },
    "geometry-output": {
        "convert": false,             // If true, export geometry files and add geometry triples to the graph
        "in-graph": false,            // If false (recommended): geometry goes to separate files; geometry resource
                                      //   layers are excluded from the RDF; OMG/FOG/GOM triples are added.
                                      // If true: the full IFC geometry representation is included in the RDF graph
                                      //   as ifcOWL triples (traditional approach); no separate files are exported
                                      //   and no OMG/FOG/GOM triples are added.
        "output-format": "glb",       // Geometry file format: glb | gltf | obj | ply | collada | stl | ifc
        "split": false,               // If false: one geometry file for the whole model (batch mode).
                                      // If true: one file per element, named by its IFC GlobalId (split mode).
        "apply-materials": false,     // If true, extract IFC material colours and apply them to geometry files.
                                      // Supported: glb, gltf, obj, collada, ply. Not supported: stl, ifc.
                                      // The material name is also recorded as a label in the RDF graph.
        "output-path": "../tests/",   // Directory where geometry files are written
                                      // Note: when output-format is "ifc", no conversion runs; the original IFC
                                      // file is used directly as the geometry reference.
        "geometry-base-url": ""       // Base URL for geometry file URIs in the RDF graph.
                                      //   (empty) — uses absolute file:// URIs resolved from output-path.
                                      //   "https://example.org/geom" — URIs become https://example.org/geom/{filename}.
                                      // Set this when geometry files are served over HTTP so the RDF URIs are
                                      // dereferenceable. Leave empty for local use.
    },
    "filters": {
        "resource": [],   // IFC resource-layer group names to exclude (see schema_structure/)
        "shared":   [],   // IFC shared-layer group names to exclude
        "domain":   [],   // IFC domain-layer group names to exclude
        "core":     [],   // IFC core-layer group names to exclude
        "entities": []    // Specific IFC entity type names to exclude (e.g. "IfcWall")
    }
}
```

Refer to [`IFC-converter/schema_structure/`](IFC-converter/schema_structure/) for available group names.

![IFC layers diagram](ifc-layers.png)

---

## Geometry management

By default, the converter produces only semantic (RDF) triples from the IFC file. When `geometry-output.convert` is `true`, it also exports the element geometries as 3D files and adds geometry metadata to the graph. This metadata uses four specialised ontologies — vocabularies that define agreed-upon terms for describing geometry on the semantic web:

| Prefix | Ontology | Role |
|---|---|---|
| `omg` | [Ontology for Managing Geometry (OMG)](http://w3id.org/omg#) | Links IFC elements to their geometry descriptions and versioned states |
| `fog` | [File Ontology for Geometry (FOG)](https://w3id.org/fog#) | Records a typed reference to the geometry file (e.g. `fog:asGltf` for GLB files) |
| `gom` | [Geometry Metadata Ontology (GOM)](https://w3id.org/gom#) | Stores quantitative metadata: vertex/face counts, file size, coordinate systems |
| `geo` | [GeoSPARQL 1.1](http://www.opengis.net/ont/geosparql#) | Expresses the real-world geospatial location of the project site |

### How geometry is represented in the graph

Each IFC element with a geometric representation gets three linked nodes in the graph — the element itself, a geometry description node, and a geometry state node that holds the actual file reference. This pattern (defined by OMG) separates the concept of "this element has geometry" from "here is the current version of that geometry", making it possible to track geometry changes over time.

```turtle
# The IFC element
inst:IfcWall_105
    omg:hasGeometry  inst:geom_105 .

# Geometry description: what kind of geometry, which coordinate system, which material
inst:geom_105
    a gom:MeshGeometry ;
    omg:hasGeometryState      inst:geomState_105 ;
    fog:hasIfcId-guid         "0qxeh3NRjCJQ6oBQBmgYRP"^^xsd:string ;
    rdfs:label                "Concrete" ;              # IFC material name (if apply-materials=true)
    gom:hasCoordinateSystem   inst:worldCoordSys .      # shared coordinate system node

# Geometry state: the current file reference and mesh statistics
inst:geomState_105
    a omg:CurrentGeometryState ;
    fog:asGltf       "https://example.org/geom/0qxeh3NRjCJQ6oBQBmgYRP.glb"^^xsd:anyURI ;
    gom:hasVertices  1248 ;
    gom:hasFaces     416 ;
    gom:hasFileSize  38400 .
```

The geometry file URI is controlled by `geometry-base-url`. When set to `"https://example.org/geom"`, URIs take the form `https://example.org/geom/{filename}` as shown above. When left empty, the converter writes an absolute `file://` URI resolved from the local output path.

Vertex/face counts and file size are only available in split mode (see below), where each element has its own geometry file.

### Batch vs split mode

The `split` config key controls how many geometry files are produced:

| Mode | `split` | Output | RDF |
|---|---|---|---|
| **Batch** | `false` | One geometry file for the whole model | All elements point to the same file URI; no per-element mesh statistics |
| **Split** | `true` | One file per element, named `{GlobalId}.{fmt}` in `output-path` | Each element has its own geometry state with vertex/face/size counts |

Split mode is necessary when individual elements need to be loaded or referenced independently (e.g. in a digital twin platform or asset management system).

### Coordinate systems and co-location

In IFC, each element's geometry is defined in a local coordinate system and then placed in the building by a chain of transformations. This converter resolves all those transformations and produces all element geometries in the single shared **IFC project coordinate frame**, so every vertex is already in the correct position relative to every other element.

A shared coordinate system node is always added to the graph when geometry is exported:

```turtle
inst:worldCoordSys
    a gom:CartesianCoordinateSystem ;
    rdfs:label "IFC Project Coordinate System" .
```

Every exported element links to it:

```turtle
inst:geom_105  gom:hasCoordinateSystem  inst:worldCoordSys .
inst:geom_189  gom:hasCoordinateSystem  inst:worldCoordSys .
```

This makes co-location **queryable**: a SPARQL query can find all geometry nodes that share `inst:worldCoordSys` and know they can be overlaid without any additional spatial transformation. This is especially important in split mode, where each element lives in its own file and the RDF graph is the only thing that ties them together spatially.

> **Note on file format axis conventions:** IFC uses a Z-up coordinate system. GLB/GLTF files are exported with a Y-up correction applied to the mesh vertices, as required by the GLTF specification. The `worldCoordSys` semantic node represents the IFC project coordinate frame; the Y-up convention is a file format detail implicit in the GLTF specification.

### Georeferencing

Georeferencing is the process of tying a local building coordinate system to a real-world location on Earth, so the model can be placed on a map or integrated with GIS data. When the IFC file contains georeferencing data, the converter automatically adds a GeoSPARQL location to the `IfcSite` entity (or `IfcProject` if no site is present). The data available differs by IFC version:

#### IFC4 and IFC4X3 — `IfcMapConversion`

IFC4 introduced `IfcMapConversion`, which defines a precise transformation from the local project coordinate system to a real-world CRS (Coordinate Reference System, e.g. EPSG:28992 Amersfoort/RD New — the Dutch national grid). EPSG codes are the industry-standard identifiers for coordinate reference systems.

The converter produces two additions to the graph:

1. A **GeoSPARQL point** placing the project origin on the map, expressed in WKT (Well-Known Text — a standard text format for geometry):

```turtle
inst:IfcSite_42
    a geo:Feature ;
    geo:hasGeometry  inst:projectOriginGeom .

inst:projectOriginGeom
    a geo:Geometry ;
    geo:asWKT
        "<http://www.opengis.net/def/crs/EPSG/0/28992> POINT Z (123456.789 234567.890 10.0)"^^geo:wktLiteral .
```

2. A **GOM transformation node** encoding the full affine mapping (translation + rotation + scale) from the IFC local system to the map CRS, expressed as a 4×4 matrix:

```turtle
inst:mapCoordSys
    a gom:CartesianCoordinateSystem ;
    rdfs:label "EPSG:28992" .

inst:ifcToMapTransform
    a gom:AffineCoordinateSystemTransformation ;
    gom:fromCartesianCoordinateSystem  inst:worldCoordSys ;
    gom:toCartesianCoordinateSystem    inst:mapCoordSys ;
    gom:hasTransformationMatrix
        "1.000000 0.000000 0.0 123456.789  0.000000 1.000000 0.0 234567.890  0.0 0.0 1.000000 10.000  0.0 0.0 0.0 1.0"^^gom:rowMajorArray .
```

#### IFC2X3 — `IfcSite.RefLatitude` / `RefLongitude`

IFC2X3 has no `IfcMapConversion`. The only available georeferencing is a rough site position stored as degrees/minutes/seconds on the `IfcSite` entity. The converter reads these values and produces a GeoSPARQL point in WGS84 (the global GPS coordinate system), using CRS84 (longitude, latitude axis order):

```turtle
inst:IfcSite_42
    a geo:Feature ;
    geo:hasGeometry  inst:projectOriginGeom .

inst:projectOriginGeom
    a geo:Geometry ;
    geo:asWKT
        "<http://www.opengis.net/def/crs/OGC/1.3/CRS84> POINT Z (-71.25807190 42.41486359 0.000)"^^geo:wktLiteral .
```

No transformation matrix is added for IFC2X3 files because the available data does not include rotation or scale.

#### No georeferencing

If neither mechanism is present in the IFC file, only the `inst:worldCoordSys` node is added. No GeoSPARQL triples are written.

### Multi-file integration

Large building projects are often split across multiple IFC files — one for the architectural model, one for MEP systems, one for structure. When each file is converted separately, each produces its own TTL with its own coordinate system node. To integrate them, a consumer can assert a transformation between the two coordinate system nodes specifying the offset (and rotation, if any) between the two local origins. If both files contain `IfcMapConversion` referencing the same CRS, their projected map coordinates can be used to estimate that offset — but only reliably when the two origins are geographically close (same site or same city). Map projections are 2D approximations of the Earth's curved surface: the scale factor varies by location, and the local North direction is not perfectly parallel between distant points. As a result, a Euclidean offset computed from projected coordinates accumulates error with distance. For buildings on the same site the error is typically negligible for BIM purposes; for buildings far apart the projected offset becomes an increasingly coarse approximation due to scale factor variation and meridian convergence.

### Material colours

When `apply-materials` is `true`, the converter extracts the colour assigned to each face of each element from the IFC material definitions and encodes them in the exported geometry file. Colours are applied per face without interpolation at material boundaries, so elements with multiple materials (e.g. a pipe with insulation) display correctly in viewers that support vertex colours.

The name of the primary material is also recorded as `rdfs:label` on the geometry node in the RDF graph.

---

## IFCExpress2OWL — Generate an OWL ontology from an IFC schema

IFC is defined using EXPRESS, a formal data modelling language. This tool reads the EXPRESS schema for any supported IFC version (via ifcopenshell) and generates the corresponding OWL ontology — the vocabulary that `IFC2RDF` uses to name types and properties in its output.

You only need this tool if you want to generate or inspect the ontology itself. The `IFC2RDF` converter works without running it, as the namespace URIs are already known.

### Usage

```bash
cd ifcowl-gen/
python IFCExpress2OWL.py
```

Schema version and output are controlled entirely by `config.json`.

### Configuration — `ifcowl-gen/config.json`

```jsonc
{
    "ifc-schema": "IFC4X3_Add2",    // ifcopenshell schema name (see Supported schemas below)
    "output-path": "./",             // Directory where the output file is saved
    "output-format": "ttl",          // Serialisation format: ttl | nt | rdf/xml
    "creators": [
        "Your Name (your@email.com)" // Appears in dce:creator of the generated ontology
    ],
    "contributors": []               // Appears in dce:contributor
}
```

---

## Supported IFC schemas

Both tools detect the IFC schema version automatically from the file header and resolve the corresponding w3id.org namespace URI. An unrecognised schema name produces a warning and falls back to `https://w3id.org/ifc/<SCHEMA_NAME>#`.

| IFC schema variant(s) | w3id.org namespace |
|---|---|
| `IFC4X3`, `IFC4X3_ADD2`, `IFC4X3_RC3` | `https://w3id.org/ifc/IFC4X3_ADD2#` |
| `IFC4` | `https://w3id.org/ifc/IFC4#` |
| `IFC4_ADD1` | `https://w3id.org/ifc/IFC4_ADD1#` |
| `IFC2X3`, `IFC2X3_TC1` | `https://w3id.org/ifc/IFC2X3_TC1#` |
| `IFC2X3_FINAL` | `https://w3id.org/ifc/IFC2X3_Final#` |

---

## Limitations

### Geometry

- **`in-graph=true` produces very large graphs.** When set to `true`, all IFC geometry representation entities are included in the RDF as ifcOWL triples (the traditional ifcOWL approach). This is valid but results in significantly larger output files and does not produce the OMG/FOG/GOM geometry metadata triples. The recommended approach is `in-graph=false` with separate geometry files.
- **Batch mode has no per-element mesh metadata.** Vertex count, face count, and file size are only populated in split mode. In batch mode all elements point to the same file and no individual statistics are recorded.
- **The GeoSPARQL location is a single point, not a footprint.** The `geo:asWKT` value represents the IFC project coordinate origin placed on the map — not the actual building outline or element boundaries. Geometric spatial queries (e.g. "which rooms contain this sensor?") are not supported.
- **Multi-file co-location is not automated.** Each conversion run produces an independent coordinate system node. Linking two separately-converted files into a shared spatial context requires a manually authored or externally computed transformation. The converter does not compare or merge coordinate systems across files.
- **Material colours and mesh metadata are not available in IFC passthrough mode.** The converter supports two geometry export paths: the built-in Python pipeline (ifcopenshell.geom + trimesh) and IFC passthrough (when `output-format` is `"ifc"`). Only the built-in pipeline tessellates the mesh, which is required for `apply-materials`, vertex/face counts, and file size recording. In IFC passthrough mode the original IFC file is used directly as the geometry reference and no mesh data is available.
- **Some complex geometry types may fail silently.** Certain IFC entity types (notably `IfcAnnotation` with curve-based representations) cannot be tessellated by ifcopenshell's geometry kernel. A warning is logged and the element is skipped; no geometry file or geometry triples are written for it.

### Georeferences

- **IFC2X3 georeferencing is approximate.** The latitude/longitude stored on `IfcSite` in IFC2X3 files is a coarse site pin with no CRS specification, rotation, or scale. It is suitable for placing a marker on a map but not for precise survey-grade integration.
- **The full transformation to a projected CRS is only available in IFC4+.** The `gom:AffineCoordinateSystemTransformation` matrix is produced only when the file contains an `IfcMapConversion` entity, which was introduced in IFC4.
- **Only the first `IfcSite` is georeferenced.** If the IFC file contains multiple `IfcSite` entities (uncommon in practice), only the first site's coordinates are used.
---

## License

This project is licensed under the GNU General Public License (GNU GPL).  
See [`LICENSE.txt`](LICENSE.txt) for the full text.
