from collections import namedtuple
import os
from time import time
from copy import copy
import json
import logging
from logging.handlers import QueueHandler
import multiprocessing
from queue import Queue, Empty, Full
from time import monotonic, sleep
from threading import Thread, get_ident, Lock
import traceback
from urllib.parse import urlparse
import uuid
import hashlib

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
    def __init__(self, submit_queue, stats_req_queue, stats_queue):
        self.submit_queue = submit_queue
        self.stats_req_queue = stats_req_queue
        self.stats_queue = stats_queue
        

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

        self.submit_queue.put(message)
        return ""
    
    def sync_status(self, slug):
        self.stats_req_queue.put(slug)
        try:
            print("fetch stats from queue %d %d" % (self.stats_queue.qsize(), id(self.stats_queue)))
            s = self.stats_queue.get(True, 3.0)
            print("got stats from queue", s)
            return s
        except Empty:
            print("sync status get timed out")
            return None


class SyncManager(multiprocessing.Process):

    def __init__(self, submit_queue, stats_req_queue, stats_queue, stop_event, db_file):
        multiprocessing.Process.__init__(self)
        self.submit_queue = submit_queue
        self.stats_req_queue = stats_req_queue
        self.stats_queue = stats_queue
        self.stop_event = stop_event
        self.db_file = db_file
        self.worker = None

    def run(self):

        self.worker = SyncWorker(self.db_file)
        self.worker.start()

        log("manager starting")
        try:
            while not self.stop_event.is_set():
                self.worker.process_log_messages()
                try:
                    job = self.submit_queue.get_nowait()
                    self.worker.job_queue.put(job)
                except Empty:
                    pass

                try:
                    slug = self.stats_req_queue.get_nowait()
                    log("got request for %s" % slug)
                    while True:
                        try:
                            s = self.worker.current_status(slug)
                            log("got stats from worker " + str(s))
                            self.stats_queue.put(s)
#                            self.stats_queue.put(self.worker.current_status(slug))
                            log("put stats into queue %d %d" % (self.stats_queue.qsize(), id(self.stats_queue)))
                            break
                        except Full:
                            log("queue full")
                            sleep(1)
                            continue
                except Empty:
                    pass

                sleep(1)

            self.worker.exit()
            self.worker.join()
        except Exception:
            traceback_str = traceback.format_exc()
            log(traceback_str)


class SyncWorker(Thread):
    
    def __init__(self, db_file):
        Thread.__init__(self)
        self.job_queue = Queue()
        self.lock = Lock()
        self.job_data = {}
        self.current_slug = None
        self._exit = False
        self.db_file = db_file
        
    def exit(self):
        self._exit = True
        
    def sync_service(self, submit_msg):
        slug = submit_msg.service["slug"]

        config = {}
        url = urlparse(submit_msg.service["url"])
        salt = str(uuid.uuid4())
        h = hashlib.new('md5')
        h.update(bytes(submit_msg.credential["password"], "utf-8"))
        h.update(bytes(salt, "utf-8"))
        token = h.hexdigest()

        config[submit_msg.service["slug"]] = {
            "host": "%s://%s" % (url.scheme, url.hostname),
            "url": submit_msg.service["url"],
            "port": int(url.port),
            "username": submit_msg.credential["user_name"],
            "password": submit_msg.credential["password"],
            "salt": salt,
            "token": token
        }
        conf = { "SUBSONIC_SERVERS" : config}
        self.lock.acquire()
        self.job_data[slug] = { "stats": None,
                                "logs": None,
                                "type": submit_msg.type,
                                "user_id": submit_msg.user_id,
                                "expire_at": submit_msg.expire_at,
                                "complete": False,
                                "error_msg": ""
                              }        
        self.lock.release()
        self.current_slug = slug

        db = SubsonicDatabase(self.db_file, Config(**conf), quiet=False)
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
            log(traceback_str)
            self.lock.acquire()
            self.job_data[slug]["error"] = "An error occurred when syncing the collection:\n" + str(traceback_str) + "\n"
            self.lock.release()
            
        self.lock.acquire()
        self.job_data[slug]["complete"] = True
        self.lock.release()
        log("JOB COMPLETE")
        self.current_slug = None
        
    def process_log_messages(self):
        """ Read log messages, process them as needed, then return them """
        
        
        slug = self.current_slug
        if slug is None:
            return
        
        loaded_rows = False
        self.lock.acquire()
        logs = self.job_data[slug]["logs"]
        self.lock.release()
        error_msg = ""
        while True:
            try:
                rec = logging_queue.get_nowait()
                if rec.message.startswith("json-"):
                    try:
                        stats = json.loads(rec.message[5:])
                    except Exception as err:
                        error_msg = err
                        log(rec.message)
                        log(err)
                        continue

                    log("received stats " + str(stats))
                    self.lock.acquire()
                    self.job_data[slug]["stats"] = stats
                    self.lock.release()
                    continue

                if logs is None:
                    logs = ""
                logs += rec.message + "\n"
                loaded_rows = True
            except Empty:
                break
            
        self.lock.acquire()
        self.job_data[slug]["logs"] = logs
        self.lock.release()
        
    def current_status(self, slug):

        self.lock.acquire()
        try:
            job = self.job_data[slug]
        except KeyError:
            return None
        finally:
            self.lock.release()

        return StatusMessage(complete=job["complete"],
                             stats=job["stats"],
                             logs=job["logs"],
                             error_msg=job["error_msg"])

    def run(self):

        log("worker starting")
        try:
            while not self._exit:
                try:
                    submit_msg = self.job_queue.get_nowait()
                except Empty:
                    # TODO: Speed this up
                    sleep(1)
                    continue

                self.sync_service(submit_msg)
        except Exception:
            traceback_str = traceback.format_exc()
            log("worker fail")
            log(traceback_str)