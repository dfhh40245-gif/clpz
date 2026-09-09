#!/usr/bin/env bash
set -u
cd mobile-android
result=0
gradle :app:connectedDebugAndroidTest || result=$?
adb pull /sdcard/Android/data/com.clpz.mobile/files/screenshots ../ui-screenshots || true
exit "$result"
