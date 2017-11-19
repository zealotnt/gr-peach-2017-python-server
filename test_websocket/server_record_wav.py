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
def get_git_root():
	CURRENT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) + os.sep
	path = CURRENT_DIR
	git_repo = git.Repo(path, search_parent_directories=True)
	git_root = git_repo.git.rev_parse("--show-toplevel")
	return git_root
sys.path.insert(0, get_git_root() + '/test_bluefinserial/bluefinserial')
from utils import *

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path, verbose=True)
globalConfig = {
	"PcmPlayer": False,
	"WavFileWriter": False,
}
APP = Flask(__name__)
LOG = APP.logger
interrupted = False
CLIENT_ACCESS_TOKEN = os.environ.get('CLIENT_ACCESS_TOKEN')
dialogFlowAgent = apiai.ApiAI(CLIENT_ACCESS_TOKEN)

def signal_handler(signal, frame):
	global interrupted
	interrupted = True

def interrupt_callback():
	global interrupted
	return interrupted
# capture SIGINT signal, e.g., Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

class bcolors:
	HEADER = '\033[95m'
	OKBLUE = '\033[94m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'

def dump_hex(data, desc_str="", token=":", prefix="", preFormat=""):
	to_write = desc_str + token.join(prefix+"{:02x}".format(ord(c)) for c in data) + "\r\n"
	sys.stdout.write(to_write)

def DoHash(binary_data):
	hashEngine = hashes.Hash(hashes.SHA1(), backend=default_backend())
	hashEngine.update(binary_data)
	return hashEngine.finalize()

def AudioDualToMono(in_data):
	new_data = bytearray()
	for idx, data in enumerate(in_data):
		if idx % 2 == 1:
			new_data.append(data)
	return str(new_data)

def SpeechToText(speech_file):
    """Transcribe the given audio file."""
    from google.cloud import speech
    from google.cloud.speech import enums
    from google.cloud.speech import types
    print_noti("[SpeechToText] Entry")
    client = speech.SpeechClient()

    # [START migration_sync_request]
    # [START migration_audio_config_file]
    with io.open(speech_file, 'rb') as audio_file:
        content = audio_file.read()

    audio = types.RecognitionAudio(content=content)
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code='en-US')
    # [END migration_audio_config_file]

    # [START migration_sync_response]
    response = client.recognize(config, audio)
    # [END migration_sync_request]
    # Print the first alternative of all the consecutive results.
    for idx, result in enumerate(response.results):
        print('[Transcript] %d %s%s%s' % (idx, bcolors.OKGREEN + bcolors.BOLD, result.alternatives[0].transcript, bcolors.ENDC))
    print_noti("[SpeechToText] End")
    if len(response.results) == 0:
    	print_err("[SpeechToText] No speech result")
    	return ""
    ret = response.results[0].alternatives[0].transcript
    print('[Transcript] Result: %s%s%s' % (bcolors.OKGREEN + bcolors.BOLD, ret, bcolors.ENDC))
    return response.results[0].alternatives[0].transcript
    # [END migration_sync_response]
# [END def_transcribe_file]

def TextToSpeech(textIn):
	from gtts import gTTS
	print_noti("[TextToSpeech] Entry")
	print "[TextToSpeech] %s" % (textIn)
	tts = gTTS(text=textIn, lang='en-us')
	tts.save("file.mp3")
	os.system("ffmpeg -y -i file.mp3 -ar 44100 -ac 2 file44100.mp3 >/dev/null 2>&1")
	print_noti("[TextToSpeech] End")

def RequestDialogflow(speechIn):
	request = dialogFlowAgent.text_request()
	request.lang = 'en'  # optional, default value equal 'en'
	request.session_id = "some_unique_id"
	request.query = speechIn
	response = request.getresponse()
	response_text = response.read()
	obj = json.loads(response_text)
	return obj

def DoAction(obj):
	device = ''
	# intent = obj["body"]["result"]["metadata"]["intentName"]

	response_text = obj["result"]["fulfillment"]["speech"]
	print ("[Response-Text]: %s%s%s" % (bcolors.OKGREEN + bcolors.BOLD, response_text, bcolors.ENDC))
	return response_text

class Singleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		if cls not in cls._instances:
			cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
		return cls._instances[cls]

class GrPeachStateMachine(object):
	__metaclass__ = Singleton
	DoneWw = False
	RcvVoiceCmd = False
	DoneStream = False
	stateChangeMux = threading.Lock()
	Count = 0
	SpeechRequest = ""

	def HandleWakeWordCallback(self):
		self.DoneWw = True

	def HandleWsMessage(self):
		"""
		if return True
		the ws-msg-handler should close the socket
		"""
		self.stateChangeMux.acquire()
		if self.DoneWw == True and self.RcvVoiceCmd == False:
			print_noti("Close cause snowboy")
			self.Count = 0
			self.RcvVoiceCmd = True
			self.stateChangeMux.release()
			return True
		if self.DoneWw == True and self.RcvVoiceCmd == True:
			self.Count += 1
		# if DoneWw == True and RcvVoiceCmd == True:
		# 	Count += 1
		# 	if Count > 20:
		# 		Count = 0
		# 		print("Close cause end command")
		# 		DoneWw = False
		# 		RcvVoiceCmd = False
		# 		DoneStream = True
		# 		self.close()
		# 		return
		self.stateChangeMux.release()
		return False


	def HandleWsClosed(self, wavFile):
		self.stateChangeMux.acquire()
		if self.DoneWw == True and self.RcvVoiceCmd == True and self.Count != 0:
			print_noti("Close cause end command")
			self.DoneWw = False
			self.RcvVoiceCmd = False
			self.DoneStream = True
			self.Count = 0
			self.SpeechRequest = SpeechToText(wavFile)
		self.stateChangeMux.release()

	def HandleGetState(self):
		self.stateChangeMux.acquire()
		ret = "idle"
		if self.DoneWw == True:
			ret = 'done-wake-word'
		if self.DoneWw == True and self.RcvVoiceCmd == True:
			ret = 'stream-cmd'
		if self.DoneStream == True:
			ret = 'play-audio'
			self.DoneStream = False
			self.DoneWw = False
			self.RcvVoiceCmd = False
			req_obj = RequestDialogflow(self.SpeechRequest)
			self.VoiceResp = DoAction(req_obj)
			TextToSpeech(self.VoiceResp)
		self.stateChangeMux.release()
		return ret

	def GetVoiceResponse(self):
		self.stateChangeMux.acquire()
		ret = self.SpeechRequest
		self.stateChangeMux.release()
		return ret

