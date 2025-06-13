import os
from copy import copy
import logging
from logging.handlers import QueueHandler
from queue import Queue, Empty
from threading import Lock, Thread
from time import time

from flask import current_app
from troi.content_resolver.subsonic import SubsonicDatabase
from urllib.parse import urlparse

from lb_local.model.service import Service

LOG_EXPIRY_DURATION = 60 * 60  # in s

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
        
    def exit(self):
        self._exit = True

    def request_service_scan(self, service, credential):
        added = False
        self.lock.acquire()
        if service.uuid in self.job_data and self.job_data[service.uuid]["completed"]:
            del self.job_data[service.uuid]
        if service.uuid not in self.job_data:
            added = True
            self.job_queue.put((service, credential))
            self.job_data[service.uuid] = { "service": service, "credential": credential, "sync_log": "", "completed": False, "expire_at": time() + LOG_EXPIRY_DURATION }
        self.lock.release()

        return added

    def sync_service(self, service, credential):
        url = urlparse(service.url)
        conf = copy(current_app.config)
        conf["SUBSONIC_HOST"] = "%s://%s" % (url.scheme, url.hostname)
        conf["SUBSONIC_PORT"] = int(url.port)

        conf["SUBSONIC_USER"] = credential.user_name
        conf["SUBSONIC_SALT"] = credential.salt
        conf["SUBSONIC_TOKEN"] = credential.token

        #TODO: how to report errors -- add to scan log for now
        index_dir = os.path.join(current_app.config["SERVICES_DIRECTORY"], service.uuid)
        try:
            os.makedirs(index_dir)
        except FileExistsError:
            pass

        db_file = os.path.join(index_dir, "subsonic.db")
        db = SubsonicDatabase(db_file, Config(**conf), quiet=False)
        if not os.path.exists(db_file):
            db.create()

        try:
            db.open()
            db.sync()
        except Exception as err:
            while True:
                try:
                    logging_queue.get_nowait()
                except Empty:
                    break
            self.lock.acquire()
            self.job_data[service.uuid]["sync_log"] += "An error occurred when syncing the collection:\n" + str(err) + "\n"
            self.lock.release()

        self.lock.acquire()
        self.job_data[service.uuid]["completed"] = True
        self.lock.release()
        
        print("scan complete")
    
    def get_sync_log(self, service):
        self.lock.acquire()
        try:
            logs = self.job_data[service]["sync_log"]
        except KeyError:
            return None, True
        finally:
            self.lock.release()
        
        loaded_rows = False
        while True:
            try:
                rec = logging_queue.get_nowait()
                logs += rec.message + "\n"
                loaded_rows = True
            except Empty:
                break
            
        self.lock.acquire()
        try:
            completed = self.job_data[service]["completed"]
        except KeyError:
            return None
        finally:
            self.lock.release()

        if not loaded_rows and completed:
            return logs, completed

        self.lock.acquire()
        self.job_data[service]["sync_log"] = logs
        self.lock.release()
        
        print("log, normal end", completed);
        return logs, completed

    def run(self):
        
        #TODO: Cleanup old logs
        while not self.exit():
            try:
                service, credential = self.job_queue.get()
            except Empty:
                sleep(.5)
                continue

            from lb_local.server import app
            with app.app_context():
                self.sync_service(service, credential)