#!/usr/bin/env python3
# 在 build-version.sh 的 2/5（assemble 完 aot-input.jar）之后插一步 strip LocalVariableTable。
# Soot 前端对 jvmdowngrader 写坏的局部变量表零容忍，full 口径必挂。
import sys

P = 'pipeline/scripts/build-version.sh'
s = open(P, encoding='utf-8').read()

ANCHOR = 'log "==== 2b/5 生成编译期桩 jar ===="'

BLOCK = '''# ---- 2a2/5 剔掉 LocalVariableTable（Soot 的 LocalVariables 校验会因此直接抛）----
STRIP_CLASSES="$HOME/.tools/stripdebug"
if [ -d "$STRIP_CLASSES" ] && [ -f "$AOT_INPUT_DIR/aot-input.jar" ]; then
  log "==== 2a2/5 剔掉 LocalVariableTable（jvmdowngrader 局部变量表冲突）===="
  set +e
  java -cp "$HOME/.tools/asm.jar:$STRIP_CLASSES" StripDebug \\
      "$AOT_INPUT_DIR/aot-input.jar" "$AOT_INPUT_DIR/aot-input-nodebug.jar" \\
      > "$WORK/strip.log" 2>&1
  SRC=$?
  set -e
  tail -3 "$WORK/strip.log" || true
  if [ "$SRC" -eq 0 ] && [ -s "$AOT_INPUT_DIR/aot-input-nodebug.jar" ]; then
    mv "$AOT_INPUT_DIR/aot-input-nodebug.jar" "$AOT_INPUT_DIR/aot-input.jar"
    log "strip ok: $(du -h "$AOT_INPUT_DIR/aot-input.jar" | cut -f1)"
  else
    log "WARN: strip 失败（rc=$SRC），继续用原 jar"
  fi
fi

'''

if '2a2/5 剔掉 LocalVariableTable' in s:
    print('strip patch already applied')
else:
    if ANCHOR not in s:
        print('ANCHOR NOT FOUND - abort')
        sys.exit(1)
    s = s.replace(ANCHOR, BLOCK + ANCHOR, 1)
    open(P, 'w', encoding='utf-8').write(s)
    print('strip patch inserted')

# ---- 追加：3b 段前把 robovm-gradle-plugin jar 落到 $HOME/.tools ----
# 现状：workflow 只把 rt/objc/cocoatouch/bro-bridge 放进 .tools，漏了插件本体，
# 于是 3c 的 find($HOME/.gradle/caches $HOME/.tools) 找不到 → ERROR rc=3。
PLUG = '''# ---- 3b/3c 前确保 plugin jar 在手（find 会搜 $HOME/.tools）----
PVER="${ROBOVM_VERSION:-3.0.1}"
PJAR="$HOME/.tools/robovm-gradle-plugin-$PVER.jar"
if [ ! -f "$PJAR" ]; then
  log "下载 robovm-gradle-plugin-$PVER.jar"
  curl -fsSL --retry 3 -o "$PJAR" \\
    "https://repo1.maven.org/maven2/com/mobidevelop/robovm/robovm-gradle-plugin/$PVER/robovm-gradle-plugin-$PVER.jar" \\
    || log "WARN: plugin jar 下载失败"
fi
ls -l "$PJAR" 2>/dev/null || true

'''

s2 = open(P, encoding='utf-8').read()
if '确保 plugin jar 在手' in s2:
    print('plugin patch already applied')
else:
    ANCH = '  if [ -n "$RAWBIN" ]; then'
    if ANCH in s2:
        s2 = s2.replace(ANCH, PLUG + ANCH, 1)
        open(P, 'w', encoding='utf-8').write(s2)
        print('plugin patch inserted')
    else:
        print('plugin anchor missing')
