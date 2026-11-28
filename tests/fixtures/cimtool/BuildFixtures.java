import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import au.com.langdale.kena.Format;
import au.com.langdale.kena.IO;
import au.com.langdale.kena.ModelFactory;
import au.com.langdale.kena.OntModel;
import au.com.langdale.kena.OntResource;
import au.com.langdale.kena.ResIterator;
import au.com.langdale.profiles.ProfileClass;
import au.com.langdale.profiles.ProfileModel;
import au.com.langdale.profiles.Refactory;
import au.com.langdale.profiles.SelectionOption;
import au.com.langdale.profiles.SelectionOptions;
import au.com.langdale.profiles.cl.CLISchemaParser;
import au.com.langdale.profiles.cl.CLISettings;

import com.hp.hpl.jena.vocabulary.OWL;

/**
 * Writes the test profiles test_a.owl, test_b.owl and test_c.owl with the CIMTool profile API,
 * as the Eclipse profile editor would, against the CIMTool-Test-Project schema.
 *
 * The .owl files are committed and immutable: run this only to change what the fixtures cover
 * (see tests/fixtures/README.md), never as part of a build.
 *
 * Each profile is a list of classes. A class entry is {name, member, ...}:
 *   name      a schema class; a trailing '*' makes it concrete
 *   member    a property of the class ('r' is <cim>ACLineSegment.r), a prefixed property of an
 *             extension namespace ('nc:EnergyConsumer.participationFactor'), or for an
 *             enumeration '=A', a value the profile restricts it to
 */
public class BuildFixtures {

    static final Map<String, String> EXTENSIONS = Map.of(
        "nc", "http://entsoe.eu/ns/nc#",
        "eu", "http://iec.ch/TC57/CIM100-European#");

    static final String NAMESPACE = "http://example.com/cimprofiles-test/";

    // Connectivity: the whole hierarchy, both ends of three associations, PhaseCode restricted
    static final String[][] TEST_A = {
        {"IdentifiedObject", "mRID", "name", "description"},
        {"PowerSystemResource"},
        {"Equipment", "normallyInService", "EquipmentContainer"},
        {"ConductingEquipment", "Terminals", "BaseVoltage"},
        {"Conductor"},
        {"ACLineSegment*", "ACLineSegmentPhases"},
        {"ACLineSegmentPhase*", "phase", "sequenceNumber", "ACLineSegment"},
        {"ACDCTerminal", "connected", "sequenceNumber"},
        {"Terminal*", "phases", "ConductingEquipment", "ConnectivityNode"},
        {"ConnectivityNode*", "Terminals", "ConnectivityNodeContainer"},
        {"ConnectivityNodeContainer"},
        {"EquipmentContainer", "Equipments"},
        {"Feeder*"},
        {"BaseVoltage*", "nominalVoltage"},
        {"PhaseCode", "=A", "=B", "=C", "=ABC", "=N"},
        {"SinglePhaseKind"},
    };

    // Electrical: overlaps test_a with intermediate classes left out, so CIMTool flattens
    // Conductor, Terminal and EnergyConsumer onto IdentifiedObject; an NC extension
    static final String[][] TEST_B = {
        {"IdentifiedObject", "name"},
        {"Conductor", "length"},
        {"ACLineSegment*", "r", "x", "PerLengthImpedance"},
        {"PerLengthImpedance", "ACLineSegments"},
        {"PerLengthPhaseImpedance*"},
        {"PerLengthSequenceImpedance*", "r"},
        {"PowerTransformerEnd*", "ratedU"},
        {"Terminal*", "phases"},
        {"EnergyConsumer*", "pfixed", "pfixedPct", "phaseConnection",
            "nc:EnergyConsumer.participationFactor", "nc:EnergyConsumer.maxEconomicP"},
        {"PhaseCode", "=A", "=B", "=C", "=AB", "=ABC", "=s1", "=s2"},
        {"PhaseShuntConnectionKind"},
    };

    // Location and datatypes: the third part of a merge, a compound, Money, PU, DateTime,
    // KiloActivePower (a 'k' multiplier) and a European extension
    static final String[][] TEST_C = {
        {"IdentifiedObject", "name", "eu:IdentifiedObject.shortName"},
        {"PowerSystemResource", "Location"},
        {"ConductingEquipment", "Terminals"},
        {"ACLineSegment"},
        {"Terminal"},
        {"EnergyConsumer"},
        {"Location*", "mainAddress", "PositionPoints", "CoordinateSystem", "PowerSystemResources"},
        {"PositionPoint*", "sequenceNumber", "xPosition", "yPosition", "Location"},
        {"CoordinateSystem*", "crsUrn"},
        {"StreetAddress", "streetDetail"},
        {"StreetDetail", "name"},
        {"WireInfo*", "radius", "gmr"},
        {"GeneratingUnit*", "startupCost", "governorMPL"},
        {"BasicIntervalSchedule*", "startTime"},
        {"ShortCircuitTest*", "loss"},
    };

