#!/usr/bin/python2.7
#
# fetch files
# 
import Queue
import shlex
import threading
import signal
import traceback
import sys
import urllib2
import time
import subprocess
import os.path
import os
import ssh
import xmpp
import ConfigParser
import string

COMMAND_PREFIX='cmd'
SLEEP_TIME=120 # two minutes, should fill up logs anyway
PAUSE_TIME=60  # one minute to pause between rsync-ssh requests
PID_FILE = os.path.join( os.getcwd(), 'fetcher.pid' )

class LogMessage(object):
	_msg = None
	_time = time.time()
	gtalk = False
	stale = False

	def __init__(self,message,gtalk=False):
		self._msg = message
		self.gtalk = gtalk

	@property
	def printableMessage(self):
		return self._msg

	@property
	def message(self):
		pmsg = self._msg
		lc = time.localtime(self._time)
		t = time.strftime( '%Y-%m-%d @ %I:%M:%S %p', lc )
		pmsg = '[%s]: %s' % (t, self._msg)
		return pmsg

class FileFetcher(threading.Thread):
	_hostname = None
	_ssh = None
	_outQueue = None
	_inQueue = None
	_postFetchCmd = None
	_inQueue = None
	_outQueue = None
	_fetchFlag = None
	_shutdownFlag = None

	def __init__(self,inQueue,outQueue,hostname):
		threading.Thread.__init__(self)
		self._inQueue = inQueue
		self._outQueue = outQueue
		self._hostname = hostname
		self.daemon = True
		self._fetchFlag = threading.Event()
		self._shutdownFlag = threading.Event()
		self.setName('FileFetcher')

	def setPostFetchCommand(self,cmd):
		self._postFetchCmd = cmd

	def connectToSsh(self):
		self._ssh = ssh.Connection( self._hostname, username='thowie' )  ## FIXME: externalize to config

	def disconnect(self):
		self._ssh.close()

	def logmsg(self,msg):
		if self._ssh is not None:
			self._ssh.execute( 'echo "%s" >>~/fetched.files' % msg.message )
		if msg.stale == False:
			self._outQueue.put(msg)

	def printmsg(self,msg,gtalk=False):
		m = LogMessage(msg,gtalk=gtalk)
		self.logmsg(m)

	def stopFetching(self):
		self._fetchFlag.set()

	def startFetching(self):
		self._fetchFlag.clear()

	def postFetchFile(self,filename):
		self.printmsg('Post-processing %s' % filename )
		# run command if specified in config
		procArgs = [self._postFetchCmd, filename]
		p = subprocess.Popen( procArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE,close_fds=True )
		status = p.wait()
		outp = p.stdout.readlines()

		if status != 0:
			self.printmsg( 'Failed to execute post-fetching command [%s]!' % self._postFetchCmd )
		else:
			for p in outp:
				p = p[:-1] # remove \n
				self.printmsg( 'POSTFETCH: ' + p )

	def getTorrentFile(self,filename):
		self.printmsg( 'Now downloading: %s' % filename, gtalk=True )
		procArgs = ['rsync', '-L', '--partial', '-e', 'ssh', '-r', '-v', 'thowie@' + self._hostname + ':' + filename, '.' ]
		#procArgs = ['rsyncssh.sh', 'thowie@' + self._hostname + ':' + filename ]  ## FIXME: externalize to config
		p = subprocess.Popen( procArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE,close_fds=True )

		## should check self._shutdownFlag() and self._fetchFlag here; if either are set,
		## need to kill the Popen subprocess and return immediately as we're shutting down
		while p.poll() is None:
			if self._fetchFlag.isSet():
				self.printmsg('Aborting fetch of [%s], killing pid [%s]!' % (filename, p.pid),gtalk=True)
				p.terminate()
				return
			else:
				self.pause( 3 )
		status = p.returncode

		output = p.stdout.readlines()
		rsyncTotal = output.pop()
		rsyncSent = output.pop()

		if status != 0:
			self.printmsg( 'Failed to execute rsync!' )
		else:
			rsyncSent = rsyncSent[:-1] # remove trailing \n
			self.printmsg( rsyncSent, gtalk=True )
			self.printmsg( 'Fetched file %s' % filename )
			localFn = os.path.basename( filename )
			# post-fetch command
			if self._postFetchCmd is not None:
				self.postFetchFile( localFn )
			self.clearTorrentFile(filename)

	def clearTorrentFile(self,filename):
		for line in self._ssh.execute('~/bin/ssh-cleartorrents.sh %s' % filename ): ## FIXME: externalize to config
			line = line[:-1]
			self.printmsg( line )

	def run(self):
		self.connectToSsh()
		while not self._shutdownFlag.isSet():
			try:
				if not self._fetchFlag.isSet():
					self.process()
				self.pause( SLEEP_TIME )
			except:
				exc = traceback.format_exc(limit=2)
				self.connectToSsh()
				self.printmsg('Reconnecting to SSH after exception %s' % exc, gtalk=True )

	def pause(self,duration):
		# process our queues and only sleep for 1 second intervals
		for i in range(duration):
			self.processQueue( self._inQueue )
			if self._shutdownFlag.isSet():
				# if we're shutting down, return immediately!
				return
			else:
				time.sleep( 1 )

	def processQueue(self,q):
		# check to see if we have logs to process
		while not q.empty():
			msg = None
			try:
				msg = q.get()
				msg.stale=True
				self.logmsg( msg )
				q.task_done()
			except Queue.Empty:
				continue

	def process(self):
		self._ssh.get( 'files.to.get' )
		f = open( 'files.to.get', 'r' )

		for line in f.readlines():
			line = line[:-1]

			if not self._fetchFlag.isSet():
				if len(line) > 0 and not (line == ''):
					self.getTorrentFile( line )
				self.pause(PAUSE_TIME)
			#else:
			#	# this could get annoying
			#	self.printmsg('DEBUG: quitFlag.isSet, so not fetching!')
		f.close()
		return True

	def shutdown(self):
		self.stopFetching()
		self._shutdownFlag.set()

