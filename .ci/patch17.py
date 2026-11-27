import os, glob, re as _re

def rw(p, fn):
    s = open(p, encoding='utf-8').read()
    s2 = fn(s)
    if s2 == s:
        print("WARN no change:", p)
    open(p, 'w', encoding='utf-8').write(s2)

# 1) Diagnostics 缺 SwiftUI
def f1(s):
    if 'import SwiftUI' in s:
        return s
    return s.replace('import Foundation\nimport UIKit\n', 'import Foundation\nimport UIKit\nimport SwiftUI\n', 1)
rw('Sources/Support/Diagnostics.swift', f1)

# 2) Diagnostics 账号行少一个右括号
def f2(s):
    return s.replace('(s.isOffline ? "长期有效" : (s.isExpired ? "token 已过期" : "token 有效")))',
                     '(s.isOffline ? "长期有效" : (s.isExpired ? "token 已过期" : "token 有效"))))', 1)
rw('Sources/Support/Diagnostics.swift', f2)

# 3) VersionStorage 少右括号
def f3(s):
    return s.replace('setKey("renderDistance", String(max(2, min(32, renderDistance)))',
                     'setKey("renderDistance", String(max(2, min(32, renderDistance))))')
rw('Sources/Versions/VersionStorage.swift', f3)

# 4) AOTRuntime encode 是 throwing
def f4(s):
    return s.replace('if let data = JSONEncoder.pretty.encode(masked) {',
                     'if let data = try? JSONEncoder.pretty.encode(masked) {')
rw('Sources/Runtime/AOTRuntime.swift', f4)

# 5) HardwareInput：rightButton 可选 + GCKeyboard handler 签名冲突
def f5(s):
    s = s.replace('input?.rightButton.pressedChangedHandler', 'input?.rightButton?.pressedChangedHandler')
    old = '''    private func connectKeyboard() {
        if let kb = GCKeyboard.coalesced {
            kb.keyboardInput?.keyChangedHandler = { _, key, pressed in
                guard let key, let code = Self.gcKeyCode(key) else { return }
                InputBridge.shared.key(code, down: pressed)
            }
        }
        observers.append(NotificationCenter.default.addObserver(
            forName: .GCKeyboardDidConnect, object: nil, queue: .main) { note in
            guard let kb = note.object as? GCKeyboard else { return }
            kb.keyboardInput?.keyChangedHandler = { _, key, pressed in
                guard let key, let code = Self.gcKeyCode(key) else { return }
                InputBridge.shared.key(code, down: pressed)
            }
        })
    }'''
    new = '''    private func connectKeyboard() {
        // GCKeyboardInput.keyChangedHandler 在不同 SDK 里参数类型不一致，
        // 硬挂会编不过；键盘走 UIKit 的 pressesBegan/Ended 主路径。
        observers.append(NotificationCenter.default.addObserver(
            forName: .GCKeyboardDidConnect, object: nil, queue: .main) { _ in
            Log.shared.info("GCKeyboard connected (using UIKey path)")
        })
    }'''
    return s.replace(old, new)
rw('Sources/Input/HardwareInput.swift', f5)

# 6) MicrosoftAuth switch 缺分支
def f6(s):
    if 'missingClientID' in s:
        return s
    old = '''            case .cancelled: return "已取消登录"
            }'''
    new = '''            case .cancelled: return "已取消登录"
            case .missingClientID: return "没有配置微软应用 ID"
            case let .clientIDRejected(msg): return "应用 ID 被微软拒绝：\\(msg)"
            }'''
    return s.replace(old, new, 1)
rw('Sources/Auth/MicrosoftAuth.swift', f6)

# 7) Preflight read 多套了一层可选
def f7(s):
    if '!chunk.isEmpty' in s:
        return s
    old = 'guard let chunk = try? fh.read(upToCount: 1 << 20), let c = chunk, !c.isEmpty else { break }'
    new = 'guard let chunk = try? fh.read(upToCount: 1 << 20), !chunk.isEmpty else { break }'
    s = s.replace(old, new)
    return s.replace('            var buf = carry\n            buf.append(c)',
                     '            var buf = carry\n            buf.append(chunk)')
rw('Sources/Runtime/Preflight.swift', f7)

# 8) Views 三元里 secondary/red 类型不一致
def f8(s):
    return s.replace('.foregroundStyle(auth.hasClientID ? .secondary : .red)',
                     '.foregroundStyle(auth.hasClientID ? Color.secondary : Color.red)')
rw('Sources/Views/Views.swift', f8)

# 9) buildscript 块不能引用 project.ext 属性（Gradle 8）
GP = 'pipeline/version-build/build.gradle'
def _gr(s):
    for a in ['robovm-rt', 'robovm-objc', 'robovm-cocoatouch']:
        s = s.replace('implementation "com.mobidevelop.robovm:%s:${robovmVersion}"' % a,
                      'implementation "com.mobidevelop.robovm:%s:2.3.26"' % a)
    return s.replace('classpath "com.mobidevelop.robovm:robovm-gradle-plugin:${robovmVersion}"',
                     'classpath "com.mobidevelop.robovm:robovm-gradle-plugin:2.3.26"')
rw(GP, _gr)

# 10) 补项目级 repositories（Gradle 8 不继承 buildscript 的仓库）
def _grr(s):
    if s.count('repositories {') >= 2:
        return s
    old = "apply plugin: 'robovm'\n\ndependencies {"
    new = "apply plugin: 'robovm'\n\nrepositories {\n    mavenCentral()\n}\n\ndependencies {"
    if old in s:
        return s.replace(old, new, 1)
    idx = s.find('dependencies {')
    if idx < 0:
        return s
    return s[:idx] + "repositories {\n    mavenCentral()\n}\n\n" + s[idx:]
rw(GP, _grr)

# 11) Info.plist：v18 已自带正确版本，只在缺失时才补
IP = 'pipeline/version-build/Info.plist'
if not os.path.exists(IP):
    open(IP, 'w', encoding='utf-8').write('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key><string>GameRuntime</string>
    <key>CFBundleIdentifier</key><string>com.mobilite.gameruntime</string>
    <key>CFBundleName</key><string>GameRuntime</string>
    <key>CFBundlePackageType</key><string>FMWK</string>
    <key>MinimumOSVersion</key><string>16.0</string>
</dict>
</plist>
''')
    print("wrote", IP)
else:
    print("keep existing", IP)

# 12) robovm.xml 不动（v18 已含 <infoPList>）；只检查关键元素存在
x = open('pipeline/version-build/robovm.xml', encoding='utf-8').read()
print('robovm.xml infoPList:', '<infoPList>' in x, '| headers:', '<headers>' in x)

# 13) shell 里 "$VAR，" 把全角标点吸进变量名
for sp in glob.glob('pipeline/**/*.sh', recursive=True):
    src = open(sp, encoding='utf-8').read()
    fixed = _re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)(?=[^\x00-\x7f])', r'${1}', src)
    if fixed != src:
        open(sp, 'w', encoding='utf-8').write(fixed)
        print("sh-cjk fix:", sp)

print("patch done (v18)")
