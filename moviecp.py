#!/usr/bin/python2.7
#
# given a directory, find a .nfo file
# FIXME: handle CD[12]-scenarios!  if findMovieFile() returns an array....
#        but how to differentiate CD[12] -vs- Movie+Sample?
#
# TODO:
#
import sys
import shutil
import urllib2
import urllib
import string
import imdb
import os
import re
import os.path
import urlparse
import getopt
import json
import time
from subprocess import call

MOVIE_ROOT="/shared/Movies"
#MOVIE_ROOT="/home/howie/tmp/shared.movies"
XBMC_HOST='192.168.1.53'
XBMC_PORT='8080'
HTTP_PROXY='http://localhost:3128'

def getImdbInstance():
	i = imdb.IMDb()
	i.set_proxy(HTTP_PROXY)
	return i

def copyMovie(localFile, outputPath,local=True):

	if local:
		shutil.copy(localFile,outputPath)
	else:
		p = call("minicp \"%s\" %s" % (localFile, outputPath), shell=True)

## FIXME: change to json api
def updateXbmc(movieDir):
	updateCmd = dict()
	updateCmd['id'] = '1'
	updateCmd['jsonrpc'] = '2.0'
	updateCmd['method'] = 'VideoLibrary.Scan'
	params = dict()
	params['directory'] = movieDir
	updateCmd['params'] = params

	url = 'http://%s:%s/jsonrpc' % (XBMC_HOST, XBMC_PORT)
	response = None
	try:
		req = urllib2.Request(url,json.dumps(updateCmd), {'Content-type':'application/json'})
		f = urllib2.urlopen( req )
		response = f.read()
		f.close()
	except IOError, e:
		print e
	return response

def findMovieFile(basePath):
	movies=[]
	
	if os.path.isdir( basePath ):
		for ext in ('.avi', '.mkv', '.mp4', '.mpg', '.m4v'):
			matches = findFilesWithExtension( basePath, ext )
			for m in matches:
				movies.append( m )
	else:
		movies.append( basePath )

	# fix the filenames
	fixedMovies = fixFileNames(movies)
	return fixedMovies

def findFilesWithExtension(basePath,fileExt):
	matches = []
	for root, dirs, files in os.walk(basePath):
		for f in files:
			if f.endswith(fileExt):
				matches.append( os.path.join( root, f ) )
	return matches

def fixFileNames(fileList):
	fixedNames = []

	for file in fileList:
		file = os.path.expandvars( os.path.expanduser( file ) )
		dirn = os.path.dirname( file )
		filen = os.path.basename( file )

		if filen.find(' ') > 0:
			# fix the spaces in the filename
			newfile = re.sub("[^A-Za-z0-9\.]", "_", filen)

			origfn = os.path.join( dirn, filen )
			newfn  = os.path.join( dirn, newfile )
			os.rename( origfn, newfn )
			fixedNames.append(newfn)
		else:
			fixedNames.append(file)
	return fixedNames

def findSingleFileWithExtension(basePath,fileExt):
	rv = None
	matches = findFilesWithExtension(basePath,fileExt)
	if len(matches) > 0:
		rv = matches[0]
	return rv

def getMovieFromUrl(url):
	#url = getImdbUrlFromFile(nfo)
	imdbId = getImdbIdFromUrl( url )
	movie = getMovieWithId( imdbId )
	return movie

# make a best-guess as to the movie name
def guessMovieName(fn):
	m = re.search('[0-9][0-9][0-9][0-9]', fn)
	idx = m.start()
	guessName = fn[:idx+4]
	guessName = re.sub('[\._]',' ', guessName)

	idb = getImdbInstance()
	try:
		movies = idb.search_movie(guessName)
	except imdb._exceptions.IMDbDataAccessError:
		print 'Bad fetch for %s, skipping' % guessName
		return None

	selectedMovie = None

	if len(movies) > 0:
        	selectedMovie = movies[0]
		idb.update(selectedMovie)
	return selectedMovie

def getImdbIdFromUrl(url):
	imdbId=None
	if url.rfind( 'Title?' ) > 0:
		# http://us.imdb.com/Title?0099864
		u = urlparse.urlparse(url)
		imdbId = u.query
	else:
		us = urlparse.urlsplit(url)
		p = us.path

		while p.endswith('/'):
			p = p[:-1] # kill trailing /

		id = os.path.basename(p)
		imdbId = id[2:] # first two chars are 'tt'
	#print '### imdbId == [%s]' % imdbId
	return imdbId

def getImdbUrlFromFile(nfoFile):
	url = None
	f = open( nfoFile, 'r' )
	for line in f.readlines():
		try:
			if line.index('imdb.com') > 0:
				m = re.search( 'http://([0-9A-Za-z\.\/\?]+)', line )
				url = m.group()
				break
		except:
			continue
	f.close()
	return url

def getMovieWithId(imdbId):
	movie = None
	if imdbId is not None:
		i = getImdbInstance()
		movie = i.get_movie(long(imdbId))
	return movie

def getMovieDirName(movie):
	title = movie['long imdb title']
	# fix the title, imdbpy-4.6 makes it wonky
	title = title.replace('?','')
	title = title.replace('\n','').replace('  ','').replace('()','').replace('  ',' ')
	title = title.rstrip().lstrip()
	title = re.sub("[\':\(\)]", "", title )
	title = re.sub('\"','', title) # drop "
	title = re.sub("^\ ", "", title)		# drop first char if its a space
	title = re.sub("[^A-Za-z0-9\.]", "_", title)
	title = re.sub('[^A-Za-z0-9_]+','', title) # "...And_Justice_For_All." ==> And_Justice_For_All
	return title

