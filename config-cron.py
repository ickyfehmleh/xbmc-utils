#!/usr/bin/python
#
# like mp3cron and ebookcron:
# 1- cd to config.rootDir
# 2- for each dir in config.monitor.baseDir:
# 3- check for config.monitor.fileRegex
# 4- if file exists, untar
# 5- loop through config.monitor.conversions.inputExtension
# 6- call config.monitor.conversions.script on inputFile and outputFile
# 7- optionally rm original file based on config value
# 8- optionally archive original tar to new dir based on config value
#

import json
import time
import os
import os.path
import glob
import tarfile
import subprocess
import shutil

CONFIG_FILE='config-sample.json'

########################################################################
def logstr(msg):
	t = time.strftime( '%Y-%m-%d @ %I:%M:%S %P' )
	print '[%s]: %s' % (t, msg)

def mkdirToday():
	today = time.strftime('%Y-%m-%d')

	if not os.path.exists( today ):
		os.mkdir( today )
	return today

########################################################################
def archiveTarball(tarball, archiveDir):
	# FIXME: need to know what category to replace, and where
	outpFn = tarball.replace('ebook_','')

	if not os.path.exists(archiveDir):
		os.mkdir( archiveDir )
	outpFile = os.path.join(archiveDir, outpFn)
	logstr('Moving [%s] to [%s]' % (tarball, outpFile))
	shutil.move(tarball, outpFile)

# should use os.walk() but im lazy
def changePermissions(rootDir):
	cmd = 'chmod -R 755 %s' % rootDir
	os.system(cmd)
########################################################################
def handleTarFile(conversions, fn):
	createdDir = None

	if not tarfile.is_tarfile(fn):
		return
	logstr('Extracting %s' % fn)
	outpDir = mkdirToday()
	tf = tarfile.open(fn)
	tf.extractall(path=outpDir)

	# are we dealing with *.epub files?
	for name in tf.getnames():
		# first name will be the dir to be created
		if createdDir is None:
			createdDir = name

		# do we need any conversions?
		handleConversions(conversions, os.path.join(outpDir, name))
	tf.close()

	changePermissions(os.path.join(outpDir,createdDir))

	logstr('Finished with %s' % fn)

########################################################################
def executeConversion(cmd, input, output):
	input = os.path.abspath(input)
	output = os.path.abspath(output)
	procArgs = [cmd, input, output]
	p = subprocess.Popen( procArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE,close_fds=True )
	status = p.wait()
	rv = False

	logstr('Status of [%s] is [%d]' % (cmd, status))

	if status == 0:
		logfn = os.path.join(os.path.dirname(output), 'conversion.log')
		logf = open(logfn,'w')
		for line in p.stdout.readlines():
			logf.write(line)
		logf.close()
		rv = True
	else:
		logstr('Failed to execute conversion!')

		for line in p.stderr.readlines():
			logstr('STDERR: %s' % line)

		for line in p.stdout.readlines():
			logstr('STDOUT: %s' % line)
	return rv

def handleFileConversion(conversion,origFile):
	cmd = conversion.get('script')
	inputExt = conversion.get('inputExtension')
	desiredExt = conversion.get('outputExtension')
	removeOriginal = conversion.get('removeOriginal')

	if cmd is None or inputExt is None or desiredExt is None:
		logstr('Conversion doesnt look right')
		return

	# may need to say 'at end of filename' here
	outputFile = origFile.replace(inputExt, desiredExt)

	logstr('Converting [%s] using [%s]' % (origFile,cmd))

	# check status of executing cmd
	status = executeConversion(cmd, origFile, outputFile)

	if status == 0:
		if removeOriginal == 'True':
			os.remove(origFile)

########################################################################
def handleConversions(conversions,origFile):
	fn,ext = os.path.splitext(origFile)

	for conversion in conversions:
		convertExtension = conversion.get('inputExtension')
		logstr('Checking for [%s] vs [%s]' % (ext, convertExtension))
		if ext == convertExtension:
			logstr('Found conversion: %s' % conversion)
			handleFileConversion(conversion,origFile)
########################################################################
if __name__ == '__main__':
	config = json.load(file(CONFIG_FILE))
	rootDir = config.get('rootDir')
	logstr('Changing to %s' % rootDir )

	for monitor in config.get('monitors'):
		subDir = monitor.get('baseDir')
		logstr('subdir == [%s]' % subDir)
		subDirPath = os.path.join(rootDir, subDir)
		logstr('Changing to [%s]' % subDirPath)

		os.chdir(subDirPath)
		
		globstr = monitor.get('fileRegex')
		logstr('Matching [%s]' % globstr)

		matches = glob.glob(globstr)
		
		if len(matches) > 0:
			conversions = monitor.get('conversions')

			for match in matches:
				logstr('Found match [%s]' % match)
				handleTarFile(conversions, match)

				# check to see if we should even archive
				archiveDir = monitor.get('archiveDir')

				if archiveDir is not None:
					archiveDirPath = os.path.join(subDirPath, archiveDir)
					archiveTarball(match, archiveDirPath)

		else:
			logstr('No matches found for [%s]!' % globstr)
