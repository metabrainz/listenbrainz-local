import os
from copy import copy
import logging
from logging.handlers import QueueHandler
from queue import Queue, Empty
from threading import Lock, Thread
from time import time
import traceback
from urllib.parse import urlparse
from lb_local.view.credential import load_credentials

from flask import current_app
from troi.content_resolver.subsonic import SubsonicDatabase
from lb_local.model.service import Service
import config

# NOTES:
#    This module is very basic right now. The UI is poor, buttons are not enabled/disabled, the page cannot be reloaded, etc.
#    There are many things that need to be improved and if someone wants to help, please jump in!


# TODO: Cleanup old log entries after a while

LOG_EXPIRY_DURATION = 60 * 60  # in s
APP_LOG_LEVEL_NUM = 19


logging_queue = Queue()
logger = logging.getLogger("troi_subsonic_scan")
logger.addHandler(QueueHandler(logging_queue))
logger.setLevel(APP_LOG_LEVEL_NUM)

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

    def request_service_scan(self, service, credential, user_id):
        added = False
        self.lock.acquire()
        if service.slug in self.job_data and self.job_data[service.slug]["completed"]:
            del self.job_data[service.slug]
        if service.slug not in self.job_data:
            added = True
            self.job_queue.put((service, credential, user_id))
            self.job_data[service.slug] = { "service": service, "credential": credential, "sync_log": "", "completed": False, "expire_at": time() + LOG_EXPIRY_DURATION }
        self.lock.release()

        return added
    
    def sync_service(self, service, credential, user_id):
        
        url = urlparse(service.url)
        conf = load_credentials(user_id)

        #TODO: how to report errors -- add to scan log for now
#        index_dir = os.path.join(current_app.config["SERVICES_DIRECTORY"], service.slug)
#        try:
#            os.makedirs(index_dir)
#        except FileExistsError:
#            pass

#        db_file = os.path.join(index_dir, "subsonic.db")
        db = SubsonicDatabase(config.DATABASE_FILE, Config(**conf), quiet=False)
        try:
            db.open()
            db.sync(service.slug)
        except Exception as err:
            while True:
                try:
                    logging_queue.get_nowait()
                except Empty:
                    break
            traceback_str = traceback.format_exc()
            self.lock.acquire()
            self.job_data[service.slug]["sync_log"] += "An error occurred when syncing the collection:\n" + str(traceback_str) + "\n"
            self.lock.release()

        self.lock.acquire()
        self.job_data[service.slug]["completed"] = True
        self.lock.release()
        
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
        
        return logs, completed

    def run(self):
        
        while not self._exit:
            try:
                service, credential, user_id = self.job_queue.get()
            except Empty:
                sleep(.1)
                continue

            from lb_local.server import app
            with app.app_context():
                self.sync_service(service, credential, user_id)