import sys, os
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import alsaaudio
import wave
from optparse import OptionParser, OptionGroup

globalConfig = {
	"PcmPlayer": False,
	"WavFileWriter": False,
}

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
	sound_out.setrate(44100)  # how many samples per second
	sound_out.setformat(alsaaudio.PCM_FORMAT_S16_LE)  # sample format

	def WriteAudio(self, data):
		if not globalConfig['PcmPlayer']:
			return
		data = str(data)
		self.sound_out.write(data)

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
		self.record_output.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))

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

	def handleMessage(self):
		# echo message back to client
		# self.sendMessage(self.data)
		sys.stdout.write('.')
		sys.stdout.flush()
		self.wavFileWriter.ExtendData(self.data)
		self.pcmPlayer.WriteAudio(self.data)

	def handleConnected(self):
		print(self.address, 'connected')
		self.wavFileWriter.OpenToWrite()

	def handleClose(self):
		print(self.address, 'closed')
		self.wavFileWriter.Close()

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

	server = SimpleWebSocketServer('', 9003, SimpleEcho)
	print ("Starting ws server at port 9003")
	server.serveforever()

if __name__ == "__main__":
	main()