################################################################################################

class GtalkFetcher(object):
	_gtalkLogin = None
	_gtalkPasswd = None
	_client = None
	_tmpl = None
	_hostname = None
	_msgUsers = []
	_logfile = None
	_fileFetcher = None
	_inQueue = None
	_outQueue = None

	def __init__(self,hostname):
		self._hostname = hostname
		self.initFetcher()
		self.connect()

	def __init__(self,hostname,login,passwd):
		self._hostname = hostname
		self._gtalkLogin = login
		self._gtalkPasswd = passwd
		self.initFetcher()
		self.connect()

	def initFetcher(self):
		self._inQueue = Queue.Queue()
		self._outQueue = Queue.Queue()
		self._fileFetcher = FileFetcher(self._outQueue, self._inQueue, self._hostname)
		## FIXME need to setPostfetchCommand() before .start()ing!!!
		self._fileFetcher.start()

	def setPostFetchCommand(self,cmd):
		self._fileFetcher.setPostFetchCommand(cmd)

	def connect(self):
		if self._gtalkLogin is not None and self._gtalkPasswd is not None:
			self.connectToGTalk(self._gtalkLogin, self._gtalkPasswd )

	def setLogfile(self,value):
		self._logfile = open( value, 'a' )

	def disconnect(self):
		self._client.close()

	def addMessageUser(self, user):
		self._msgUsers.append( user )
	
	def connectToGTalk(self,login,passwd):
		self._client = xmpp.Client('gmail.com', debug=[])
		self._client.connect( server= ('talk.google.com',5223) )  ## FIXME: google talk is dead
		self._client.auth(login,passwd,'SshFetcherV2')
		# register to receive messages
		self._client.RegisterHandler('message',self.receivedMessage)
		self._client.sendInitPresence()
		self._client.Process(1)

	def receivedMessage(self, con, event):
		typ = event.getType()

		if typ != 'error':
			fromUser = event.getFrom().getStripped()
			msg = event.getBody()
			self.printmsg('Received msg of type [%s] consisting of [%s] from user [%s]' % (typ, msg, fromUser))
			if fromUser in self._msgUsers:
				if typ in ['message','chat',None]:
					self.printmsg('Message is authorized!')
					if msg.find(':') > 0:
						(cmd, args) = msg.split( ':' )
						if cmd == 'queue':
							self.changeFetchStatus( event, args )
						elif cmd == 'cmd':
							self.executeCommandMessage( event, args )
						# TODO are we a queue status command?
						# TODO see if its a command, execute it

	def changeFetchStatus(self, event, args):
		# change the underlying fetcher's status so it can/cannot fetch files
		fromUser = event.getFrom().getStripped()
		if args == 'stop':
			self._fileFetcher.stopFetching()
			self.printmsg('%s told me to stop fetching' % fromUser,gtalk=True)
		elif args == 'start':
			self._fileFetcher.startFetching()
			self.printmsg('%s told me to start fetching' % fromUser,gtalk=True)

	def executeCommandMessage( self, event, args ):
		fromUser = event.getFrom().getStripped()
		self.printmsg('User [%s] executed command [%s]' % (fromUser, args), gtalk=False)
		try:
			p = subprocess.Popen( shlex.split(str(args)), stdout=subprocess.PIPE, stderr=subprocess.PIPE,close_fds=True )
			status = p.wait()
			outp = p.stdout.readlines()
			lines = string.join(outp,'')
			print '### lines == ', type(lines)
			print '#### value == ', lines
			self.sendMessageToUser(lines, fromUser)
		except:
			exc = traceback.format_exc(limit=2)
			msg = 'Error executing: %s' % exc
			self.printmsg(msg, gtalk=False)
			self.sendMessageToUser(msg, fromUser)

	def sendMessageToUser(self,msg,user):
		self._client.send( xmpp.Message( user, msg ) )

	def sendMessage(self,msg):
		if self._client is not None:
			for user in self._msgUsers:
				self.sendMessageToUser( msg, user )

	def logmsg(self,msg):
		print msg.message

		if self._logfile is not None:
			self._logfile.write( msg.message )
			self._logfile.write( '\n' )
		if msg.gtalk:
			self.sendMessage(msg.printableMessage)
		if not msg.stale:
			self._outQueue.put(msg)

	def printmsg(self,msg,gtalk=False):
		m = LogMessage(msg,gtalk=gtalk)
		m.stale=True
		self.logmsg(m)

	def process(self):
		while not self._inQueue.empty():
			msg = self._inQueue.get()
			msg.stale=True
			self.logmsg( msg )
			self._inQueue.task_done()
		self._client.Process(1)
		return True

	def shutdown(self):
		self.printmsg('Shutting down gracefully!',gtalk=True)
		# terminate gtalk gracefully
		# tell fetcher thread to stop
		self._fileFetcher.shutdown()
		print '### fileFetcher.shutdown()'
		self._fileFetcher.join()
		print '### fileFetcher.join()'
		while self._fileFetcher.isAlive():
			print '### fetcher still alive!'
			time.sleep( 2 )
		# will need to ctrl-c again
		self.printmsg('Shutting down gracefully!')
		if self._logfile is not None:
			self._logfile.close()

