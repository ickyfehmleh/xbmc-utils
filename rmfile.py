#!/usr/bin/python2.7
#
# remove a movie; notify hosts that a movie is being removed;  
#
import os
import os.path
import shutil
import sys
import urllib2
import urllib
import traceback
import json

# https://github.com/jcsaaddupuy/python-xbmc 
from xbmcjson import XBMC

XBMC_PORT='8080'
XBMC_HOSTS=['xbmc']
XBMC_DB_HOST="xbmc"

class Remover:
	_db = None
	def _mkhost(self,host):
		xbmcHost = 'http://%s:%s/jsonrpc' % (host,XBMC_PORT)
		xbmcInstance = XBMC(xbmcHost)
		return xbmcInstance

	def __init__(self):
		self._db = self._mkhost(XBMC_DB_HOST)

	# return a map of data: label, tvshowid, movieid, episodeid, showname
	def getDataForFile(self,dir):
		rv = dict()
		response = self._db.Files.GetFileDetails(file=dir, media='video')
		#print response
		fileDetails = response.get('result').get('filedetails')

		if fileDetails is not None:
			rv['fileId'] = fileDetails.get('id')
			rv['label'] = fileDetails.get('label')
			rv['fileType'] = fileDetails.get('type')
		else:
			print '### Failed to fetch info for [%s]' % dir
		return rv

	def removeMovieId(self, movieId):
		rv = False
		try:
			self._db.VideoLibrary.RemoveMovie({'movieid':movieId})
			rv = True
		except:
			errmsg = traceback.format_exc(limit=2)
			print '### Exception removing movieId for [%s]: %s' % (movieId, errmsg)
		#print '### DEBUG: removeMovieId(%s): %s' % (movieId, rv)
		return rv

	def removeEpisodeId(self, fileId):
		rv = False
		try:
			self._db.VideoLibrary.RemoveEpisode({'episodeid':fileId})
			rv = True
		except:
			errmsg = traceback.format_exc(limit=2)
			print '### Exception removing episode for [%s]: %s' % (fileId, errmsg)
		return rv

	def removeFile(self,fn):
		rv = False

		# find out type of file
		fileData = self.getDataForFile(fn)
		isFileRemoved = False
		msgFileType = None
		msgFileName = os.path.basename(fn)

		if fileData is not None:
			fileId = fileData['fileId']

			# handle tv show
			if fileData.get('fileType') == 'episode':
				isFileRemoved = self.removeEpisodeId(fileId)
				msgFileType = 'Episode'

			elif fileData.get('fileType') == 'movie':
				isFileRemoved = self.removeMovieId(fileId)
				msgFileType = 'Movie'

			if isFileRemoved:
				self.notifyHosts(msgFileType, msgFileName)
				print 'Removing file [%s]' % fn
				os.remove(fn)
				rv = isFileRemoved
			else:
				print '### failed to remove [%s]' % fn
		else:
			print 'Failed to fetch file data for [%s]' % fn

		return rv

	def notifyHosts(self, fileType, name):
		for host in XBMC_HOSTS:
			xbmc = self._mkhost(host)
			xbmc.GUI.ShowNotification({"title":'Deleted %s' % fileType, "message":name})

	def isFileProcessable(self,fn):
		rv = True
		if f.endswith('.nfo'):
			rv = False
		elif f.endswith('.jpg'):
			rv = False
		elif f.endswith('.tbn'):
			rv = False
		elif f.startswith('.'):
			rv = False
		return rv
######################################################################################################

if __name__ == "__main__":
	db = Remover()

	for arg in sys.argv[1:]:
		if not os.path.exists( arg ):
			print '%s does not exist, skipping' % arg
			continue
		# wipe movie
		try:
			fp = os.path.abspath(arg)

			if os.path.isdir(arg):
				isDeleted = False

				for root, dirs, files in os.walk(fp):
					for f in files:
						fullPath = os.path.join( root, f)

						if db.isFileProcessable(f):
							if not db.removeFile(fullPath):
								print 'Could not dbremove %s!' % fullPath
								isDeleted = False
							else:
								isDeleted = True

					# only wipe dir if everything in it has been wiped
					if isDeleted:
						shutil.rmtree( fp )
			else:
				# abs path
				absArg = os.path.abspath(arg)
				if not db.removeFile(absArg):
					print 'Could not remove [%s]' % arg
		except:
			print traceback.format_exc(limit=2)
