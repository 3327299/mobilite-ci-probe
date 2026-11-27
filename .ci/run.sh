#!/usr/bin/env bash
# MobiLite v17 内置构建（macOS runner）
set -eo pipefail
cd "${GITHUB_WORKSPACE:-$PWD}"

exec 3>&1 4>&2
: > /tmp/build.log
exec > >(tee -a /tmp/build.log) 2>&1

on_exit() {
  rc=$?
  if [ "$rc" != "0" ]; then
    sleep 2
    grep -nE "What went wrong|FAILURE|Caused by|Execution failed|error:|Unsupported|NoClassDef|Could not|Failed to read|No such file" /tmp/build.log 2>/dev/null | tail -20 > /tmp/ctx.log || true
    while IFS= read -r l; do echo "::error::$l"; done < /tmp/ctx.log >&3
    U=$(curl -sS --max-time 300 -X POST -H "filename: log-$AOT_SCOPE.txt" --data-binary @/tmp/build.log "https://filebin.net/$BIN/log-$AOT_SCOPE.txt" 2>/dev/null || true)
    echo "::error::log: $U" >&3
  fi
  exit $rc
}
trap on_exit EXIT

echo "== 环境 =="
uname -m; sw_vers; xcodebuild -version | head -2

echo "== 0) 源码 =="
OK=0
echo "-- try $SRC_ZIP"
if curl -fsSL --retry 5 --retry-all-errors --retry-delay 3 --max-time 600 -o /tmp/src.zip "$SRC_ZIP"; then OK=1; fi
if [ "$OK" != "1" ]; then
  echo "-- fallback CDN with resume"
  for i in $(seq 1 15); do
    curl -fsSL --retry 3 --retry-all-errors -C - --max-time 300 -o /tmp/src.zip "$SRC_ZIP_ALT" && { OK=1; break; }
    sleep 2
  done
fi
[ "$OK" = "1" ] || { echo "::error::源码下载全失败"; exit 1; }
unzip -t /tmp/src.zip >/dev/null || { echo "::error::zip 损坏"; exit 1; }
rm -rf /tmp/src && unzip -q /tmp/src.zip -d /tmp/src
SRC=$(find /tmp/src -maxdepth 3 -type d -name Sources | head -1)
ROOT=$(dirname "$SRC")
echo "src root: $ROOT"
cp -R "$ROOT/." .
echo "swift files: $(find Sources -name '*.swift' | wc -l)"

echo "== 1) 打补丁 =="
python3 .ci/patch17.py

echo "== 2) JDK 21 =="
curl -fsSL --retry 5 --retry-all-errors --max-time 600 -o /tmp/jdk21.tgz \
  "https://api.adoptium.net/v3/binary/latest/21/ga/mac/aarch64/jdk/hotspot/normal/eclipse"
mkdir -p /tmp/jdk21 && tar xzf /tmp/jdk21.tgz -C /tmp/jdk21
J21=$(find /tmp/jdk21 -maxdepth 4 -type d -name Home | head -1)
[ -x "$J21/bin/java" ] || { echo "::error::JDK21 解压异常"; exit 1; }
export JAVA_HOME="$J21"
export PATH="$JAVA_HOME/bin:$PATH"
echo "JAVA_HOME_21=$J21" >> "$GITHUB_ENV"
java -version 2>&1 | head -2

echo "== 3) Gradle 8.8 + MobiVM 运行时 + JvmDowngrader =="
curl -fsSL --retry 5 --retry-all-errors --max-time 600 -o /tmp/gradle.zip \
  "https://services.gradle.org/distributions/gradle-8.8-bin.zip"
unzip -q /tmp/gradle.zip -d /tmp
chmod +x /tmp/gradle-8.8/bin/gradle
export GRADLE_HOME="/tmp/gradle-8.8"
echo "GRADLE_HOME=$GRADLE_HOME" >> "$GITHUB_ENV"
"$GRADLE_HOME/bin/gradle" --version | head -5
mkdir -p "$HOME/.tools"
for a in robovm-rt robovm-objc robovm-cocoatouch; do
  curl -fsSL --retry 5 --retry-all-errors -o "$HOME/.tools/$a.jar" \
    "https://repo1.maven.org/maven2/com/mobidevelop/robovm/$a/2.3.26/$a-2.3.26.jar"
