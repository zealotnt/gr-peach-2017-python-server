import sys, os
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
# import alsaaudio
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


class Singleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		if cls not in cls._instances:
			cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
		return cls._instances[cls]

# class PcmPlayer(object):
# 	__metaclass__ = Singleton
# 	global globalConfig
# 	sound_out = alsaaudio.PCM()  # open default sound output
# 	sound_out.setchannels(1)  # use only one channel of audio (aka mono)
# 	sound_out.setrate(16000)  # how many samples per second
# 	sound_out.setformat(alsaaudio.PCM_FORMAT_S16_LE)  # sample format
# 	sound_out.setperiodsize(4)

# 	def WriteAudio(self, data):
# 		if not globalConfig['PcmPlayer']:
# 			return
# 		data = str(data)
# 		self.sound_out.write(data)

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

class GrPeachStateMachine(object):
	__metaclass__ = Singleton
	DoneWw = False
	RcvVoiceCmd = False
	DoneStream = False
	stateChangeMux = threading.Lock()
	eventWaitOutcome = threading.Event()
	eventWaitOutcome.clear()
	outcomeResult = []
	grAction = []
	Count = 0
	SpeechRequest = ""
	State = STATE_IDLE
	LastState = STATE_IDLE

	def HandleWakeWordCallback(self):
		self.SetState(STATE_WW_DONE)

	def HandleWsMessage(self):
		"""
		if return True
		the ws-msg-handler should close the socket
		"""
		self.stateChangeMux.acquire()

		if globalConfig["TestV1"] == True:
			self.Count += 1
			if self.State == STATE_IDLE:
				if self.Count > 1:
					self.Count = 0
					print("Closing 1")
					self.SetState(STATE_RCV_CMD)
					self.stateChangeMux.release()
					return True
			elif self.State == STATE_WW_DONE or self.State == STATE_RCV_CMD:
				if self.Count > 1:
					self.Count = 0
					self.SetState(STATE_PREPARE_PLAYING)
					print("Closing 2")
					self.stateChangeMux.release()
					return True
		else:
			if self.State == STATE_WW_DONE:
				print_noti("Close cause snowboy")
				self.Count = 0
				self.SetState(STATE_RCV_CMD)
				self.stateChangeMux.release()
				return True
			elif self.State == STATE_RCV_CMD:
				self.Count += 1

		self.stateChangeMux.release()
		return False


	def HandleWsClosed(self, nlpServiceInst, wavWriterInst):
		self.stateChangeMux.acquire()
		if self.State == STATE_RCV_CMD and self.Count > 0:
			print_noti("Close cause end command")
			self.Count = 0
			self.SetState(STATE_PREPARE_PLAYING)
			nlpServiceInst.SetRun(wavWriterInst.GetLastFile())
		self.stateChangeMux.release()

	def HandleGetState(self):
		print_noti("In HandleGetState")
		self.stateChangeMux.acquire()
		ret = "idle"
		todo = {}
		if self.State == STATE_WW_DONE:
			ret = 'done-wake-word'
		elif self.State == STATE_RCV_CMD:
			ret = 'stream-cmd'
		elif self.State == STATE_PREPARE_PLAYING:
			ret = 'prepare-playing'
			self.SetState(STATE_ANALYZING)
		elif self.State == STATE_ANALYZING:
			outcomeObj = self.WaitNLPOutcome()
			print("xong nv 2")
			ret = outcomeObj["state"]
			if "todo" in outcomeObj:
				todo = outcomeObj["todo"]
		elif self.State == STATE_PLAYING:
			ret = 'play-audio'

		resp = {"command": ret}
		for key, value in todo.iteritems():
			resp[key] = value
		self.stateChangeMux.release()
		print resp
		return resp

	def HandleDownload(self):
		self.SetState(STATE_IDLE)

	def SetState(self, state):
		self.LastState = self.State
		self.State = state

	def GetLastState(self):
		return self.LastState

	def WaitNLPOutcome(self):
		self.eventWaitOutcome.wait()
		self.eventWaitOutcome.clear()
		return self.outcomeResult

	def SetNLPOutCome(self, result):
		self.outcomeResult = result
		self.eventWaitOutcome.set()

	def WaitGrAction(self):
		self.eventWaitGrAction.wait()
		self.eventWaitGrAction.clear()
		return self.grAction

	def SetGrAction(self, result):
		self.grAction = result
		self.eventWaitGrAction.set()
