import snowboydecoder
import sys
import signal
from server_record_wav import *
from threading import Thread

interrupted = False
def signal_handler(signal, frame):
	global interrupted
	interrupted = True

def interrupt_callback():
	global interrupted
	return interrupted

if len(sys.argv) == 1:
	print("Error: need to specify model name")
	print("Usage: python demo.py your.model")
	sys.exit(-1)

model = sys.argv[1]

# capture SIGINT signal, e.g., Ctrl+C
signal.signal(signal.SIGINT, signal_handler)


def start_ws_server():
	server = SimpleWebSocketServer('', 9003, SimpleEcho)
	print ("Starting ws server at port 9003")
	server.serveforever()
thread = Thread(target = start_ws_server)
thread.start()
commObject = AudioProducer()
snowboydecoder.AddChainCallback(commObject.WakeWordCallBack)

detector = snowboydecoder.HotwordDetector(	model,
											sensitivity=1,
											enableGrPeach=True,
											audioCommObject=commObject)
print('Listening... Press Ctrl+C to exit')

# main loop
detector.start(detected_callback=snowboydecoder.play_audio_file,
			   interrupt_check=interrupt_callback,
			   sleep_time=0.03)

detector.terminate()
