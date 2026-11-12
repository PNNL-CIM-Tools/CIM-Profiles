# JSON-LD document cache

Offline copies of JSON-LD contexts and unit vocabularies, loaded by
`cimprofiles.jsonld.load_document`. `index.json` maps each URL (and each vocabulary's
`owl:versionIRI`) to a file here.

- `inst4cim/` — unmodified copies from [Sveino/Inst4CIM-KG](https://github.com/Sveino/Inst4CIM-KG)
  (`develop` branch), Apache License 2.0 (see `inst4cim/LICENSE`):
  - `rdf-improved/cim-context-old.jsonld`, `cim-context-new.jsonld`: instance-data contexts
    for the `http://iec.ch/TC57/CIM100#` and `https://cim.ucaiug.io/ns#` namespaces
  - `rdfs-improved/CIM-ontology-context.jsonld`: context of the vocabularies
  - `rdfs-improved/CGMES/jsonld/61970-600-2_*_v3-0-0.jsonld`: CGMES 3.0 vocabularies with
    `qudt:hasUnit` per property (Dynamics and Header are not included)
- `<profile>/<version>/` — contexts and unit vocabularies built by
  `python -m cimprofiles.jsonld.build` for each stable cim-profiles release, also published
  on GitHub Pages. Earlier versions stay: files written with them still name them.

To refresh `inst4cim/`, download the same files again and keep `index.json` entries in sync.
