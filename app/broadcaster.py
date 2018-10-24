from datetime import datetime, timedelta
import queue
import threading
import logging
import requests
import re
import time
import base64
from .status import Status
import json

class HTTPBasicThenDigestAuth(requests.auth.HTTPDigestAuth):
    """Try HTTPBasicAuth, then HTTPDigestAuth."""

    def __init__(self):
        super(HTTPBasicThenDigestAuth, self).__init__(None, None)

    def __call__(self, r):
        # Extract auth from URL
        self.username, self.password = requests.utils.get_auth_from_url(r.url)

        # Prepare basic auth
        r = requests.auth.HTTPBasicAuth(self.username, self.password).__call__(r)

        # Let HTTPDigestAuth handle the 401
        return super(HTTPBasicThenDigestAuth, self).__call__(r)

class Broadcaster:
    """Handles relaying the source MJPEG stream to connected clients"""

    _instance = None

    def __init__(self, url):
        self.url = url

        self.clients = []

        self.status = Status._instance

        self.kill = False
        self.broadcastThread = threading.Thread(target = self.streamFromSource)
        self.broadcastThread.daemon = True

        self.lastFrame = b""
        self.lastFrameBuffer = b""

        self.connected = False
        self.broadcasting = False

        try:
            feedLostFile = open("app/resources/feedlost.jpeg", "rb") #read-only, binary
            feedLostImage = feedLostFile.read()
            feedLostFile.close()

            self.feedLostFrame =     "Content-Type: image/jpeg\r\n"\
                                    "Content-Length: {}\r\n\r\n"\
                                    "{}".format(len(feedLostImage), feedLostImage).encode("utf-8")
        except IOError as e:
            logging.warning("Unable to read feedlost.jpeg: {}".format(e))
            self.feedLostFrame = False

        Broadcaster._instance = self

    def start(self):
        if (self.connectToStream()):
            self.broadcasting = True
            logging.info("Connected to stream source, boundary separator: {}".format(self.boundarySeparator))
            self.broadcastThread.start()

    #
    # Connects to the stream source
    #
    def connectToStream(self):
        try:
            self.sourceStream = requests.get(self.url, stream = True, timeout = 10, auth = HTTPBasicThenDigestAuth())
        except Exception as e:
            logging.error("Error: Unable to connect to stream source at {}: {}".format(self.url, e))
            return False

        self.boundarySeparator = self.parseStreamHeader(self.sourceStream.headers['Content-Type']).encode("utf-8")

        if (not self.boundarySeparator):
            logging.error("Unable to find boundary separator in the header returned from the stream source")
            return False

        self.connected = True
        return True

    #
    # Parses the stream header and returns the boundary separator
    #
    def parseStreamHeader(self, header):
        if (not isinstance(header, str)):
            return None

        match = re.search(r'boundary=(.*)', header, re.IGNORECASE)
        try:
            boundary = match.group(1)
            if not boundary.startswith("--"):
                boundary = "--" + boundary
            return boundary
        except:
            logging.error("Unexpected header returned from stream source: unable to parse boundary")
            logging.error(header)
            return None

    #
    # Returns the total number of connected clients
    #
    def getClientCount(self):
        return len(self.clients)

    def updateClients(self, inv):
        invoice = json.loads(inv)
        logging.info(invoice)
        for client in self.clients:
            if client.r_hash == invoice["r_hash"]:
                client.paid = invoice["settled"]
                client.timeConnected = datetime.now()

    #
    # Process data in frame buffer, extract frames when present
    #
    def extractFrames(self, frameBuffer):
        if (frameBuffer.count(self.boundarySeparator) >= 2):
            #calculate the start and end points of the frame
            start = frameBuffer.find(self.boundarySeparator)
            end = frameBuffer.find(self.boundarySeparator, start + 1)

            #extract frame data
            frameStart = frameBuffer.find(b"\r\n\r\n", start) + len(b"\r\n\r\n")
            frame = frameBuffer[frameStart:end]

            #process for WebSocket clients
            webSocketFrame = base64.b64encode(frame)

            return (webSocketFrame, frame, end)
        else:
            return (None, None, 0)

    #
    # Broadcast data to a list of StreamingClients
    #
    def broadcastToStreamingClients(self, clients, data):
        for client in self.clients:
            if (not client.connected):
                clients.remove(client)
                logging.info("Client left. Client count: {}".format(self.getClientCount()))
            if client.paid: 
                if datetime.now() - client.timeConnected > timedelta(seconds=60):
                    logging.info("time's up! disconnect")
                    client.kill = True 
                else:
                    logging.info("Client paid")
                    client.bufferStreamData(data)

    #
    # Broadcast data to all connected clients
    #
    def broadcast(self, data):
        self.lastFrameBuffer += data
        webSocketFrame, frame, bufferProcessedTo = self.extractFrames(self.lastFrameBuffer)
        if (webSocketFrame and frame):
            #delete the frame now that it has been extracted, keep what remains in the buffer
            self.lastFrameBuffer = self.lastFrameBuffer[bufferProcessedTo:]

            #save for /snapshot requests
            self.lastFrame = frame

            #serve to websocket clients
            self.broadcastToStreamingClients(self.clients, webSocketFrame)

    #
    # Thread to handle reading the source of the stream and rebroadcasting
    #
    def streamFromSource(self):
        while True:
            try:
                for data in self.sourceStream.iter_content(1024):
                    if self.kill:
                        for client in self.clients:
                            client.kill = True
                        return
                    self.broadcast(data)
                    self.status.addToBytesIn(len(data))
                    self.status.addToBytesOut(len(data)*self.getClientCount())
            except Exception as e:
                logging.error("Lost connection to the stream source: {}".format(e))
            finally:
                #flush the frame buffer to avoid conflicting with future frame data
                self.lastFrameBuffer = b""
                self.connected = False
                while (not self.connected):
                    if (self.feedLostFrame):
                        data = self.boundarySeparator + b"\r\n" + self.feedLostFrame + b"\r\n"
                        self.broadcast(data)
                    time.sleep(5)
                    self.connectToStream()