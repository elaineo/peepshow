from datetime import datetime, timedelta
import sys
import queue
import socket
import threading
import logging
from .broadcaster import Broadcaster
from .SimpleWebSocketServer import WebSocket


class StreamingClient(object):

	def __init__(self):
		self.streamBuffer = b""
		self.streamQueue = queue.Queue()
		self.streamThread = threading.Thread(target = self.stream)
		self.streamThread.daemon = True
		self.connected = True
		self.kill = False
		self.timeConnected = None
		self.r_hash = None
		self.paid = False
		super(StreamingClient, self).__init__()

	def start(self):
		self.streamThread.start()

	def transmit(self, data):
		return len(data)

	def stop(self):
		pass

	def bufferStreamData(self, data):
		#use a thread-safe queue to ensure stream buffer is not modified while we're sending it
		self.streamQueue.put(data)

	def stream(self):
		while self.connected:
			#this call blocks if there's no data in the queue, avoiding the need for busy-waiting
			self.streamBuffer += self.streamQueue.get()

			#check if kill or connected state has changed after being blocked
			if (self.kill or not self.connected):
				self.stop()
				return

			while (len(self.streamBuffer) > 0):
				streamedTo = self.transmit(self.streamBuffer)
				if (streamedTo and streamedTo >= 0):
					self.streamBuffer = self.streamBuffer[streamedTo:]
				else:
					self.streamBuffer = b""

class WebSocketStreamingClient(WebSocket, StreamingClient):
	def __init__(self, client, server):
		logging.info(client)
		super(WebSocketStreamingClient, self).__init__(server, client["handler"], client["address"])
		self.r_hash = client["r_hash"]
		self.handleConnected()

	def stop(self):
		pass

	def transmit(self, data):
		self.sendMessage("data:image/jpg;base64," + data.decode("utf-8"))
		return len(data)

	def handleConnected(self):
		self.start()
		Broadcaster._instance.clients.append(self)

	def handleClose(self):
		self.connected = False