done
curl -fsSL --retry 5 --retry-all-errors -o "$HOME/.tools/jvmdowngrader-all.jar" \
  "https://repo1.maven.org/maven2/xyz/wagyourtail/jvmdowngrader/jvmdowngrader/2.0.1/jvmdowngrader-2.0.1-all.jar"
ls -l "$HOME/.tools"

echo "== 4) 拉官方 ${MC_VER} + API 桩包 =="
python3 pipeline/scripts/fetch-vanilla.py "$MC_VER" "/tmp/mc$MC_VER"
ls -l "/tmp/mc$MC_VER/client.jar"
./pipeline/api-jar/build.sh
ls -l pipeline/out/ || true

echo "== 5) 全量降级到 ${CLASS_VER} =="
export JVD_JAR="$HOME/.tools/jvmdowngrader-all.jar"
mkdir -p "Frameworks/Versions/$MC_VER"
cp "/tmp/mc$MC_VER/$MC_VER.json" "Frameworks/Versions/$MC_VER/version.json"
API_JAR="$PWD/pipeline/out/api-java21-down52.jar" \
  ./pipeline/scripts/downgrade-all.sh "/tmp/mc$MC_VER/client.jar" "/tmp/mc$MC_VER/libs" "pipeline/build/$MC_VER/dg" "$CLASS_VER"
ls -l "pipeline/build/$MC_VER/dg/client-shaded.jar"

echo "== 6) 组装 AOT 输入 =="
TOP6="$PWD"
cp "$TOP6/pipeline/build/$MC_VER/dg/client-shaded.jar" "$TOP6/pipeline/build/$MC_VER/mc-downgraded.jar"
ROBOVM_RT="$HOME/.tools/robovm-rt.jar" \
ROBOVM_OBJC="$HOME/.tools/robovm-objc.jar" \
ROBOVM_COCOA="$HOME/.tools/robovm-cocoatouch.jar" \
  "$TOP6/pipeline/scripts/assemble-aot-input.sh" \
    "$TOP6/pipeline/build/$MC_VER/mc-downgraded.jar" \
    "$TOP6/pipeline/build/$MC_VER/dg/libs" \
    "$TOP6/pipeline/build/$MC_VER/aot-input"
ls -l "$TOP6/pipeline/build/$MC_VER/aot-input/"

echo "== 7) MobiVM AOT（scope=${AOT_SCOPE}）=="
TOP="$PWD"
VB="$TOP/pipeline/version-build"
CONFIG="$VB/robovm.xml"
if [ "$AOT_SCOPE" = "narrow" ]; then
  CONFIG="$VB/robovm.narrow.xml"
  ./pipeline/scripts/make-narrow-config.sh "$VB/robovm.xml" "$CONFIG"
fi
cat "$CONFIG"
cd "$VB"
"$GRADLE_HOME/bin/gradle" tasks --all > /tmp/tasks.txt 2>&1 || tail -40 /tmp/tasks.txt
grep -iE 'xcframework|createIPA|createFramework|robovm' /tmp/tasks.txt | head -40 || true
PICK=""
for t in robovmXcframework createXcframework createFramework createIPA; do
  if grep -q "$t" /tmp/tasks.txt; then PICK=$t; break; fi
done
[ -z "$PICK" ] && PICK=createIPA
echo "== task: $PICK =="
"$GRADLE_HOME/bin/gradle" "$PICK" --stacktrace \
  -PversionID="$MC_VER" \
  -PaotInput="$TOP/pipeline/build/$MC_VER/aot-input" \
  -PoutDir="$TOP/Frameworks/Versions/$MC_VER" \
  -ProbovmConfig="$CONFIG" 2>&1 | tee /tmp/gradle.log
cd "$TOP"

