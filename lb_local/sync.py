import os
from copy import copy
import logging
from logging.handlers import QueueHandler
from queue import Queue
from threading import Lock, Thread

from flask import current_app
from troi.content_resolver.subsonic import SubsonicDatabase
from urllib.parse import urlparse

from lb_local.model.service import Service

logging_queue = Queue()
logger = logging.getLogger("troi_subsonic_scan")
logger.addHandler(QueueHandler(logging_queue))
logger.setLevel(logging.INFO)

class Config:
        def __init__(self, **entries):
            self.__dict__.update(entries)

class SyncManager(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.job_queue = Queue()
        self.lock = Lock()
        self.job_data = {}
        self._exit = False

    def request_service_scan(self, service, credential):
        added = False
        self.lock.acquire()
        if service.uuid not in self.job_data:
            added = True
            self.job_queue.put((service, credential))
            self.job_data[service.uuid] = { "service": service, "credential": credential, "scan_log": list() }
        self.lock.release()

        return added

    def scan_service(self, service, credential):
        print("Start scanning")

        url = urlparse(service.url)
        conf = copy(current_app.config)
        conf["SUBSONIC_HOST"] = "%s://%s" % (url.scheme, url.hostname)
        conf["SUBSONIC_PORT"] = int(url.port)

        conf["SUBSONIC_USER"] = credential.user_name
        conf["SUBSONIC_SALT"] = credential.salt
        conf["SUBSONIC_TOKEN"] = credential.token

        #TODO: how to report errors
        index_dir = os.path.join(current_app.config["SERVICES_DIRECTORY"], service.uuid)
        try:
            os.makedirs(index_dir)
        except FileExistsError:
            pass

        db_file = os.path.join(index_dir, "subsonic.db")
        db = SubsonicDatabase(db_file, Config(**conf), quiet=False)
        if not os.path.exists(db_file):
            db.create()

        db.open()
        db.sync()

    def run():
        while not _self.exit():
            pass
