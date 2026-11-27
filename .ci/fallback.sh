#!/usr/bin/env bash
# fallback：gradle createIPA 不支持 xcframework（Archiving is not supported）
# 直调 AppCompiler.compile()，配置读 robovm.narrow.xml
set -eo pipefail
cd "${GITHUB_WORKSPACE:-$PWD}"
exec > >(tee -a /tmp/fallback.log) 2>&1

VB="$PWD/pipeline/version-build"
echo "== F1) narrow config =="
./pipeline/scripts/make-narrow-config.sh "$VB/robovm.xml" "$VB/robovm.narrow.xml"
grep -E "infoPList|target|arch|pattern" "$VB/robovm.narrow.xml" || true

echo "== F2) compiler jar + javac =="
mkdir -p "$HOME/.tools" /tmp/mkf/classes
curl -fsSL --retry 3 -o "$HOME/.tools/rgp.jar" "https://repo1.maven.org/maven2/com/mobidevelop/robovm/robovm-gradle-plugin/2.3.26/robovm-gradle-plugin-2.3.26.jar"
javac -nowarn -cp "$HOME/.tools/rgp.jar" -d /tmp/mkf/classes .ci/MakeFramework.java

echo "== F3) compile =="
export DEVELOPER_DIR="$(xcode-select -p)"
java -cp "/tmp/mkf/classes:$HOME/.tools/rgp.jar" MakeFramework \
  "$VB/robovm.narrow.xml" "$PWD/pipeline/build/$MC_VER/aot-input" \
  "$HOME/.tools/robovm-rt.jar" "$HOME/.tools/robovm-objc.jar" "$HOME/.tools/robovm-cocoatouch.jar" \
  "$VB"

echo "== F4) collect =="
FOUND=$(find "$VB/build" \( -name 'GameRuntime.framework' -o -name 'GameRuntime.xcframework' -o -name 'GameRuntime.dylib' \) 2>/dev/null | head -1)
if [ -z "$FOUND" ]; then
  echo "::error::no GameRuntime artifact after compile"
  find "$VB/build" -maxdepth 4 | head -40
  exit 4
fi
echo "found=$FOUND"
OUT="Frameworks/Versions/$MC_VER"
mkdir -p "$OUT"
rm -rf "$OUT/GameRuntime.framework" "$OUT/GameRuntime.xcframework" "$OUT/GameRuntime.dylib"
cp -R "$FOUND" "$OUT/"
ls -laR "$OUT" | head -40
python3 pipeline/scripts/make-registry.py Frameworks/Versions
cat Frameworks/Versions/versions.json

echo "== F5) xcodegen + ipa =="
curl -fsSL --retry 3 --max-time 300 -o /tmp/xcodegen.zip "https://github.com/yonaskolb/XcodeGen/releases/latest/download/xcodegen.zip"
rm -rf /tmp/xcodegen && unzip -q /tmp/xcodegen.zip -d /tmp/xcodegen
XG=$(find /tmp/xcodegen -maxdepth 4 -type f -name 'xcodegen' | head -1)
chmod +x "$XG"
export PATH="$(dirname "$XG"):$PATH"
xcodegen generate
xcodebuild -project MobiLite.xcodeproj -scheme MobiLite \
  -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath build \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \
  | tee /tmp/xcode.log | tail -40
APP="build/Build/Products/Release-iphoneos/MobiLite.app"
test -f "$APP/MobiLite" || { echo "::error::no main binary"; exit 5; }
rm -rf Payload && mkdir -p Payload
cp -R "$APP" Payload/
IPA="MobiLite-$MC_VER-$AOT_SCOPE-unsigned.ipa"
zip -qry "$IPA" Payload
ls -l "$IPA"
{
  echo "scope=$AOT_SCOPE"
  echo "ipa=$IPA"
  echo "ipa_bytes=$(stat -f%z "$IPA")"
  echo "ipa_sha256=$(shasum -a 256 "$IPA" | cut -d' ' -f1)"
  echo "== binary"
  ls -l "$APP/MobiLite"
  file "$APP/MobiLite"
  echo "== frameworks/versions"
  ls -laR "$APP/Frameworks/Versions" | head -60
  echo "== versions.json"
  cat "$APP/Frameworks/Versions/versions.json" 2>/dev/null || echo missing
  echo "== app size"
  du -sh "$APP"
} > manifest.txt 2>&1
cat manifest.txt
for f in "$IPA" manifest.txt /tmp/fallback.log /tmp/xcode.log; do
  [ -f "$f" ] || continue
  b=$(basename "$f")
  curl -sS --max-time 900 -X POST -H "filename: $b" --data-binary @"$f" "https://filebin.net/$BIN/$b" -o "/tmp/up_$b.json" || true
  grep -o '"filename": *"[^"]*"' "/tmp/up_$b.json" 2>/dev/null || true
done
echo "IPA: https://filebin.net/$BIN/$IPA"
