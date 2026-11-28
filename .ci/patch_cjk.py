#!/usr/bin/env python3
# 修 shell 脚本里 "$VAR，" 这类全角标点被吸进变量名的写法（unbound variable 的直接原因）
import glob, re, sys

files = sorted(glob.glob('pipeline/**/*.sh', recursive=True)) + sorted(glob.glob('.ci/*.sh'))
n = 0
for sp in files:
    s = open(sp, encoding='utf-8').read()
    f = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)(?=[^\x00-\x7f])',
               lambda m: '${' + m.group(1) + '}', s)
    if f != s:
        open(sp, 'w', encoding='utf-8').write(f)
        n += 1
        print('cjk-var fixed:', sp)
print('total fixed files:', n)
