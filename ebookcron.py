#!/usr/bin/python2.7
#
# monitor a dir, look for ebook_*.tar
# mkdir $EBOOK_ROOT/$TODAY_DATE if it does not already exist
# untar file
# see if newly created dir contains *.epub
# if so, convert *.epub to *.mobi via "ebook-convert"
#
# NOTE: will need to change mtfetch post-fetch command to store ebook_*.tar in ebooks/ and not untar
#

import os
import os.path
import time
import sys
import glob
import shutil
import tarfile
import subprocess
import traceback

ARCHIVE_DIR="archive"
SLEEP_TIME=30
CONVERT_EBOOK_CMD='/usr/bin/ebook-convert'

def logstr(msg):
	t = time.strftime( '%Y-%m-%d @ %I:%M:%S %P' )
	print '[%s]: %s' % (t, msg)

def mkdirToday():
	today = time.strftime('%Y-%m-%d')

	if not os.path.exists( today ):
		os.mkdir( today )
	return today

def executeConversion(input, output):
	input = os.path.abspath(input)
	output = os.path.abspath(output)
	#input = '"' + input + '"'
	#output = '"' + output + '"'
	procArgs = [CONVERT_EBOOK_CMD, input, output]
	p = subprocess.Popen( procArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE,close_fds=True )
	status = p.wait()
	rv = False

	if status == 0:
		logfn = os.path.join(os.path.dirname(output), 'conversion.log')
		logf = open(logfn,'w')
		for line in p.stdout.readlines():
			logf.write(line)
		logf.close()
		rv = True
	else:
		logstr('Failed to execute conversion!')

	return rv

def archiveTarball(tarball):
	# ebook_what.tar
	outpFn = tarball.replace('ebook_','')

	if not os.path.exists(ARCHIVE_DIR):
		os.mkdir( ARCHIVE_DIR )
	outpFile = os.path.join(ARCHIVE_DIR, outpFn)
	logstr('Moving [%s] to [%s]' % (tarball, outpFile))
	shutil.move(tarball, outpFile)

def convertEpubFile(fn):
	mobifn = fn.replace('.epub', '.mobi')
	logstr('Converting EPUB [%s] to [%s]' % (fn, mobifn))

	if not os.path.exists(mobifn):
		s = executeConversion(fn, mobifn)

		# verify file exists before removing the epub
		if os.path.exists(mobifn):
			os.remove(fn)
			logstr('Removed old EPUB [%s]' % fn)
	else:
		logstr('File [%s] already exists, not overwriting.' % mobifn)

# should use os.walk() but im lazy
def changePermissions(rootDir):
	cmd = 'chmod -R 755 %s' % rootDir
	os.system(cmd)

def handleFile(fn):
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

		# we need to convert to mp3
		if name.rfind('.epub') > 0:
			convertEpubFile( os.path.join( outpDir, name) )
	tf.close()

	changePermissions(os.path.join(outpDir,createdDir))

	archiveTarball(fn)
	logstr('Finished with %s' % fn)

logstr( 'Starting in directory %s' % os.getcwd() )
cont = True
while cont:
	try:
		fileList = glob.glob('ebook_*.tar')
		if len(fileList) > 0:
			logstr( 'Examining directory %s' % os.getcwd() )

			for file in fileList:
				logstr( 'Found tarball [%s]' % file)
				handleFile(file)
		time.sleep(SLEEP_TIME)
	except KeyboardInterrupt:
		cont = False
	except:
		exc = traceback.format_exc(limit=2)
		logstr( 'Unhandled exception: %s ' % exc )
		cont = False