def createNfoFile(fn,movie,url):
	f = open( fn, 'w' )
	
	# create the xbmc .nfo file
	f.write( '<movie>\n' )
	writestr(movie,'title',f)
	writestr(movie,'year',f)
	writestr(movie,'plot outline', f, tag='plot')
	writestr(movie,'full-size cover url', f, tag='thumb')

	try:
		f.write( mktag( 'id', movie.getID() ) )
	except:
		pass

	f.write( '</movie>\n' )
	f.write( url )
	f.write( '\n' )
	f.close()

def writestr(movie,key,fh,tag=None):
	if tag is None:
		tag = key

	if movie.has_key( key ):
		try:
			fh.write( mktag( tag, movie[key] ) )
		except:
			pass

def mktag(tag,value):
	s = '<%s>%s</%s>\n' % (tag, str(value), tag)
	return s

#####
urls = []
url = None
specifyManually = False
onlyUpdate = False
isLocal = True
copyFiles = True

try:
        opts, args = getopt.getopt(sys.argv[1:], 'mulc', ['no-copy', 'local','manual','update-only'])
except getopt.GetoptError:
	print 'USAGE: %s <movie dir1>... <movie dirN>' % sys.argv[0]
	sys.exit()

if len(args) == 0:
	print 'USAGE: %s <movie dir1>... <movie dirN>' % sys.argv[0]
	sys.exit()

for o,a in opts:
	if o in ('-m','--manual'):
		specifyManually = True
		#if len(args) % 2 != 0:
		if len(args) > 2:
			print 'USAGE: %s <movie dir1> <url 1>' % sys.argv[0]
			sys.exit()
		url = args.pop()
	elif o in ('-u', '--update-only'):
		onlyUpdate = True
	elif o in ('-l','--local'):
		isLocal = True
	elif o in ('-c','--no-copy'):
		copyFiles = False
		
for arg in args:
	print 'Processing [%s]' % arg

	if onlyUpdate:
		updateXbmc(arg)
		continue

	# copy the movie file over
	movieFiles = findMovieFile( arg )
	movieUrl = None
	movie = None

	if len(movieFiles) > 0:
		print 'Found movie [%s]' % movieFiles

		if not specifyManually:
			nfoFile = findSingleFileWithExtension( arg, '.nfo' )
	
			if nfoFile is None:
				movie = guessMovieName(arg)

				if movie is None:
					print 'ERROR: Cannot find nfo file for [%s], no guesses :(' % arg
					continue

				# pause for 5 seconds to make sure its ok
				print
				print 'Guessed [%s] as movie name, waiting...' % movie.get('title')

				try:
					time.sleep(5)
				except KeyboardInterrupt:
					print 'Aborting processing for [%s]' % arg
					continue

				## assign movieUrl as we faked it
				movieUrl = 'http://www.imdb.com/title/tt' + movie.movieID
			else:
				movieUrl = getImdbUrlFromFile(nfoFile)
	
				if movieUrl is None:
					print 'ERROR: Cannot find url [%s]' % arg
					continue
		else:
			movieUrl = url

		if movie is None:
			# could be initialized in the guessMovieName() call
			movie = getMovieFromUrl( movieUrl )

		print 'Using movie name [%s] for arg [%s]' % (movie.get('title'), arg)
		movieDir = getMovieDirName( movie )
	
		# make output dir
		outpMovieDir = os.path.join( MOVIE_ROOT, movieDir )
		if not os.path.exists( outpMovieDir ):
			try:
				os.mkdir( outpMovieDir, 0777 )
			except:
				print '### FAILED TO mkdir(%s)!' % outpMovieDir
				continue

		if copyFiles:
			if len(movieFiles) == 1:
				movieFile = movieFiles[0]
				# copy movie file over
				(origMovieFile, ext) = os.path.splitext( movieFile )
				outpMovieFile = movieDir + ext
				outpMoviePath = os.path.join( MOVIE_ROOT, movieDir, outpMovieFile)
	
				copyMovie( movieFile, outpMoviePath, local=isLocal)
			else:
				for movieFile in movieFiles:
					outpMoviePath = os.path.join( MOVIE_ROOT, movieDir, os.path.basename( movieFile ) )
					copyMovie( movieFile, outpMoviePath, local=isLocal)

		# generate nfo file
		outpNfoFile = movieDir + '.nfo'
		outpNfoPath = os.path.join( MOVIE_ROOT, movieDir, outpNfoFile )
	
		if not os.path.exists( outpNfoFile ):
			createNfoFile( outpNfoPath, movie, movieUrl )

		# fetch thumbnail
		imgPath = os.path.join( MOVIE_ROOT, movieDir, 'folder.jpg' )

		if not os.path.exists( imgPath ):
			for imgKey in ['full-size cover url', 'find other urls']:
				if movie.has_key(imgKey):
					try:
						url = movie[imgKey]
						f = urllib2.urlopen(url)
						img = f.read()
						f.close()
						imgf = open( imgPath, 'w')
						imgf.write( img )
						imgf.close()
					except:
						print 'Failed to fetch artwork for [%s]' % arg

		print 'Updating XBMC...'
		updateXbmc(os.path.join(MOVIE_ROOT,movieDir))
