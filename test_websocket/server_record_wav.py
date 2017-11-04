import sys
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import alsaaudio
import wave

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

class WavFileWriter(object):
	__metaclass__ = Singleton
	fileCount = 0
	fileName = 'record%d.wav' % fileCount
	record_output = wave.open(fileName, 'w')
	record_output.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))
	audio_data = bytearray()

	def ExtendData(self, data):
		self.audio_data.extend(data)

	def OpenToWrite(self):
		if self.record_output != None:
			self.Close()
		self.fileName = 'record%d.wav' % self.fileCount
		print("Open file %s to write" % self.fileName)
		self.record_output = wave.open(self.fileName, 'w')
		self.record_output.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))

	def Close(self):
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
		print self.wavFileWriter

	def handleMessage(self):
		# echo message back to client
		# self.sendMessage(self.data)
		sys.stdout.write('.')
		sys.stdout.flush()
		self.wavFileWriter.ExtendData(self.data)

	def handleConnected(self):
		print(self.address, 'connected')
		self.wavFileWriter.OpenToWrite()

	def handleClose(self):
		print(self.address, 'closed')
		self.wavFileWriter.Close()

server = SimpleWebSocketServer('', 9003, SimpleEcho)
print ("Starting ws server at port 9003")
server.serveforever()
