import sys, os
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
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
from server_config import globalConfig
from server_objects import *
def get_git_root():
	CURRENT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) + os.sep
	path = CURRENT_DIR
	git_repo = git.Repo(path, search_parent_directories=True)
	git_root = git_repo.git.rev_parse("--show-toplevel")
	return git_root
sys.path.insert(0, get_git_root() + '/test_bluefinserial/bluefinserial')
from utils import *

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

def AudioDualToMono(in_data):
	new_data = bytearray()
	for idx, data in enumerate(in_data):
		if idx % 2 == 1:
			new_data.append(data)
	return str(new_data)

def SpeechToText(speech_file):
	"""Transcribe the given audio file."""
	if globalConfig["TestV1"] == True:
		return
	from google.cloud import speech
	from google.cloud.speech import enums
	from google.cloud.speech import types
	print_noti("[SpeechToText] Entry")
	if globalConfig["ByPassSTT"] == True:
		ret = globalConfig["STT_BYPASS_MSG"]
		print_noti("[SpeechToText] Bypass %s" % ret)
		return ret
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
	return ret
	# [END migration_sync_response]
# [END def_transcribe_file]

def TextToSpeech(textIn):
	if globalConfig["TestV1"] == True:
		return
	from gtts import gTTS
	print_noti("[TextToSpeech] Entry")
	if globalConfig["ByPassTTS"] == True:
		print_noti("[TextToSpeech] Bypass")
		return
	if textIn == "" or textIn is None:
		textIn = "Sorry, I can't hear that"
	print "[TextToSpeech] %s" % (textIn)
	tts = gTTS(text=textIn, lang='en-us')
	tts.save("file.mp3")
	os.system("ffmpeg -y -i file.mp3 -ar 44100 -ac 2 file44100.mp3 >/dev/null 2>&1")
	print_noti("[TextToSpeech] End")

def RequestDialogflow(speechIn):
	if globalConfig["TestV1"] == True:
		return
	if speechIn == "":
		return None
	def isFromWebhook(object):
		if len(obj["result"]["metadata"]) == 0:
			return False
		return True
	request = dialogFlowAgent.text_request()
	request.lang = 'en'  # optional, default value equal 'en'
	request.session_id = "some_unique_id"
	request.query = speechIn
	response = request.getresponse()
	response_text = response.read()
	obj = json.loads(response_text)
	print "[RequestDialogflow]", json.dumps(obj, indent=4, sort_keys=True)
	return obj["result"]["fulfillment"]["messages"][0]["speech"]

def DoAction(obj, state_machine):
	if globalConfig["TestV1"] == True:
		return
	if obj == None:
		print_err("[DoAction] obj is None")
		return "Sorry, I can't here it"

	device = ''
	# intent = obj["body"]["result"]["metadata"]["intentName"]
	# state_machine.SetState(STATE_JSON_ACTION)

	response_text = obj["result"]["fulfillment"]["speech"]
	print ("[Response-Text]: %s%s%s" % (bcolors.OKGREEN + bcolors.BOLD, response_text, bcolors.ENDC))
	return response_text
