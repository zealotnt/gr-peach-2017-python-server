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
def get_git_root():
	CURRENT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) + os.sep
	path = CURRENT_DIR
	git_repo = git.Repo(path, search_parent_directories=True)
	git_root = git_repo.git.rev_parse("--show-toplevel")
	return git_root
sys.path.insert(0, get_git_root() + '/test_bluefinserial/bluefinserial')
from utils import *


globalConfig = {
	"PcmPlayer": False,
	"WavFileWriter": False,
	"TestV1": False,			# WW 5 ws-stream, CMD 5 ws-stream, play-audio
	"ByPassSTT": True,			# By pass STT
	"ByPassTTS": True,			# By pass TTS
	"STT_BYPASS_MSG": "Is there any new device ?",
}

STATE_IDLE=0
STATE_WW_DONE=1
STATE_RCV_CMD=2
STATE_PREPARE_PLAYING=3
STATE_ANALYZING=4
STATE_PLAYING=5
STATE_JSON_ACTION=6
STATE_PLAYDONE=7

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path, verbose=True)
APP = Flask(__name__)
LOG = APP.logger
interrupted = False
CLIENT_ACCESS_TOKEN = os.environ.get('CLIENT_ACCESS_TOKEN')
dialogFlowAgent = apiai.ApiAI(CLIENT_ACCESS_TOKEN)