class PcmPlayer(object):
	__metaclass__ = Singleton
	global globalConfig
	sound_out = alsaaudio.PCM()  # open default sound output
	sound_out.setchannels(1)  # use only one channel of audio (aka mono)
	sound_out.setrate(16000)  # how many samples per second
	sound_out.setformat(alsaaudio.PCM_FORMAT_S16_LE)  # sample format
	sound_out.setperiodsize(4)

	def WriteAudio(self, data):
		if not globalConfig['PcmPlayer']:
			return
		data = str(data)
		self.sound_out.write(data)

class SpeechToTextProducer(object):
	"""Opens a recording stream as a generator yielding the audio chunks."""
	# Please make sure the audio format is
	# + 16000 KHz
	# + feed 1600 sample <=> 3200bytes <=> 100ms at a time (chunk)
	# + only 1 channel (need to be trimmed down)
	# + Create a thread-safe buffer of audio data
	__metaclass__ = Singleton
	_buff = queue.Queue()
	closed = False

	def StopStreaming(self):
		self.closed = True
		# Signal the generator to terminate so that the client's
		# streaming_recognize method will not block the process termination.
		self._buff.put(None)

	def Fill_buffer(self, in_data):
		"""Continuously collect data from the audio stream, into the buffer."""
		# in_data = AudioDualToMono(in_data)
		in_data = str(in_data)
		self._buff.put(in_data)

	def generator(self):
		while not self.closed:
			# Use a blocking get() to ensure there's at least one chunk of
			# data, and stop iteration if the chunk is None, indicating the
			# end of the audio stream.
			chunk = self._buff.get()
			if chunk is None:
				return
			data = [chunk]

			# Now consume whatever other data's still buffered.
			while True:
				try:
					chunk = self._buff.get(block=False)
					if chunk is None:
						return
					data.append(chunk)
				except queue.Empty:
					break
			yield b''.join(data)
# [END stream-code]

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
		# return AudioDualToMono(in_data)
		return in_data

	def WakeWordCallBack(self, *arg):
		# This callback will be called when snowboy detect the wakeword
		grStateMachine = GrPeachStateMachine()
		grStateMachine.HandleWakeWordCallback()
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
		if self.record_output == None:
			return
		self.audio_data.extend(data)

	def OpenToWrite(self):
		if not globalConfig['WavFileWriter']:
			return
		if self.record_output != None:
			self.Close()
		self.fileName = 'record%d.wav' % self.fileCount
		print_noti("[WavWriter] Open file %s to write" % self.fileName)
		self.record_output = wave.open(self.fileName, 'w')
		self.record_output.setparams((  1,						# nchannels
										2,						# sampwidth
										16000,					# framerate
										0,						# nframes
										'NONE',					# comptype
										'not compressed'))		# compname

	def Close(self):
		if not globalConfig['WavFileWriter']:
			return
		if self.record_output == None:
			return
		print_noti("[WavWriter] Record len: %d" % len(self.audio_data))
		self.record_output.writeframes(self.audio_data)
		self.record_output.close()
		self.record_output = None
		self.audio_data = bytearray()
		self.fileCount += 1

	def GetLastFile(self):
		if self.fileCount == 0:
			return ""
		return 'record%d.wav' % (self.fileCount - 1)

class SimpleEcho(WebSocket):
	def __init__(self, *args, **kwargs):
		super(SimpleEcho, self).__init__( *args, **kwargs)
		self.wavFileWriter = WavFileWriter()
		self.pcmPlayer = PcmPlayer()
		self.comm = AudioProducer()
		self.sttStreamer = SpeechToTextProducer()
		self.grStateMachine = GrPeachStateMachine()

	def handleMessage(self):
		# echo message back to client
		# self.sendMessage(self.data)
		self.data = AudioDualToMono(self.data)
		if self.grStateMachine.HandleWsMessage() == True:
			self.close()
			return

		sys.stdout.write('.')
		sys.stdout.flush()
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
		ret = self.grStateMachine.HandleGetState()
		print_noti("[WsConn] connection closed - %s" % ret)
		self.wavFileWriter.Close()
		self.grStateMachine.HandleWsClosed(self.wavFileWriter.GetLastFile())

@APP.route('/', methods=['GET'])
def webhook():
	# Get request parameters
	# req = request.get_json(silent=True, force=True)
	# action = req.get('result').get('action')
	grStateMachine = GrPeachStateMachine()
	ret = grStateMachine.HandleGetState()
	res = {'action': ret}

	return make_response(jsonify(res))

@APP.route('/audio')
def file_downloads():
	try:
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
