import org.robovm.compiler.AppCompiler;
import org.robovm.compiler.config.Arch;
import org.robovm.compiler.config.Config;
import org.robovm.compiler.config.OS;
import java.io.File;

public class MakeFramework {
    public static void main(String[] args) throws Exception {
        String aot = args[0], rt = args[1], objc = args[2], cocoa = args[3];
        String plist = args[4], work = args[5], name = args[6];

        File home = new File(work, "rvmhome");
        File bin = new File(home, "bin"); bin.mkdirs();
        File libvm = new File(home, "lib/vm"); libvm.mkdirs();
        Config.Home h = new Config.Home(home, bin, libvm, new File(rt));

        Config.Builder b = new Config.Builder();
        b.home(h);
        b.executableName(name);
        b.mainClass("com.mobilite.game.MobiLiteGame");
        b.targetType("xcframework");
        b.os(OS.ios);
        b.arch(Arch.arm64);
        b.addClasspathEntry(new File(aot));
        b.addClasspathEntry(new File(rt));
        b.addClasspathEntry(new File(objc));
        b.addClasspathEntry(new File(cocoa));
        b.infoPList(new File(plist));
        b.iosInfoPList(new File(plist));
        b.installDir(new File(work, "build/install"));

        for (String p : new String[]{"com.mobilite.game.**", "net.minecraft.**", "com.mojang.**"}) {
            b.addForceLinkClass(p);
        }
        for (String f : new String[]{"Foundation", "UIKit", "OpenGLES", "QuartzCore", "CoreGraphics", "GameController"}) {
            b.addFramework(f);
        }

        Config c = b.build();
        AppCompiler compiler = new AppCompiler(c);
        compiler.compile();
        compiler.install();
        System.out.println("MAKE_FRAMEWORK_OK");
    }
}
