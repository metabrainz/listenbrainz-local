from collections import namedtuple
import os
from time import time
from copy import copy
import json
import logging
from logging.handlers import QueueHandler
import multiprocessing
from queue import Queue, Empty
from time import monotonic, sleep
from threading import Thread, get_ident
import traceback
from urllib.parse import urlparse

from troi.content_resolver.subsonic import SubsonicDatabase
from troi.content_resolver.metadata_lookup import MetadataLookup

from lb_local.view.credential import load_credentials
from lb_local.model.service import Service

APP_LOG_LEVEL_NUM = 19

def log(msg):
    with open("/tmp/log", "a+") as l:
        l.write("pid %d tid %d: %s\n" % (os.getpid(), get_ident(), msg))

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
        _, err_msg = load_credentials(message.user_id)
        if err_msg:
            return err_msg

        print("submit to queue %d" % os.getpid())
        self.submit_queue.put(message)
        print("submitted to queue")
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

    def __init__(self, submit_queue, stats_queue, stop_event, db_file):
        multiprocessing.Process.__init__(self)
        self.submit_queue = submit_queue
        self.stats_queue = stats_queue
        self.stop_event = stop_event
        self.db_file = db_file
        self.worker = None

        print("sync manager init %d, %d" % (os.getpid(), get_ident()))
        log("sync manager init %d, %d" % (os.getpid(), get_ident()))

    def run(self):

        self.worker = SyncWorker(self.db_file)
        self.worker.start()

        print("sync manager run %d, %d" % (os.getpid(), get_ident()))
        log("sync manager run %d, %d" % (os.getpid(), get_ident()))

        try:
            log("manager process started")
            while not self.stop_event.is_set():
                self.worker.process_log_messages()
                try:
                    job = self.submit_queue.get_nowait()
                    #log(str(job))
                    log("queue put(): job queue id: %d, pid: %d" % (id(self.worker.job_queue), os.getpid()))
                    self.worker.job_queue.put(job)
                    log("added job %d" % self.worker.job_queue.qsize())
                except Empty:
                    log("manager sleep")
                    # TODO: Reduce a bit later
                    sleep(1)
                    continue

            log("manager loop exited")
            self.worker.exit()
            self.worker.join()
            log("manager process exited")
        except Exception:
            traceback_str = traceback.format_exc()
            log("manager fail")
            log(traceback_str)

        print("sync manager run exit %d, %d" % (os.getpid(), get_ident()))
        log("sync manager run exit %d, %d" % (os.getpid(), get_ident()))
            

class SyncWorker(Thread):
    
    def __init__(self, db_file):
        Thread.__init__(self)
        self.job_queue = Queue()
        self.job_data = {}
        self.current_slug = None
        self._exit = False
        self.db_file = db_file
        print("sync worker init %d, %d" % (os.getpid(), get_ident()))
        log("sync worker init %d, %d" % (os.getpid(), get_ident()))
        
    def exit(self):
        self._exit = True
        
    def sync_service(self, submit_msg):
        print("sync service %d, %d" % (os.getpid(), get_ident()))
        log("sync service %d, %d" % (os.getpid(), get_ident()))

        slug = submit_msg.service["slug"]
        url = urlparse(submit_msg.service["url"])
        conf, _ = load_credentials(submit_msg.user_id)

        self.job_data[slug] = { "stats": None,
                                "logs": None,
                                "type": submit_msg.type,
                                "user_id": submit_msg.user_id,
                                "expire_at": submit_msg.expire_time,
                                "complete": False
                              }        
        self.current_slug = slug

        db = SubsonicDatabase(self.db_file, Config(**conf), quiet=False)
        try:
            db.open()
            
            if submit_msg["type"] == "full":
                log("call sync!")
                db.sync(slug)

            lookup = MetadataLookup(False)
            log("call lookup!")
            lookup.lookup(slug)

        except Exception as err:
            while True:
                try:
                    logging_queue.get_nowait()
                except Empty:
                    break
            traceback_str = traceback.format_exc()
            log("sync failed")
            log(traceback_str)
            self.job_data[slug]["error"] = "An error occurred when syncing the collection:\n" + str(traceback_str) + "\n"
            
        log("sync complete")

        self.job_data[slug]["complete"] = True
        self.current_slug = None
        
    def process_log_messages(self):
        """ Read log messages, process them as needed, then return them """
        
        
        slug = self.current_slug
        
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
                        log(rec.message)
                        log(err)
                        continue
                    self.job_data[slug]["stats"] = stats
                    continue
                    
                logs += rec.message + "\n"
                loaded_rows = True
            except Empty:
                break
            
        try:
            complete = self.job_data[service]["complete"]
        except KeyError:
            stats = self.job_data[service]["stats"]
            return StatusMessage(complete=False, stats=self.job_data[service]["stats"])

        if not loaded_rows and complete:
            return StatusMessage(complete=True, stats=self.job_data[service]["stats"], logs=logs)

        self.job_data[service]["sync_log"] = logs
        
        stats = self.job_data[service]["stats"]

        return StatusMessage(complete=complete, stats=self.job_data[service]["stats"], logs=logs)

    def run(self):

        print("sync worker run %d, %d" % (os.getpid(), get_ident()))
        log("sync worker run %d, %d" % (os.getpid(), get_ident()))
        try:
            while not self._exit:
                try:
                    log("get_nowait() queue id %d pid: %d size: %d" % (id(self.job_queue), os.getpid(), self.job_queue.qsize()))
                    submit_msg = self.job_queue.get_nowait()
                    log("got message!")
                except Empty:
                    log("worker sleep")
                    # TODO: Speed this up
                    sleep(1)
                    continue

                log("start sync job")
                self.sync_service(submit_msg)
                log("finish sync job")
        except Exception:
            traceback_str = traceback.format_exc()
            log("manager fail")
            log(traceback_str)
        print("sync worker run exit %d, %d" % (os.getpid(), get_ident()))
        log("sync worker run exit %d, %d" % (os.getpid(), get_ident()))