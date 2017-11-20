#!/usr/bin/env python
# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This is a sample for a translation fulfillment webhook for an API.AI agent

This is meant to be used with the sample translate agent for API.AI, it uses
the Google Cloud Translation API and requires an API key from an API project
with the Google Cloud Translation API enabled.
"""

import json
import random
from httplib import HTTPException
from urllib2 import HTTPError, URLError

import flask
from flask import Flask, jsonify, make_response, request

APP = Flask(__name__)
LOG = APP.logger

@APP.route('/dialogflow-webhook', methods=['POST'])
def webhook():
	# Get request parameters
	req = request.get_json(silent=True, force=True)
	print json.dumps(req, indent=4, sort_keys=True)

	intent = req["result"]["metadata"]["intentName"]

	statement = "intent: "
	device = ''
	numDevice = 1
	status = ''

	if intent == "Conversion.device.add":
		output = "There is %d new device. Do you want to name it? \n" % numDevice
	elif intent == "Conversion.device.add - yes - nameing - yes":
		device = req["result"]["contexts"][0]["parameters"]['Device']
		output = "Awesome, I added " + device + " to our network.\n"
	elif intent == "smarthome.device.switch.check":
		device = req["result"]["parameters"]['Device']
		status = "turn on"
		output = "The " + device + " was " + status
	elif intent == "smarthome.device.switch.off":
		device = req["result"]["parameters"]['Device']
		output = "The " + device + " currently was turn off"
	elif intent == "smarthome.device.switch.on":
		device = req["result"]["parameters"]['Device']
		output = "The " + device + " currently was turn on"
	else:
		output = "error"
	res = {'speech': output, 'displayText': output}

	return make_response(jsonify(res))

import httplib
def GetRequest(ip, ep):
	conn = httplib.HTTPConnection(ip)
	conn.request("GET", ep)
	resp = conn.getresponse()
	data = resp.read()
	print resp.status, resp.reason
	print data
	conn.close()
	# resp_obj = json.loads(data)
	# return resp_obj
	return

def PostRequest(ip, ep, body):
	import httplib, urllib
	params = urllib.urlencode({'spam': 1, 'eggs': 2, 'bacon': 0})
	headers = {	"Content-type": "application/x-www-form-urlencoded",
				"Accept": "text/plain"}
	conn = httplib.HTTPConnection("musi-cal.mojam.com:80")
	conn.request("POST", "/cgi-bin/query", params, headers)
	response = conn.getresponse()
	print response.status, response.reason
	data = response.read()
	conn.close()

if __name__ == '__main__':
	PORT = 8000
	APP.run(
		debug=True,
		port=PORT,
		host='0.0.0.0'
	)
	# GetRequest("192.168.1.177", "/")
	# PostRequest("", "", "")
	# pass
