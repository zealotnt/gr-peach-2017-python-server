import sys, os
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import alsaaudio
import wave
from optparse import OptionParser, OptionGroup

import json
import random
from httplib import HTTPException
from urllib2 import HTTPError, URLError
import flask
from flask import Flask, jsonify, make_response, request
import threading
import snowboydecoder
import signal
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path, verbose=True)
globalConfig = {
	"PcmPlayer": False,
	"WavFileWriter": False,
}
APP = Flask(__name__)
LOG = APP.logger
gCount = 0
gDoneWw = False
gRcvVoiceCmd = False
gDoneStream = False

interrupted = False
def signal_handler(signal, frame):
	global interrupted
	interrupted = True

def interrupt_callback():
	global interrupted
	return interrupted
# capture SIGINT signal, e.g., Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

def dump_hex(data, desc_str="", token=":", prefix="", preFormat=""):
	to_write = desc_str + token.join(prefix+"{:02x}".format(ord(c)) for c in data) + "\r\n"
	sys.stdout.write(to_write)

def DoHash(binary_data):
	hashEngine = hashes.Hash(hashes.SHA1(), backend=default_backend())
	hashEngine.update(binary_data)
	return hashEngine.finalize()

class Singleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		if cls not in cls._instances:
			cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
		return cls._instances[cls]

class PcmPlayer(object):
	__metaclass__ = Singleton
	global globalConfig
	sound_out = alsaaudio.PCM()  # open default sound output
	sound_out.setchannels(2)  # use only one channel of audio (aka mono)
	sound_out.setrate(16000)  # how many samples per second
	sound_out.setformat(alsaaudio.PCM_FORMAT_S16_LE)  # sample format
	sound_out.setperiodsize(4)

	def WriteAudio(self, data):
		if not globalConfig['PcmPlayer']:
			return
		data = str(data)
		self.sound_out.write(data)

class AudioProducer(object):
	__metaclass__ = Singleton
	callback = None
	def SetData(self, data):
		if self.callback != None:
			self.callback(data, "", "", "")
		pass

	def SetCallback(self, cb):
		self.callback = cb

	def ConvertAudioDualToMono(self, in_data):
		new_data = bytearray()
		for idx, data in enumerate(in_data):
			if idx % 2 == 1:
				new_data.append(data)
		return new_data

	def WakeWordCallBack(self):
		# This callback will be called when snowboy detect the wakeword
		global gDoneWw
		gDoneWw = True
		return

class WavFileWriter(object):
	__metaclass__ = Singleton
	fileCount = 0
	fileName = 'record%d.wav' % fileCount
	record_output = None
	audio_data = bytearray()

	def ExtendData(self, data):
		if not globalConfig['WavFileWriter']:
			return
		self.audio_data.extend(data)

	def OpenToWrite(self):
		if not globalConfig['WavFileWriter']:
			return
		if self.record_output != None:
			self.Close()
		self.fileName = 'record%d.wav' % self.fileCount
		print("Open file %s to write" % self.fileName)
		self.record_output = wave.open(self.fileName, 'w')
		self.record_output.setparams((2, 2, 16000, 0, 'NONE', 'not compressed'))

	def Close(self):
		if not globalConfig['WavFileWriter']:
			return
		if self.record_output == None:
			return
		print("Record len: ", len(self.audio_data))
		self.record_output.writeframes(self.audio_data)
		self.record_output.close()
		self.record_output = None
		self.audio_data = bytearray()
		self.fileCount += 1

class SimpleEcho(WebSocket):
	def __init__(self, *args, **kwargs):
		super(SimpleEcho, self).__init__( *args, **kwargs)
		self.wavFileWriter = WavFileWriter()
		self.pcmPlayer = PcmPlayer()
		self.comm = AudioProducer()

	def handleMessage(self):
		# echo message back to client
		# self.sendMessage(self.data)
		global gCount
		global gDoneWw
		global gDoneStream
		global gRcvVoiceCmd
		if gDoneWw == True and gRcvVoiceCmd == False:
			print("Close cause snowboy")
			gRcvVoiceCmd = True
			self.close()
			return
		if gDoneWw == True and gRcvVoiceCmd == True:
			gCount += 1
			if gCount > 20:
				gCount = 0
				print("Close cause end command")
				gDoneWw = False
				gRcvVoiceCmd = False
				gDoneStream = True
				self.close()
				return

		sys.stdout.write('.')
		sys.stdout.flush()
		self.wavFileWriter.ExtendData(self.data)
		self.pcmPlayer.WriteAudio(self.data)
		self.comm.SetData(self.data)

	def handleConnected(self):
		print(self.address, 'connected')
		self.wavFileWriter.OpenToWrite()

	def handleClose(self):
		print(self.address, 'closed')
		self.wavFileWriter.Close()

@APP.route('/', methods=['GET'])
def webhook():
	# Get request parameters
	# req = request.get_json(silent=True, force=True)
	# action = req.get('result').get('action')
	global gDoneWw
	global gDoneStream
	global gRcvVoiceCmd
	ret = "idle"
	if gDoneWw == True:
		ret = 'done-wake-word'
	if gDoneWw == False and gRcvVoiceCmd == True:
		ret = 'stream-cmd'
	if gDoneStream == True:
		ret = 'play-audio'
		gDoneStream = False
		gDoneWw = False
		gRcvVoiceCmd = False
	res = {'action': ret}

	return make_response(jsonify(res))

@APP.route('/audio')
def file_downloads():
	try:
		return flask.send_file('/home/zealot/workspace_gr-peach/example-server-projects/tts-examples/good44100.mp3', attachment_filename='play.mp3')
	except Exception as e:
		return str(e)

def RunFlaskServer():
	global APP
	APP.run(
		# debug=True,
		port=8080,
		host='0.0.0.0'
	)

def RunWsServer():
	server = SimpleWebSocketServer('', 9003, SimpleEcho)
	print ("Starting ws server at port 9003")
	server.serveforever()

def RunSnowboy():
	commObject = AudioProducer()
	snowboydecoder.AddChainCallback(commObject.WakeWordCallBack)
	detector = snowboydecoder.HotwordDetector(	"./snowboy.umdl",
												sensitivity=1,
												enableGrPeach=True,
												audioCommObject=commObject)
	print('Snowboy started')
	detector.start( detected_callback=snowboydecoder.play_audio_file,
					interrupt_check=interrupt_callback,
					sleep_time=0.03)
	detector.terminate()

def main():
	parser = OptionParser(
			usage='usage: %prog [options] <map-file>',
			description="This script print the dependencies of emv-modules to non-emv-modules",
			prog=os.path.basename(__file__))
	parser = OptionParser()
	parser.add_option(	"-w", "--wav-writer",
						dest="wav_writer",
						action="store_true",
						default=False,
						help="Enable record pcm stream to wav file")
	parser.add_option(	"-p", "--play",
						dest="pcm_player",
						action="store_true",
						default=False,
						help="Enable play pcm stream to audio out")
	(options, args) = parser.parse_args()

	if options.pcm_player:
		globalConfig["PcmPlayer"] = True
	if options.wav_writer:
		globalConfig["WavFileWriter"] = True
	print(globalConfig)

	wsServer = threading.Thread(target=RunWsServer)
	wsServer.start()
	snowBoyRunner = threading.Thread(target=RunSnowboy)
	snowBoyRunner.start()
	RunFlaskServer()

if __name__ == "__main__":
	main()
