from collections import namedtuple
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
        
SubmitMessage = namedtuple("SubmitMessage", ["service",
                                             "credential",
                                             "user_id",
                                             "expire_at",
                                             "type"])
StatusMessage = namedtuple("StatusMessage", ["complete",
                                             "error_msg",
                                             "stats",
                                             "logs"])

class SyncClient:
    def __init__(self, submit_queue, stats_queue):
        self.submit_queue = submit_queue
        self.stats_queue = stats_queue
        self.latest_status = None
        

        # TODO: Update the entry on disk  for both functions below
#        if complete:
#            query = Service.update({ "last_synched": time(), "status": "synced ok" }).where(Service.slug == service)
 #           query.execute()

    def request_sync(self, message: SubmitMessage):
        """ This function is called from the initiating process!"""
        
        # Make sure we can load a credential
        _, err_msg = load_credentials(user_id)
        if err_msg:
            return err_msg

        if message.expire_at is None:
            message.expire_at = monotonic() + LOG_EXPIRY_DURATION

        self.submit_queue.put(message)
        return ""
    
    def sync_status(self):
        
        # Fetch the latest stats. Keep only the last one
        while True:
            try:
                self.latest_status = self.stats_queue.get_nowait()
            except Empty:
                break
            
        return self.latest_status


class SyncManager(multiprocessing.Process):

    def __init__(self, submit_queue, stats_queue, stop_event):
        multiprocessing.Process.__init__(self)
        self.submit_queue = submit_queue
        self.stats_queue = stats_queue
        self.stop_event = stop_event
        
        self.worker = SyncWorker()
        self.worker.start()

    def run(self):

        print("manager process started")
        while not self.stop_event.is_set():
            self.worker.process_log_messages()
            try:
                job = self.submit_queue.get()
                self.worker.add_job(job)
            except Empty:
                print("sleep")
                sleep(1)
                continue

        self.worker.exit()
        print("manager process exited")

class SyncWorker(Thread):
    
    def __init__(self):
        Thread.__init__(self)
        self.job_queue = Queue()
        self.lock = Lock()
        self.job_data = {}
        self.current_slug = None
        self._exit = False
        
    def exit(self):
        self._exit = True
        
    def add_job(self, job):
        self.job_queue.put(job)

    def sync_service(self, submit_msg):
        
        slug = submit_msg.service.slug
        url = urlparse(submit_msg.service.url)
        conf, _ = load_credentials(submit_msg.user_id)

        self.lock.acquire()
        self.job_data[slug] = { "stats": None,
                                "logs": None,
                                "type": submit_msg.type,
                                "user_id": submit_msg.user_id,
                                "expire_at": submit_msg.expire_time,
                                "complete": False
                              }        
        self.current_slug = slug
        self.lock.release()

        from lb_local.server import app
        with app.app_context():
            db = SubsonicDatabase(current_app.config["DATABASE_FILE"], Config(**conf), quiet=False)
        try:
            db.open()
            
            if submit_msg.type == "full":
                db.sync(slug)

            lookup = MetadataLookup(False)
            lookup.lookup(slug)

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
            self.job_data[slug]["error"] = "An error occurred when syncing the collection:\n" + str(traceback_str) + "\n"
            self.lock.release()

        self.lock.acquire()
        self.job_data[slug]["complete"] = True
        self.current_slug = None
        self.lock.release()
        
    def process_log_messages(self):
        """ Read log messages, process them as needed, then return them """
        self.lock.acquire()
        slug = self.current_slug
        self.lock.release()
        
        if slug is None:
            return
        
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
                    self.job_data[slug]["stats"] = stats
                    self.lock.release()
                    continue
                    
                logs += rec.message + "\n"
                loaded_rows = True
            except Empty:
                break
            
        try:
            self.lock.acquire()
            complete = self.job_data[service]["complete"]
            self.lock.release()
        except KeyError:
            self.lock.acquire()
            stats = self.job_data[service]["stats"]
            self.lock.release()
            return StatusMessage(complete=False, stats=self.job_data[service]["stats"])

        if not loaded_rows and complete:
            return StatusMessage(complete=True, stats=self.job_data[service]["stats"], logs=logs)

        self.job_data[service]["sync_log"] = logs
        
        self.lock.acquire()
        stats = self.job_data[service]["stats"]
        self.lock.release()
        return StatusMessage(complete=complete, stats=self.job_data[service]["stats"], logs=logs)

    def run(self):

        print("sync thread started")
        while not self._exit:
            try:
                submit_mesg = self.job_queue.get()
            except Empty:
                sleep(.1)
                continue

            from lb_local.server import app
            with app.app_context():
                print("start sync job")
                self.sync_service(submit_msg)
                print("finish sync job")

        print("sync thread exited")