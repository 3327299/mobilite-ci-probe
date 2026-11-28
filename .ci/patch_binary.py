#!/usr/bin/env python3
import os, sys

# ---- 1) BinaryImport: iOS 没有 SecStaticCode，必须用 #if 隔开；锚点放在 sizeText 之后 ----
P = 'Sources/Runtime/BinaryImport.swift'
s = open(P, encoding='utf-8').read()
if '#if os(iOS)' in s:
    print('BinaryImport already guarded')
else:
    anchor = '        let sizeText = ByteCountFormatter.string(fromByteCount: size, countStyle: .file)\n'
    i = s.find(anchor)
    if i < 0:
        print('!! sizeText anchor not found')
    else:
        pos = i + len(anchor)
        ios = ('#if os(iOS)\n'
               '        // iOS SDK 没有 SecStaticCode / SecCodeCopySigningInformation（macOS 专有）\n'
               '        return ImportAudit(verdict: .unsigned, teamID: nil, appTeamID: nil,\n'
               '                           arch: ArchCheck.arch(of: url), sizeText: sizeText,\n'
               '                           detail: "iOS 不支持 SecStaticCode 验签，加载时由系统判定")\n'
               '#else\n')
        s = s[:pos] + ios + s[pos:]
        end = s.find('\n    }\n', pos + len(ios))
        if end > pos:
            s = s[:end] + '\n#endif' + s[end:]
        a2 = '    static func appTeamID() -> String? {\n'
        i2 = s.find(a2)
        if i2 >= 0 and 'if os(iOS)\n        return nil' not in s:
            b2 = i2 + len(a2)
            e2 = s.find('\n    }\n', b2)
            if e2 > b2:
                s = s[:b2] + '#if os(iOS)\n        return nil\n#else\n' + s[b2:e2] + '#endif' + s[e2:]
        open(P, 'w', encoding='utf-8').write(s)
        print('patched BinaryImport (iOS guard after sizeText)')

# ---- 2) make-framework-bundle.sh: macOS 没有 find -printf，set -e 下会直接拖垮脚本 ----
P2 = 'pipeline/scripts/make-framework-bundle.sh'
t = open(P2, encoding='utf-8').read()
bad = """find "$XC" -type f -printf '  %P  (%s bytes)\\n' | sort"""
good = '''python3 - "$XC" <<'PYEOF'
import os, sys
root = sys.argv[1]
for dp, _, fs in os.walk(root):
    for f in sorted(fs):
        p = os.path.join(dp, f)
        print("  %s (%d bytes)" % (os.path.relpath(p, root), os.path.getsize(p)))
PYEOF'''
if bad in t:
    t = t.replace(bad, good)
    open(P2, 'w', encoding='utf-8').write(t)
    print('fixed bundle -printf')
else:
    print('bundle -printf pattern not found')

# ---- 3) MicrosoftAuth: switch 必须穷尽 enum ----
P3 = 'Sources/Auth/MicrosoftAuth.swift'
s3 = open(P3, encoding='utf-8').read()
if 'case .missingClientID: return' in s3:
    print('MicrosoftAuth already fixed')
else:
    old = '            case .cancelled: return "已取消登录"\n            }'
    new = ('            case .cancelled: return "已取消登录"\n'
           '            case .missingClientID: return "没有配置微软应用 ID"\n'
           '            case let .clientIDRejected(msg): return "应用 ID 被微软拒绝：" + msg\n'
           '            }')
    if old in s3:
        open(P3, 'w', encoding='utf-8').write(s3.replace(old, new, 1))
        print('fixed MicrosoftAuth switch')
    else:
        print('!! MicrosoftAuth pattern missing')

# ---- 4) 括号规范化：把多余的右括号压回正确数量 ----
P4 = 'Sources/Support/Diagnostics.swift'
s4 = open(P4, encoding='utf-8').read()
for bad_p, good_p in (('token 有效")))))', 'token 有效"))))'),
                      ('token 有效"))))))', 'token 有效"))))')):
    while bad_p in s4:
        s4 = s4.replace(bad_p, good_p)
open(P4, 'w', encoding='utf-8').write(s4)
print('Diagnostics parens:', 'token 有效"))))' in s4)

P5 = 'Sources/Versions/VersionStorage.swift'
s5 = open(P5, encoding='utf-8').read()
for bad_p, good_p in (('renderDistance)))))', 'renderDistance))))'),
                      ('renderDistance))))))', 'renderDistance))))')):
    while bad_p in s5:
        s5 = s5.replace(bad_p, good_p)
open(P5, 'w', encoding='utf-8').write(s5)
print('VersionStorage parens:', 'renderDistance))))' in s5)
print('extra patch done')