############################################################################
def exitGracefully(reason=None):
	# remove pid
	if os.path.exists( PID_FILE ):
		os.remove( PID_FILE )

	if reason is not None:
		print reason
	sys.exit()

def processSignal(signalNumber, frame):
	exitGracefully('Received signal %d' % signalNumber )

# register to receive signals
#for recvSignal in [signal.SIGKILL, signal.SIGINT, signal.SIGTERM, signal.SIGUSR1, signal.SIGUSR2]:
#	signal.signal(recvSignal, processSignal)
############################################################################
cont = True

cfg = ConfigParser.SafeConfigParser()
cfg.read( os.path.expanduser( os.path.expandvars( '~/.fetcher.ini' ) ) )

## TODO move this to ConfigParser
hostname = cfg.get( 'fetcher', 'hostname' )
username = cfg.get( 'gtalk', 'username' )
passwd   = cfg.get( 'gtalk', 'password' )

f = GtalkFetcher(hostname, username, passwd )

if cfg.has_option('fetcher','logfile'):
	logfile = cfg.get('fetcher','logfile')
	logfile = os.path.expanduser( os.path.expandvars( logfile ) )
	f.setLogfile(logfile)

ops = cfg.options( 'gtalk recipients' )
for recip in ops:
	name = cfg.get( 'gtalk recipients', recip )
	f.addMessageUser( name )

if cfg.has_option('fetcher','fetch command'):
	cmd = cfg.get('fetcher','fetch command')
	cmd = os.path.expanduser( os.path.expandvars( cmd ) )
	f.setPostFetchCommand( cmd )

f.printmsg( 'Starting %s' % sys.argv[0] )

# write pid file
pf = open( PID_FILE, 'w' )
pf.write( str( os.getpid() ) )
pf.write( '\n' )
pf.close()

while cont:
	try:
		cont = f.process()
		time.sleep( 2 )
	except KeyboardInterrupt:
		cont = False
	except:
		f.connect()
		exc = traceback.format_exc(limit=2)
		f.printmsg( 'Reconnected after exception %s' % exc, gtalk=True )

f.printmsg( 'Exiting gracefully!')
f.shutdown()
os.unlink( PID_FILE )
sys.exit()
