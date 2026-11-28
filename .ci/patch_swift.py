#!/usr/bin/env python3
# v24 遗留的 1 处 Swift 语病：Preflight.swift:158
#   guard let chunk = try? fh.read(upToCount:), let c = chunk, !c.isEmpty
# read(upToCount:) 返回 Data?，try? 后是 Data?，所以 chunk 已解包为 Data，
# 再写 let c = chunk 就是 "conditional binding must have Optional type, not 'Data'"。
import sys

P = 'Sources/Runtime/Preflight.swift'
s = open(P, encoding='utf-8').read()
orig = s

s = s.replace(', let c = chunk, !c.isEmpty', ', !chunk.isEmpty')
s = s.replace('buf.append(c)', 'buf.append(chunk)')

if s == orig:
    print('swift patch: no change needed')
else:
    open(P, 'w', encoding='utf-8').write(s)
    print('swift patch: Preflight.swift guard fixed')
