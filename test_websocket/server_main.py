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
from six.moves import queue
import io
import apiai
import json
import inspect
import git
from server_utility import *
from server_config import *
from server_objects import *
def get_git_root():
	CURRENT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) + os.sep
	path = CURRENT_DIR
	git_repo = git.Repo(path, search_parent_directories=True)
	git_root = git_repo.git.rev_parse("--show-toplevel")
	return git_root
sys.path.insert(0, get_git_root() + '/test_bluefinserial/bluefinserial')
from utils import *

def signal_handler(signal, frame):
	global interrupted
	interrupted = True

def interrupt_callback():
	global interrupted
	return interrupted
# capture SIGINT signal, e.g., Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

class SimpleEcho(WebSocket):
	def __init__(self, *args, **kwargs):
		super(SimpleEcho, self).__init__( *args, **kwargs)
		self.wavFileWriter = WavFileWriter()
		self.pcmPlayer = PcmPlayer()
		self.comm = AudioProducer()
		self.sttStreamer = SpeechToTextProducer()
		self.grStateMachine = GrPeachStateMachine()
		self.count = 0

	def handleMessage(self):
		# echo message back to client
		# self.sendMessage(self.data)
		self.data = AudioDualToMono(self.data)
		if self.grStateMachine.HandleWsMessage() == True:
			self.close()
			return

		self.count += 1
		if self.count > 0:
			sys.stdout.write('.')
			sys.stdout.flush()
			self.count = 0
		self.wavFileWriter.ExtendData(self.data)
		self.pcmPlayer.WriteAudio(self.data)
		# self.sttStreamer.Fill_buffer(self.data)
		self.comm.SetData(self.data)

	def handleConnected(self):
		# self.address
		ret = self.grStateMachine.HandleGetState()
		print_noti("[WsConn] new connection connected - %s" % ret)
		if ret == "done-wake-word" or ret == "stream-cmd":
			self.wavFileWriter.OpenToWrite()

	def handleClose(self):
		nlpServiceInst = NLPService()
		self.wavFileWriter.Close()
		self.grStateMachine.HandleWsClosed(nlpServiceInst, self.wavFileWriter)
		ret = self.grStateMachine.HandleGetState()
		print_noti("[WsConn] connection closed - %s" % ret)

@APP.route('/', methods=['GET'])
def HTTPServeGetStatus():
	# Get request parameters
	# req = request.get_json(silent=True, force=True)
	# action = req.get('result').get('action')
	grStateMachine = GrPeachStateMachine()
	ret = grStateMachine.HandleGetState()
	print_noti("[HTTP-GET] STATUS - %s" % ret)

	res = {'action': ret}

	return make_response(jsonify(res))

@APP.route('/status/update', methods=['POST'])
def HTTPServeUpdateDeviceStatus():
	req = request.get_json(silent=True, force=True)
	print json.dumps(req, indent=4, sort_keys=True)
	res = {'status': 'ok'}
	return make_response(jsonify(res))

@APP.route('/action')
def HTTPServeGetAction():
	res = {'action': ''}
	return make_response(jsonify(res))

@APP.route('/audio')
def HTTPServeAudio():
	try:
		grStateMachine = GrPeachStateMachine()
		grStateMachine.HandleDownload()
		return flask.send_file('./file44100.mp3', attachment_filename='play.mp3')
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
	snowboydecoder.AddChainCallback(snowboydecoder.play_audio_file)
	detector = snowboydecoder.HotwordDetector(	"./snowboy.umdl",
												sensitivity=1,
												enableGrPeach=True,
												audioCommObject=commObject)
	print('Snowboy started')
	detector.start( detected_callback=snowboydecoder.CallbackChains,
					interrupt_check=interrupt_callback,
					sleep_time=0.03)
	detector.terminate()

class NLPService():
	__metaclass__ = Singleton
	grStateMachine = GrPeachStateMachine()
	eventEnable = threading.Event()
	eventEnable.clear()
	speechFile = ""

	def SetRun(self, speechFile):
		self.speechFile = speechFile
		self.eventEnable.set()

	def GetRun(self):
		self.eventEnable.wait()
		self.eventEnable.clear()
		return self.speechFile

	def run(self):
		print_noti("[NLPService] Started")
		while True:
			speechFile = self.GetRun()
			print_noti("[NLPService] Triggered")
			text_cmd = SpeechToText(speechFile)
			text_resp = RequestDialogflow(text_cmd)
			self.grStateMachine.SetState(STATE_PLAYING)
			TextToSpeech(text_resp)
			results = {'state': "play-audio"}
			self.grStateMachine.SetNLPOutCome(results)

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

	nlpServiceInst = NLPService()
	nlpService = threading.Thread(target=nlpServiceInst.run)
	nlpService.start()
	wsServer = threading.Thread(target=RunWsServer)
	wsServer.start()
	snowBoyRunner = threading.Thread(target=RunSnowboy)
	snowBoyRunner.start()
	RunFlaskServer()

if __name__ == "__main__":
	main()
