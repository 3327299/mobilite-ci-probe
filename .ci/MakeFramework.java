import org.robovm.compiler.AppCompiler;
import org.robovm.compiler.config.Config;
import java.io.File;
import java.io.FilenameFilter;

public class MakeFramework {
    public static void main(String[] args) throws Exception {
        String xml = args[0];
        String aotDir = args[1];
        String rt = args[2], objc = args[3], cocoa = args[4];
        String work = args[5];

        Config.Builder b = new Config.Builder();
        b.read(new File(xml));

        File home = new File(work, "rvmhome");
        File bin = new File(home, "bin"); bin.mkdirs();
        File libvm = new File(home, "lib/vm"); libvm.mkdirs();
        b.home(new Config.Home(home, bin, libvm, new File(rt)));

        File[] jars = new File(aotDir).listFiles(new FilenameFilter() {
            public boolean accept(File d, String n) { return n.endsWith(".jar"); }
        });
        int n = 0;
        if (jars != null) {
            for (File j : jars) { b.addClasspathEntry(j); n++; }
        }
        System.out.println("aot jars: " + n);

        b.addClasspathEntry(new File(rt));
        b.addClasspathEntry(new File(objc));
        b.addClasspathEntry(new File(cocoa));
        b.installDir(new File(work, "build/install"));

        Config c = b.build();
        System.out.println("target=" + c.getTarget());
        System.out.println("mainClass=" + c.getMainClass());
        System.out.println("executable=" + c.getExecutableName());

        AppCompiler compiler = new AppCompiler(c);
        compiler.compile();
        System.out.println("MAKE_FRAMEWORK_OK");
    }
}
