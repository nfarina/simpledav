#!/bin/bash

cd `dirname $0`
CURUSER=`whoami`

sudo patch /Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine/google/appengine/tools/dev_appserver.py < dev_appserver-allmethods.patch
sudo chown $CURUSER:admin /Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine/google/appengine/tools/dev_appserver.py 