#!/usr/bin/env bash
# MobiLite v17 AOT fallback: 直调 RoboVM AppCompiler（补 Info.plist）
set -eo pipefail
cd "${GITHUB_WORKSPACE:-$PWD}"
TOP="$PWD"
VB="$TOP/pipeline/version-build"
exec > >(tee -a /tmp/fallback.log) 2>&1

on_exit() {
  rc=$?
  if [ "$rc" != "0" ]; then
    grep -nE "Exception|error:|No such|not found|FAILED|Could not" /tmp/fallback.log 2>/dev/null | tail -15 > /tmp/fctx.log || true
    while IFS= read -r l; do echo "::error::$l"; done < /tmp/fctx.log || true
  fi
  exit $rc
}
trap on_exit EXIT

echo "== F1) RoboVM compiler jar =="
mkdir -p "$HOME/.tools"
curl -fsSL --retry 5 --retry-all-errors -o "$HOME/.tools/rgp.jar" \
  "https://repo1.maven.org/maven2/com/mobidevelop/robovm/robovm-gradle-plugin/2.3.26/robovm-gradle-plugin-2.3.26.jar"
ls -l "$HOME/.tools/rgp.jar"

AOTJ=$(find "$TOP/pipeline/build/$MC_VER/aot-input" -maxdepth 1 -name '*.jar' 2>/dev/null | head -1)
echo "aotjar=$AOTJ"
[ -f "$AOTJ" ] || { echo "::error::no aot-input jar"; exit 9; }

echo "== F2) javac MakeFramework =="
mkdir -p /tmp/mkf/classes
javac -nowarn -cp "$HOME/.tools/rgp.jar" -d /tmp/mkf/classes "$TOP/.ci/MakeFramework.java"

echo "== F3) compile framework =="
java -cp "/tmp/mkf/classes:$HOME/.tools/rgp.jar" MakeFramework \
  "$AOTJ" "$HOME/.tools/robovm-rt.jar" "$HOME/.tools/robovm-objc.jar" "$HOME/.tools/robovm-cocoatouch.jar" \
  "$VB/Info.plist" "$VB" GameRuntime

echo "== F4) collect =="
OUT="Frameworks/Versions/$MC_VER"
FOUND=$(find "$VB/build" -maxdepth 10 \( -name 'GameRuntime.xcframework' -o -name 'GameRuntime.framework' -o -name 'GameRuntime.dylib' \) 2>/dev/null | head -1)
if [ -z "$FOUND" ]; then
  echo "::error::no GameRuntime artifact"
  find "$VB/build" -maxdepth 5 | head -60
  exit 4
fi
echo "found=$FOUND"
mkdir -p "$OUT"
rm -rf "$OUT/GameRuntime.xcframework" "$OUT/GameRuntime.framework" "$OUT/GameRuntime.dylib"
cp -R "$FOUND" "$OUT/"
python3 pipeline/scripts/make-registry.py Frameworks/Versions
cat Frameworks/Versions/versions.json

echo "== F5) XcodeGen + IPA =="
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
  ls -l Payload/MobiLite.app/MobiLite
  file Payload/MobiLite.app/MobiLite
  ls -laR Payload/MobiLite.app/Frameworks/Versions | head -120
} > manifest.txt 2>&1
cat manifest.txt
for f in "$IPA" manifest.txt /tmp/fallback.log /tmp/xcode.log; do
  [ -f "$f" ] || continue
  b=$(basename "$f")
  curl -sS --max-time 900 -X POST -H "filename: $b" --data-binary @"$f" "https://filebin.net/$BIN/$b" -o "/tmp/up_$b.json" || true
  grep -o '"filename": *"[^"]*"' "/tmp/up_$b.json" 2>/dev/null || true
done
echo "IPA: https://filebin.net/$BIN/$IPA"
