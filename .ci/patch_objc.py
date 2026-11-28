#!/usr/bin/env python3
# v29 冒烟暴露的 ObjC 错误（共 11 条，集中在 2 个文件）：
#  GLFWIos.m:259/260  gLayer 声明为 id → property 'frame'/'contentsScale' not found
#  GLFWIos.m:298      @implementation 里又写了一行分号声明 → expected method body
#                     （连带 310 的 w/h undeclared、323 missing '@end' 都是它引起的 cascade）
#  MobiEGL.m:281      缺 <dlfcn.h> → dlsym / RTLD_DEFAULT 未声明
import re, sys

A = 'bridge/glfw-ios/GLFWIos.m'
B = 'bridge/glfw-ios/MobiEGL.m'

s = open(A, encoding='utf-8').read()
n = 0

if 'static id gLayer;' in s:
    s = s.replace('static id gLayer;', 'static CAEAGLLayer *gLayer;')
    n += 1

# 删掉主 @implementation 里那行重复的分号声明
s2 = re.sub(r'\n\+ \(void\)pushEventType:\(int32_t\)t a:\(int32_t\)a b:\(int32_t\)b x:\(double\)x y:\(double\)y;[ \t]*\n',
            '\n', s)
if s2 != s:
    s = s2
    n += 1

open(A, 'w', encoding='utf-8').write(s)

b = open(B, encoding='utf-8').read()
if '<dlfcn.h>' not in b:
    b = b.replace('#include <string.h>', '#include <string.h>\n#include <dlfcn.h>', 1)
    open(B, 'w', encoding='utf-8').write(b)
    n += 1

print('objc patches applied:', n)

# v29.1：版本号改为 29.1（影响 Info.plist 的 CFBundleShortVersionString / IPA 命名）
try:
    p = 'project.yml'
    s = open(p, encoding='utf-8').read()
    s2 = s.replace('MARKETING_VERSION: "1.0.0"', 'MARKETING_VERSION: "29.1"')
    if s2 != s:
        open(p, 'w', encoding='utf-8').write(s2)
        print('version -> 29.1')
except FileNotFoundError:
    pass
