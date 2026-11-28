#!/usr/bin/env python3
# 两处 v24 工程缺陷的自动修补（幂等）：
# 1) build.gradle 只有 buildscript.repositories，project 级 dependencies 没有 repositories
#    → "Cannot resolve external dependency ... because no repositories are defined"
# 2) gradle 默认 heap 512Mi，robovmInstall 直接 GC thrashing 把 daemon 干停
#    → 写 gradle.properties 放大堆；同时 3c 回退分支硬编码 2.3.26 改成跟随 ROBOVM_VERSION
import os, re, sys

VB = 'pipeline/version-build'
GRADLE = os.path.join(VB, 'build.gradle')
BVS = 'pipeline/scripts/build-version.sh'

BLOCK = """

repositories {
    mavenCentral()
    maven { url 'https://oss.sonatype.org/content/repositories/snapshots' }
}
"""

s = open(GRADLE, encoding='utf-8').read()
outside = re.sub(r'buildscript\s*\{.*?\n\}', '', s, flags=re.S)
if re.search(r'\nrepositories\s*\{', outside):
    print('gradle patch: repositories already present')
else:
    if "apply plugin: 'robovm'" in s:
        s = s.replace("apply plugin: 'robovm'", "apply plugin: 'robovm'" + BLOCK, 1)
    else:
        s = s.replace('dependencies {', BLOCK.strip() + '\n\ndependencies {', 1)
    open(GRADLE, 'w', encoding='utf-8').write(s)
    print('gradle patch: project-level repositories inserted')

# gradle.properties：robovmInstall 链接 8956 类要几个 G
props = os.path.join(VB, 'gradle.properties')
if not os.path.exists(props):
    open(props, 'w', encoding='utf-8').write(
        'org.gradle.jvmargs=-Xmx6g -XX:MaxMetaspaceSize=2g -XX:+UseParallelGC\n'
        'org.gradle.parallel=false\n'
        'org.gradle.daemon=true\n')
    print('gradle.properties: created (-Xmx6g)')
else:
    print('gradle.properties: exists')

# build-version.sh 的 3c 回退硬编码 robovm-gradle-plugin-2.3.26.jar
b = open(BVS, encoding='utf-8').read()
if 'robovm-gradle-plugin-2.3.26' in b:
    b = b.replace('robovm-gradle-plugin-2.3.26.jar', 'robovm-gradle-plugin-${ROBOVM_VERSION:-3.0.1}.jar')
    b = b.replace('robovm-gradle-plugin-2.3.26', 'robovm-gradle-plugin-${ROBOVM_VERSION:-3.0.1}')
    open(BVS, 'w', encoding='utf-8').write(b)
    print('build-version.sh: plugin jar version now follows ROBOVM_VERSION')
else:
    print('build-version.sh: plugin jar version ok')
