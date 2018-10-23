import socket
import threading
import logging
import re
import json
from .status import Status
from .broadcaster import Broadcaster
from .lightning import LndWrapper

class HTTPRequestHandler:
	"""Handles the initial connection with HTTP clients"""

	def __init__(self, port, lightning):
		#response we'll send to the client, pretending to be from the real stream source
		dummyHeaderfh = open('app/resources/dummy.header', 'r')
		self.dummyHeader = dummyHeaderfh.read()

		htmlfh = open('app/web/status.html', 'r')
		self.statusHTML = htmlfh.read()

		self.indexHTML = open('app/web/index.html', 'r').read()

		self.acceptsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.acceptsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.acceptsock.bind(("0.0.0.0", port))
		self.acceptsock.listen(10)

		self.broadcast = Broadcaster._instance
		self.status = Status._instance
		self.lnrpc = lightning

		self.kill = False

		self.acceptThread = threading.Thread(target = self.acceptClients)
		self.acceptThread.daemon = True

	def start(self):
		self.acceptThread.start()

	#
	# Thread to process client requests
	#
	def handleRequest(self, clientsock):
		buff = b""
		while True:
			try:
				data = clientsock.recv(64)
				if (data == b""):
					break

				buff += data

				if b"\r\n\r\n" in buff or b"\n\n" in buff:
					break #as soon as the header is sent - we only care about GET requests

			except Exception as e:
				logging.info(e)
				break

		if (buff != b""):
			try:
				match = re.search(r'GET (.*) ', buff.decode("utf-8"))

				requestPath = match.group(1)
			except Exception as e:
				logging.info("Client sent unexpected request: {}".format(buff))
				return

			if ("/status" in requestPath):
				clientsock.sendall(b'HTTP/1.0 200 OK\r\nContentType: text/html\r\n\r\n')
				clientsock.sendall(self.statusHTML.format(clientcount = self.broadcast.getClientCount(), bwin = float(self.status.bandwidthIn*8)/1000000, bwout = float(self.status.bandwidthOut*8)/1000000).encode("utf-8"))
				clientsock.close()
			elif ("/invoice" in requestPath):
				clientsock.sendall(b'HTTP/1.0 200 OK\r\nContentType: application/json; charset=utf-8\r\n\r\n')
				invoice = self.lnrpc.get_invoice()
				logging.info(invoice)
				clientsock.sendall(json.dumps(invoice).encode("utf-8"))
				clientsock.close()					
			elif ("/snapshot" in requestPath):
				clientsock.sendall('HTTP/1.0 200 OK\r\n')
				clientsock.sendall('Content-Type: image/jpeg\r\n')
				clientsock.sendall('Content-Length: {}\r\n\r\n'.format(len(self.broadcast.lastFrame)))
				clientsock.sendall(self.broadcast.lastFrame)
				clientsock.close()
			else:
				clientsock.sendall(b'HTTP/1.0 200 OK\r\nContentType: text/html\r\n\r\n')
				clientsock.sendall(self.indexHTML.encode("utf-8"))
				clientsock.close()
		else:
			logging.info("Client connected but didn't make a request")

	#
	# Thread to handle connecting clients
	#
	def acceptClients(self):
		while True:
			clientsock, addr = self.acceptsock.accept()

			if self.kill:
				clientsock.close()
				return
			handlethread = threading.Thread(target = self.handleRequest, args = (clientsock,))
			handlethread.start()