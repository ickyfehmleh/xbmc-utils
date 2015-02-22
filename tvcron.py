#!/usr/bin/python2.7
#
# monitor a dir, look for tv_*, find a file to copy, and copy that file.  then note that the directory has been processed.
# TODO: 
# - copy file as $dirName+.$fileExt because groups have shitty naming
#

import os
import os.path
import time
import sys
import glob
import re
import traceback
import string
import shutil
from string import Template
import urllib2

PROCESS_DIR="/shared/process/Series"
LOGFILE="$HOME/.tvcron/logfile"
PID_FILE="$HOME/.tvcron/pid"
SLEEP_TIME=40
PRCP="tvcp"

def removeUnnecessaryFiles(baseDir):
	for ext in ['.nfo', '.nzb', '.html', '.url']:
		p = os.path.join(baseDir, '*' + ext)
		for f in glob.glob(p):
			os.remove(f)
			logstr('Removed [%s]' % f)

def sendUpdateToSickbeard(url):
	response = None
	try:
		logstr('Sending Sickbeard update to [%s]' % url)
                f = urllib2.urlopen( url )
                response = f.read()
                f.close()
		logstr('Updated Sickbeard')
        except IOError, e:
                print e
        return response

def updateSickbeard():
	args = dict()
	args['SB_HOST']="xbmc"
	args['SB_PORT']="8081"
	args['SB_PATH']="/sickbeard"
	args['SB_URL_ARGS']="dir=/shared/process/Series"
	urlTemplate = Template("http://${SB_HOST}:${SB_PORT}${SB_PATH}/home/postprocess/processEpisode?${SB_URL_ARGS}")
	url = urlTemplate.substitute(args)
	sendUpdateToSickbeard(url)

def logstr(msg):
	t = time.strftime( '%Y-%m-%d @ %I:%M:%S %P' )
	print '[%s]: %s' % (t, msg)

def determineFilename(dir):
	foundFile = None
	if os.path.isfile(dir):
		foundFile = dir
	else:
		for root, dirs, files in os.walk(dir):
			for file in files:
				fn, ext = os.path.splitext(file.lower())
				
				if ext in ['.avi', '.mkv', '.mp4', '.mpg', '.m4v']:
					foundFile = os.path.join(root,file)
				# remove unnecessary files
				elsif ext in ['.html','.url','.nfo','.nzb']:
					absfn = os.path.join(root, file)
					logstr('Removing [%s]' % absfn )
					os.remove( absfn )
	return foundFile

def handleShowCopy(rootDir,fn):
	## copy file as dirName + . + fileExt because groups suck at naming
	copyFile = None

	hackedFileExt = os.path.splitext(fn)[1]
	hackedFileName = rootDir
	copyFile = hackedFileName + hackedFileExt

	# eliminate 'tv_' since we havent been processed yet
	copyFile = re.sub('^tv_', '', copyFile)

	# copy the file via minicp
	outpDirFile = os.path.join( PROCESS_DIR, copyFile )
	inpDirFile = os.path.abspath(fn)

	if not os.path.exists(fn):
		logstr( 'ERROR: [%s] does not exist (yet?)' % fn )
		return

	logstr( 'Copying [%s] to [%s/%s]' % (fn, PROCESS_DIR, copyFile) )

	#cmd = 'minicp %s %s' % (inpDirFile, outpDirFile)
	#os.system(cmd)
	try:
		shutil.move(inpDirFile, outpDirFile)
	except OSError oe:
		pass

	# wipe unnecessary files
	removeUnnecessaryFiles(rootDir)

	# rename from tv_what to just what
	nonTvDir = rootDir[3:]
	logstr( 'Renaming [%s] to [%s]' % (rootDir, nonTvDir) )
	os.rename(rootDir, nonTvDir)

	# tell sickbeard to update?
	logstr( "Telling SickBeard about the new file..." )
	updateSickbeard()

logstr( 'Starting in directory %s' % os.getcwd() )
cont = True
while cont:
	try:
		fileList = glob.glob('tv_*')
		if len(fileList) > 0:
			logstr( 'Examining directory %s' % os.getcwd() )

			# look at $TV_ROOT_DIR/tv_*
			for file in fileList:
				logstr( 'Found directory [%s]' % file)
				# sleep for a second because postfetch.sh may be moving a file over
				time.sleep(1)

				copyFile = determineFilename(file)
				if copyFile is not None:
					handleShowCopy(file,copyFile)
				else:
					logstr( 'Could not find any files to copy in [%s]' % file)
		time.sleep(SLEEP_TIME)
	except KeyboardInterrupt:
		cont = False
		logstr( 'Exiting gracefully!' )
	except:
		ex = traceback.format_exc()
		#ex = str(sys.exc_info())
		logstr( 'Unhandled exception: %s ' % ex )
		cont = False
