#!/usr/bin/env python3
# BinaryImport.swift 的 SecStaticCode 是 macOS 专有 API，iOS SDK 里根本没有。
# 把 audit() / appTeamID() 在 iOS 上换成不依赖 Sec* 的简化实现。
P = 'Sources/Runtime/BinaryImport.swift'
s = open(P, encoding='utf-8').read()
if '#if os(iOS)' in s:
    print('BinaryImport already patched')
else:
    start = '    static func audit(_ url: URL) -> ImportAudit {\n'
    i = s.find(start)
    assert i >= 0, 'audit() not found'
    b = i + len(start)
    e = s.find('\n    }\n', b)
    assert e > b, 'audit() end not found'
    ios = ('#if os(iOS)\n'
           '        // iOS SDK 没有 SecStaticCode / SecCodeCopySigningInformation（macOS 专有）\n'
           '        return ImportAudit(verdict: .unsigned, teamID: nil, appTeamID: nil,\n'
           '                           arch: ArchCheck.arch(of: url), sizeText: sizeText,\n'
           '                           detail: "iOS 不支持 SecStaticCode 验签，加载时由系统判定")\n'
           '#else\n')
    s = s[:b] + ios + s[b:e] + '#endif' + s[e:]
    start2 = '    static func appTeamID() -> String? {\n'
    i2 = s.find(start2)
    if i2 >= 0:
        b2 = i2 + len(start2)
        e2 = s.find('\n    }\n', b2)
        if e2 > b2:
            s = s[:b2] + '#if os(iOS)\n        return nil\n#else\n' + s[b2:e2] + '#endif' + s[e2:]
    open(P, 'w', encoding='utf-8').write(s)
    print('patched BinaryImport (iOS guard)')
