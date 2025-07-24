import os
from time import time
from copy import copy
import json
import logging
from logging.handlers import QueueHandler
import multiprocessing
from queue import Queue, Empty
from time import monotonic
from threading import Thread, Lock
import traceback
from urllib.parse import urlparse

from flask import current_app
from troi.content_resolver.subsonic import SubsonicDatabase
from troi.content_resolver.metadata_lookup import MetadataLookup

from lb_local.view.credential import load_credentials
from lb_local.model.service import Service

LOG_EXPIRY_DURATION = 60 * 60  # in s
APP_LOG_LEVEL_NUM = 19


logging_queue = Queue()
logger = logging.getLogger("troi_subsonic_scan")
logger.addHandler(QueueHandler(logging_queue))
logger.setLevel(APP_LOG_LEVEL_NUM)

class Config:
    def __init__(self, **entries):
        self.__dict__.update(entries)

class SyncManagerClient:
    def __init__(self, submit_queue, stats_queue):
        self.submit_queue = submit_queue
        self.stats_queue = stats_queue

    def request_service_scan(submit_queue, service, credential, user_id, metadata_only=False):
        """ This function is called from the initiating process!"""
        
        # Make sure we can load a credential
        _, msg = load_credentials(user_id)
        if msg:
            return msg

        job_data = { "service": service,
                     "credential": credential,
                     "sync_log": "", 
                     "completed": False,
                     "expire_at": monotonic() + LOG_EXPIRY_DURATION,
                     "stats": tuple(),
                     "type": "metadata" if metadata_only else "full" }
        submit_queue.put((service, credential, user_id, job_data))
        return ""

class SyncManager(multiprocessing.Process):

    def __init__(self, submit_queue, stats_queue):
        multiprocessing.Process.__init__(self)
        self.submit_queue = submit_queue
        self.stats_queue = stats_queue
        
        self.worker = SyncWorker()
        self.worker.start()

    def exit(self):
        self.worker.exit()

    def get_sync_status(self, service):
        """ Fetch the current status """
        pass

    
    def run(self):

        print("manager process started")
        while not self._exit:
            self.worker.process_log_messages()
            try:
                job = self.submit_queue.get()
                self.worker.add_job(job)
            except Empty:
                sleep(.1)
                continue

        print("manager process exited")

class SyncWorker(Thread):
    
    def __init__(self):
        self.job_queue = Queue()
        self.job_data = {}
        self._exit = False
        
    def exit(self):
        self._exit = True
        
    def add_job(self, job):
        self.job_queue.put(job)

    def sync_completed(self, slug):
        self.lock.acquire()
        if slug in self.job_data:
            completed = self.job_data[slug]["completed"] 
        else:
            completed = True
        self.lock.release()

        return completed

    def sync_service(self, service, credential, user_id, job_data):
        
        url = urlparse(service.url)
        conf, _ = load_credentials(user_id)

        self.lock.acquire()
        type = self.job_data[service.slug]["type"]
        self.lock.release()

        from lb_local.server import app
        with app.app_context():
            db = SubsonicDatabase(current_app.config["DATABASE_FILE"], Config(**conf), quiet=False)
        try:
            db.open()
            
            if type == "full":
                db.sync(service.slug)

            lookup = MetadataLookup(False)
            lookup.lookup(service.slug)

        except Exception as err:
            while True:
                try:
                    logging_queue.get_nowait()
                except Empty:
                    break
            traceback_str = traceback.format_exc()
            print("sync failed")
            print(traceback_str)
            self.lock.acquire()
            self.job_data[service.slug]["sync_log"] += "An error occurred when syncing the collection:\n" + str(traceback_str) + "\n"
            self.lock.release()

        self.lock.acquire()
        self.job_data[service.slug]["completed"] = True
        self.lock.release()
        
    def process_log_messages(self):
        """ Read log messages, mangle and then return to push into stats queue"""
        try:
            self.lock.acquire()
            logs = self.job_data[service]["sync_log"]
            self.lock.release()
        except KeyError:
            return None, tuple(), True
        
        loaded_rows = False
        while True:
            try:
                rec = logging_queue.get_nowait()
                if rec.message[0] == "[":
                    try:
                        stats = json.loads(rec.message)
                    except Exception as err:
                        print(rec.message)
                        print(err)
                        continue
                    self.lock.acquire()
                    self.job_data[service]["stats"] = stats
                    self.lock.release()
                    continue
                    
                logs += rec.message + "\n"
                loaded_rows = True
            except Empty:
                break
            
        try:
            self.lock.acquire()
            completed = self.job_data[service]["completed"]
            self.lock.release()
        except KeyError:
            self.lock.acquire()
            stats = self.job_data[service]["stats"]
            self.lock.release()
            return None, stats, False
            
        if completed:
            query = Service.update({ "last_synched": time(), "status": "synced ok" }).where(Service.slug == service)
            query.execute()

        if not loaded_rows and completed:
            return logs, self.job_data[service]["stats"], completed

        self.job_data[service]["sync_log"] = logs
        
        self.lock.acquire()
        stats = self.job_data[service]["stats"]
        self.lock.release()
        return logs, stats, completed

    def clear_out_old_logs(self):
        # TODO: Old, needs updating
        
    def run(self):

        print("sync thread started")
        while not self._exit:
            try:
                service, credential, user_id, job_data = self.job_queue.get()
            except Empty:
                sleep(.1)
                continue

        added = False  

        self.lock.acquire()
        if service.slug in self.job_data and self.job_data[service.slug]["completed"]:
            if service.slug not in self.job_data:
                added = True
                self.job_queue.put(job)
        self.lock.release()
        
        else:
            msg = "There is a sync already queued, it should start soon."
        return added
            from lb_local.server import app
            with app.app_context():
                print("start sync job")
                self.sync_service(service, credential, user_id, job_data)
                print("finish sync job")

        print("sync thread exited")