    static OntModel schema;
    static String cim;

    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            System.err.println("usage: BuildFixtures <CIMTool project dir> <schema .qea> <output dir>");
            System.exit(2);
        }
        File project = new File(args[0]);
        schema = new CLISchemaParser(new CLISettings(project), project).parse(new File(args[1]));
        cim = schema.getValidOntology().getURI() + "#";
        File output = new File(args[2]);
        write(profile("test_a", TEST_A), "test_a", new File(output, "test_a.owl"));
        write(profile("test_b", TEST_B), "test_b", new File(output, "test_b.owl"));
        write(profile("test_c", TEST_C), "test_c", new File(output, "test_c.owl"));
    }

    static OntModel profile(String name, String[][] classes) {
        OntModel profile = ModelFactory.createMem();
        OntResource header = profile.createResource(NAMESPACE + name);
        header.addRDFType(OWL.Ontology);
        header.addLabel(name, null);
        header.addProperty(OWL.imports, schema.getValidOntology());
        profile.setNsPrefix("", NAMESPACE + name + "#");
        profile.setNsPrefix("cim", cim);

        ProfileModel profileModel = new ProfileModel();
        profileModel.setOntModel(profile);
        profileModel.setBackgroundModel(schema);
        Refactory refactory = profileModel.getRefactory();

        // Every class first, so each property's range is a class of this profile
        Map<String, OntResource> made = new LinkedHashMap<>();
        for (String[] entry : classes) {
            String className = entry[0].replace("*", "");
            OntResource clss = refactory.createProfileClass(schemaResource(className), entry[0].endsWith("*"));
            if (!clss.getLocalName().equals(className))
                throw new IllegalStateException(name + ": " + className + " was created as " + clss.getLocalName());
            made.put(className, clss);
        }
        SelectionOptions options = new SelectionOptions(SelectionOption.UseSchemaCardinality);
        for (String[] entry : classes) {
            String className = entry[0].replace("*", "");
            ProfileClass profileClass = new ProfileClass(made.get(className), refactory.getNamespace());
            for (int i = 1; i < entry.length; i++) {
                if (entry[i].startsWith("=")) {
                    profileClass.addIndividual(schemaResource(className + "." + entry[i].substring(1)));
                    continue;
                }
                OntResource property = property(className, entry[i]);
                profileClass.createAllValuesFrom(property, options);
                if (property.isObjectProperty())
                    refactory.createDefaultRange(profileClass, property);
            }
        }
        linkHierarchy(made, refactory.getNamespace());
        return profile;
    }

    /**
     * Make each class a subclass of its nearest ancestor in the profile, as the editor leaves
     * it: ConductingEquipment(PowerSystemResource) when the profile has no Equipment. The API
     * links only direct parents, and only in the order classes are added.
     */
    static void linkHierarchy(Map<String, OntResource> made, String namespace) {
        for (Map.Entry<String, OntResource> entry : made.entrySet()) {
            OntResource clss = entry.getValue();
            List<OntResource> profileParents = new ArrayList<>();
            for (ResIterator it = clss.listSuperClasses(false); it.hasNext(); ) {
                OntResource parent = it.nextResource();
                if (parent.isURIResource() && parent.getURI().startsWith(namespace))
                    profileParents.add(parent);
            }
            for (OntResource parent : profileParents)
                clss.removeSuperClass(parent);
            String ancestor = nearestProfiledAncestor(entry.getKey(), made);
            if (ancestor != null)
                clss.addSuperClass(made.get(ancestor));
        }
    }

    static String nearestProfiledAncestor(String className, Map<String, OntResource> made) {
        OntResource base = schemaResource(className);
        while (true) {
            OntResource parent = null;
            for (ResIterator it = base.listSuperClasses(false); it.hasNext(); ) {
                OntResource candidate = it.nextResource();
                if (candidate.isURIResource() && candidate.getURI().startsWith(cim))
                    parent = candidate;   // the CIM parent, not a shadow extension class
            }
            if (parent == null)
                return null;
            if (made.containsKey(parent.getLocalName()))
                return parent.getLocalName();
            base = parent;
        }
    }

    static OntResource property(String className, String member) {
        int colon = member.indexOf(':');
        String uri = colon < 0 ? cim + className + "." + member
                               : EXTENSIONS.get(member.substring(0, colon)) + member.substring(colon + 1);
        OntResource property = schema.createResource(uri);
        if (!property.isProperty())
            throw new IllegalArgumentException("Not a schema property: " + uri);
        return property;
    }

    static OntResource schemaResource(String localName) {
        OntResource resource = schema.createResource(cim + localName);
        if (!resource.isClass() && !resource.hasRDFType(schema.createResource(cim + localName.split("\\.")[0])))
            throw new IllegalArgumentException("Not in the schema: " + cim + localName);
        return resource;
    }

    // As CIMTool's Task.write saves a profile
    static void write(OntModel profile, String name, File file) throws Exception {
        String namespace = NAMESPACE + name;
        Map<String, String> style = new HashMap<>();
        style.put("xmlbase", namespace);
        style.put("relativeURIs", "same-document");
        style.put("showXmlDeclaration", "true");
        try (OutputStream out = new FileOutputStream(file)) {
            IO.write(profile, out, namespace, Format.RDF_XML_WITH_NODEIDS.toFormat(), style);
        }
        System.out.println("wrote " + file);
    }
}
