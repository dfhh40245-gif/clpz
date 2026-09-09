#!/usr/bin/env bash
set -u
cd mobile-android
result=0
gradle :app:connectedDebugAndroidTest || result=$?
adb pull /sdcard/Download/clpz-ui ../ui-screenshots || true
exit "$result"