echo "== 8) 收产物 + 刷新 versions.json =="
OUT="Frameworks/Versions/$MC_VER"
ls -laR "$OUT" | head -100
FOUND=$(find pipeline/version-build/build -maxdepth 10 \( -name 'GameRuntime.xcframework' -o -name 'GameRuntime.framework' -o -name 'GameRuntime.dylib' \) 2>/dev/null | head -1)
if [ -z "$FOUND" ]; then
  echo "::error::AOT 没出 GameRuntime 产物"
  find pipeline/version-build/build -maxdepth 5 | head -80
  exit 4
fi
echo "found: $FOUND"
rm -rf "$OUT/GameRuntime.xcframework" "$OUT/GameRuntime.framework" "$OUT/GameRuntime.dylib"
cp -R "$FOUND" "$OUT/"
python3 pipeline/scripts/make-registry.py Frameworks/Versions
cat Frameworks/Versions/versions.json
grep -q '"id": "1.21.4"' Frameworks/Versions/versions.json || { echo "::error::versions.json 里没有 $MC_VER"; exit 6; }

echo "== 9) XcodeGen + xcodebuild + IPA =="
curl -fsSL --retry 5 --retry-all-errors --max-time 300 -o /tmp/xcodegen.zip \
  "https://github.com/yonaskolb/XcodeGen/releases/latest/download/xcodegen.zip"
rm -rf /tmp/xcodegen && unzip -q /tmp/xcodegen.zip -d /tmp/xcodegen
XG=$(find /tmp/xcodegen -maxdepth 4 -type f -name 'xcodegen' | head -1)
chmod +x "$XG"
export PATH="$(dirname "$XG"):$PATH"
xcodegen --version
xcodegen generate
xcodebuild -project MobiLite.xcodeproj -scheme MobiLite \
  -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath build \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \
  | tee /tmp/xcode.log | tail -60
APP="build/Build/Products/Release-iphoneos/MobiLite.app"
test -f "$APP/MobiLite" || { echo "::error::没有主程序"; exit 5; }
rm -rf Payload && mkdir -p Payload
cp -R "$APP" Payload/
zip -qry "MobiLite-$MC_VER-$AOT_SCOPE-unsigned.ipa" Payload
ls -l *.ipa

echo "== 10) 清单 + 上传 =="
IPA="MobiLite-$MC_VER-$AOT_SCOPE-unsigned.ipa"
{
  echo "scope=$AOT_SCOPE"
  echo "ipa=$IPA"
  echo "ipa_bytes=$(stat -f%z "$IPA")"
  echo "ipa_sha256=$(shasum -a 256 "$IPA" | cut -d' ' -f1)"
  echo "== 主程序"
  ls -l Payload/MobiLite.app/MobiLite
  file Payload/MobiLite.app/MobiLite
  echo "== Frameworks/Versions"
  ls -laR Payload/MobiLite.app/Frameworks/Versions | head -100
  echo "== versions.json"
  cat Payload/MobiLite.app/Frameworks/Versions/versions.json 2>/dev/null || echo "(缺)"
  echo "== plist"
  /usr/libexec/PlistBuddy -c "Print :MinimumOSVersion" Payload/MobiLite.app/Info.plist 2>/dev/null
  /usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" Payload/MobiLite.app/Info.plist 2>/dev/null
  /usr/libexec/PlistBuddy -c "Print :UIFileSharingEnabled" Payload/MobiLite.app/Info.plist 2>/dev/null
  echo "== app 大小"
  du -sh Payload/MobiLite.app
} > manifest.txt 2>&1
cat manifest.txt
for f in "$IPA" manifest.txt /tmp/gradle.log /tmp/xcode.log; do
  [ -f "$f" ] || continue
  b=$(basename "$f")
  echo "-- upload $b"
  curl -sS --max-time 900 -X POST -H "filename: $b" --data-binary @"$f" "https://filebin.net/$BIN/$b" -o "/tmp/up_$b.json" || true
  grep -o '"filename": *"[^"]*"' "/tmp/up_$b.json" 2>/dev/null || head -c 150 "/tmp/up_$b.json" 2>/dev/null || true
  echo
done
echo "IPA: https://filebin.net/$BIN/$IPA"

echo "== DONE =="
