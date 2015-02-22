#!/usr/bin/python
#
# monitor a dir, look for mp3_*.tar
# mkdir $MUSIC_ROOT/$TODAY_DATE if it does not already exist
# untar file
# see if newly created dir contains *FLAC*
# if so, convert *.flac to mp3 using mkmp3.sh
#
# OPT: archive mp3_*.tar to appropriate moviedisk?
#
# NOTE: will need to change mtfetch post-fetch command to store mp3*.tar in music/ and not untar
#

import os
import os.path
import time
import sys
import glob
import shutil
import tarfile

ARCHIVE_DIR="archive"
SLEEP_TIME=30

def logstr(msg):
	t = time.strftime( '%Y-%m-%d @ %I:%M:%S %P' )
	print '[%s]: %s' % (t, msg)

def mkdirToday():
	today = time.strftime('%Y-%m-%d')

	if not os.path.exists( today ):
		os.mkdir( today )
	return today

def archiveTarball(tarball):
	# mp3_what.tar
	outpFn = tarball.replace('mp3_','')

	if not os.path.exists(ARCHIVE_DIR):
		os.mkdir( ARCHIVE_DIR )
	outpFile = os.path.join(ARCHIVE_DIR, outpFn)
	logstr('Moving [%s] to [%s]' % (tarball, outpFile))
	shutil.move(tarball, outpFile)

def convertFlacFile(fn):
	mp3fn = fn.replace('.flac','.mp3')
	logstr('Converting flac in [%s] to [%s]' % (fn,mp3fn))

	if not os.path.exists(mp3fn):
		#cmd = 'avconv -i "%s" -b 192k "%s"' % (fn, mp3fn)
		# farm out the mp3 creation to a script
		cmd = 'mkmp3.sh "%s" "%s"' % (fn, mp3fn)
		logstr( 'Executing command [%s]' % cmd )
		os.system(cmd)
		# rm .flac when done
		if os.path.exists( mp3fn ):
			os.remove(fn)
			logstr( 'Removed FLAC file [%s]' % fn )
	else:
		logstr( 'File [%s] already exists, not overwriting.' % mp3fn)

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

	# are we dealing with *.flac files?
	for name in tf.getnames():
		# first name will be the dir to be created
		if createdDir is None:
			createdDir = name

		# we need to convert to mp3
		if name.rfind('.flac') > 0:
			convertFlacFile( os.path.join( outpDir, name) )
	tf.close()

	changePermissions(os.path.join(outpDir,createdDir))

	archiveTarball(fn)
	logstr('Finished with %s' % fn)

logstr( 'Starting in directory %s' % os.getcwd() )
cont = True
while cont:
	try:
		fileList = glob.glob('mp3_*.tar')
		if len(fileList) > 0:
			logstr( 'Examining directory %s' % os.getcwd() )

			for file in fileList:
				logstr( 'Found tarball [%s]' % file)
				
				# sleep for a second to make sure postfetch.sh is done moving
				time.sleep(1)

				handleFile(file)
		time.sleep(SLEEP_TIME)
	except KeyboardInterrupt:
		cont = False
	except:
		logstr( 'Unhandled exception: %s ' % str(sys.exc_info()) )
        #       cont = False
