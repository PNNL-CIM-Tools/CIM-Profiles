import java.io.File;

import au.com.langdale.kena.OntModel;
import au.com.langdale.profiles.cl.CLIBuilderPreferences;
import au.com.langdale.profiles.cl.CLIProfileTransformer;
import au.com.langdale.profiles.cl.CLISchemaParser;
import au.com.langdale.profiles.cl.CLISettings;
import au.com.langdale.profiles.cl.builders.BuilderRegistry;

/**
 * Runs the cimantic-graphs builders on profiles, as CIMTool does on save.
 *
 * The CIMTool CLI runs a custom XSLT (--xslt) without its TEXT post-processing, so the Python
 * builders would come out as indent markup. This registers the builders from a directory
 * (builders.json and <builder>.xsl, see generate.sh) and runs them by name instead.
 */
public class GenerateOutputs {

    static final String[] BUILDERS = {"cimantic-graphs", "cimantic-graphs-init", "cimantic-graphs-jsonld-context"};

    public static void main(String[] args) throws Exception {
        if (args.length < 5) {
            System.err.println("usage: GenerateOutputs <CIMTool project dir> <schema .qea> <builders dir> <output dir> <profile.owl>...");
            System.exit(2);
        }
        File project = new File(args[0]);
        OntModel schema = new CLISchemaParser(new CLISettings(project), project).parse(new File(args[1]));
        BuilderRegistry registry = new BuilderRegistry(new File(args[2]));
        CLIBuilderPreferences preferences = new CLIBuilderPreferences(project);
        File output = new File(args[3]);
        for (int i = 4; i < args.length; i++) {
            for (String builder : BUILDERS) {
                CLIProfileTransformer transformer = new CLIProfileTransformer(preferences, registry);
                transformer.setProfile(new File(args[i]));
                transformer.addSchema(schema);
                transformer.setBuilder(builder);
                transformer.setOutputDirectory(output);
                transformer.transform();
                System.out.println("wrote " + transformer.getOutputFile());
            }
        }
    }
}
