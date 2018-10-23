import logging, threading
from datetime import datetime
import sys
sys.path.insert(0, 'googleapis')

import rpc_pb2 as ln
import rpc_pb2_grpc as lnrpc
import grpc
import json

from google.protobuf.json_format import MessageToJson

from .broadcaster import Broadcaster


class LndWrapper:
    """API for Lightning gRPC client
    """
    _instance = None

    def __init__(self, cert, config):
        creds = grpc.ssl_channel_credentials(cert)
        channel = grpc.secure_channel(config.LND_HOST, creds)
        self.stub = lnrpc.LightningStub(channel)
        self.DEFAULT_PRICE = config.DEFAULT_PRICE
        self.DEFAULT_EXPIRY = config.DEFAULT_EXPIRY
        try:
            request = ln.GetInfoRequest()
            response = self.stub.GetInfo(request)
            logging.info(response)
        except grpc.RpcError as e:
           logging.error(e)    

        self.broadcast = Broadcaster._instance
        self.invoiceThread = threading.Thread(target = self.subscribe_invoices)
        self.invoiceThread.daemon = True

        LndWrapper._instance = self

    def start(self):
        self.invoiceThread.start()

    def get_invoice(self, memo="Peepshow"):
        try:
            expiry = { "creation_date": int(datetime.now().timestamp()),
                        "expiry": self.DEFAULT_EXPIRY }
            request = ln.Invoice(
                memo=memo,
                value=self.DEFAULT_PRICE,
                expiry=self.DEFAULT_EXPIRY,
                creation_date=expiry["creation_date"]
            )
            response = self.stub.AddInvoice(request)
            return { **json.loads(MessageToJson(response)), **expiry}
        except grpc.RpcError as e:
           logging.error(e)
           return e.details()

    def subscribe_invoices(self):
        try:
            request = ln.InvoiceSubscription()
            invoices = self.stub.SubscribeInvoices(request)
            for invoice in invoices:
                self.broadcast.updateClients(MessageToJson(invoice))
        except grpc.RpcError as e:
           logging.error(e)
           return e.details()  

