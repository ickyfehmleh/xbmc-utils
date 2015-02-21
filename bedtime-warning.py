#!/usr/bin/python
#
# Bedtime Warning System
#
# - 5 minutes prior: 
#    - warn that bedtime quickly approaches
# 
# - at bedtime:
#    - announce that it is bedtime!
#    - pause whatever is being watched
#    - make a bookmark
#    - stop movie

# https://github.com/jcsaaddupuy/python-xbmc 
from xbmcjson import XBMC, PLAYER_VIDEO
import sys
import getopt
import os.path

# ignore file
IGNORE_FILE='~/bedtime-ignore'

def handleInstance(host, isWarning=False):
	xbmcHost = 'http://%s/jsonrpc' % host
	xbmc = XBMC(xbmcHost)
	xbmc.GUI.ShowNotification({"title":title, "message":msg})

	if not isWarning:
		# get active player
		players = xbmc.Player.GetActivePlayers()	

		if len(players.get('result')) == 0:
			print 'Nothing playing on %s!' % host
		else:
			for player in players.get('result'):
				playerId = player.get('playerid')

				# player.stop
				if player['type'] == 'video':
					xbmc.Player.Stop([PLAYER_VIDEO])

if __name__ == '__main__':
	titleWarn='Bedtime Approaches!'
	msgWarn = 'Bedtime in 5 minutes!'

	titleBedtime='It Is Now Bedtime!'
	msgBedtime='Time for bed!'

	title=titleBedtime
	msg=msgBedtime
	isWarning = False

	ignoreFile = os.path.expanduser( os.path.expandvars( IGNORE_FILE ) )
	ignoreFileExists = os.path.exists( ignoreFile )

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'w', ['warn'])
	except getopt.GetoptError:
		print 'USAGE: %s [-w] <host:port> ... <hostN:port>' % sys.argv[0]
		sys.exit()

	for o,a in opts:
		if o in ('-w','--warn'):
			title=titleWarn
			msg=msgWarn
			isWarning=True

	# if IGNORE_FILE exists, exit
	if ignoreFileExists:
		print 'IGNORE FILE [%s] EXISTS!  Quitting!' % ignoreFile

		# if we're not warning, delete the file; it's only valid once
		if not isWarning:
			print 'Removed ignore file'
			os.remove( ignoreFile )
	else:
		for host in args:
			# no port specified, default to :8080
			if host.rfind(':') < 0:
				host = host + ':8080'
			handleInstance(host, isWarning)
