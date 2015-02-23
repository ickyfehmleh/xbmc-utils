# xbmc-utils
Utils for XBMC installations.

*cron.py: monitors a directory for files prefixed with a certain category,
then converts and/or copies those files to other directories.  tvcron.py
handles tv_* shows, copying to an output dir that, say, SickBeard monitors; ebookcron.py
converts *.epub to MOBI for Kindle reading; mp3cron.py converts .flac files
to mp3.

mtfetch.py: A multi-threaded file fetcher that communicates gia Google Talk
or other XMPP hosts.

rmfile.py: Remove a file on disk and in XBMC's database.

moviecp.py: Given a 'scene' release, query IMDB, make the appropriate directory
for XBMC, copy the file over, make a .nfo file for XBMC, and fetch some artwork.
Also guesses at the movie name based on the directory, usually that works well.
Pauses for a few seconds in case it got a bad match, giving the operator time
to abort via Ctrl-C.

bedtime-warning.py: Remind your kids when its bedtime and turn off XBMC players.
