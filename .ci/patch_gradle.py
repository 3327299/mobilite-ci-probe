#!/usr/bin/env python3
# v24 的 build.gradle 只有 buildscript.repositories，project 级 dependencies 没有
# repositories → "Cannot resolve external dependency ... because no repositories are defined"
# 这里在 apply plugin: 'robovm' 后补上 project 级 repositories（幂等）。
import re, sys

p = 'pipeline/version-build/build.gradle'
s = open(p, encoding='utf-8').read()

BLOCK = """

repositories {
    mavenCentral()
    maven { url 'https://oss.sonatype.org/content/repositories/snapshots' }
}
"""

# 只看 buildscript 块之外是否已有 repositories
outside = re.sub(r'buildscript\s*\{.*?\n\}', '', s, flags=re.S)
if re.search(r'\nrepositories\s*\{', outside):
    print('gradle patch: repositories already present')
    sys.exit(0)

if 'apply plugin: \'robovm\'' in s:
    s = s.replace("apply plugin: 'robovm'", "apply plugin: 'robovm'" + BLOCK, 1)
else:
    s = s.replace('dependencies {', BLOCK.strip() + '\n\ndependencies {', 1)

open(p, 'w', encoding='utf-8').write(s)
print('gradle patch: project-level repositories inserted')
