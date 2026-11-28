import java.io.*;
import java.util.*;
import java.util.zip.*;
import org.objectweb.asm.*;

/**
 * 删掉 class 里的 LocalVariableTable / LocalVariableTypeTable。
 *
 * 原因：jvmdowngrader 降级后某些类（如 net.minecraft.client.main.Main$2）的局部变量表
 * 索引重复、名字不一致（$$75 / $$39 指同一个 slot 35），RoboVM 的 Soot 前端在
 * LocalVariables 校验时直接 IllegalStateException，full 口径必挂。
 * 这些表只服务调试器，AOT 不需要。
 */
public final class StripDebug {
    public static void main(String[] args) throws Exception {
        File in = new File(args[0]);
        File out = new File(args[1]);
        int classes = 0;
        try (ZipFile zf = new ZipFile(in);
             ZipOutputStream zo = new ZipOutputStream(new FileOutputStream(out))) {
            Enumeration<? extends ZipEntry> en = zf.entries();
            while (en.hasMoreElements()) {
                ZipEntry e = en.nextElement();
                byte[] b;
                try (InputStream is = zf.getInputStream(e)) {
                    b = is.readAllBytes();
                }
                if (e.getName().endsWith(".class")) {
                    ClassReader cr = new ClassReader(b);
                    ClassWriter cw = new ClassWriter(cr, 0);
                    ClassVisitor cv = new ClassVisitor(Opcodes.ASM9, cw) {
                        @Override
                        public void visitLocalVariable(String name, String desc, String sig,
                                                       Label start, Label end, int index) {
                            // drop
                        }
                    };
                    cr.accept(cv, 0);
                    b = cw.toByteArray();
                    classes++;
                }
                zo.putNextEntry(new ZipEntry(e.getName()));
                zo.write(b);
                zo.closeEntry();
            }
        }
        System.out.println("[strip] classes processed: " + classes);
        System.out.println("[strip] out: " + out + " (" + out.length() / 1024 / 1024 + " MB)");
    }
}
