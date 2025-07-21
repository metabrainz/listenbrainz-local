import os
from time import time
from copy import copy
import json
import logging
from logging.handlers import QueueHandler
from queue import Queue, Empty
from threading import Lock, Thread
from time import monotonic
import traceback
from urllib.parse import urlparse

from flask import current_app
from troi.content_resolver.subsonic import SubsonicDatabase
from troi.content_resolver.metadata_lookup import MetadataLookup

from lb_local.view.credential import load_credentials
from lb_local.model.service import Service

# NOTES:
#    This module is very basic right now. The UI is poor, buttons are not enabled/disabled, the page cannot be reloaded, etc.
#    There are many things that need to be improved and if someone wants to help, please jump in!


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

    def request_service_scan(self, service, credential, user_id, metadata_only=False):
        conf, msg = load_credentials(user_id)
        if msg:
            return msg

        added = False
        self.lock.acquire()
        if service.slug in self.job_data and self.job_data[service.slug]["completed"]:
            del self.job_data[service.slug]
        if service.slug not in self.job_data:
            added = True
            self.job_queue.put((service, credential, user_id))
            self.job_data[service.slug] = { "service": service,
                                            "credential": credential,
                                            "sync_log": "", "completed": False,
                                            "expire_at": monotonic() + LOG_EXPIRY_DURATION,
                                            "stats": tuple(),
                                            "type": "metadata" if metadata_only else "full" }
        else:
            msg = "There is a sync already queued, it should start soon."
        self.lock.release()
        
#        self.clear_out_old_logs()

        return msg
    
    def sync_completed(self, slug):
        self.lock.acquire()
        if slug in self.job_data:
            completed = self.job_data[slug]["completed"] 
        else:
            completed = True
        self.lock.release()
        return completed

    def sync_service(self, service, credential, user_id):
        
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
            print(err)
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
            return None, tuple(), True
        finally:
            self.lock.release()
        
        loaded_rows = False
        while True:
            try:
                rec = logging_queue.get_nowait()
                if rec.message[0] == "[":
                    try:
                        stats = json.loads(rec.message)
                    except Exception as err:
                        print(err)
                        continue
                    self.job_data[service]["stats"] = stats
                    continue
                    
                logs += rec.message + "\n"
                loaded_rows = True
            except Empty:
                break
            
        self.lock.acquire()
        try:
            completed = self.job_data[service]["completed"]
        except KeyError:
            return None, self.job_data[service]["stats"], False
        finally:
            self.lock.release()
            
        if completed:
            query = Service.update({ "last_synched": time(), "status": "synced ok" }).where(Service.slug == service)
            query.execute()

        if not loaded_rows and completed:
            return logs, self.job_data[service]["stats"], completed

        self.lock.acquire()
        self.job_data[service]["sync_log"] = logs
        self.lock.release()
        
        return logs, self.job_data[service]["stats"], completed

    def clear_out_old_logs(self):
        # TODO: Old, needs updating
        self.lock.acquire()
        valid_jobs = []
        for job in self.job_data:
            if self.job_data[job]["expire_at"] > monotonic():
                valid_jobs.append(self.job_data[job])
                
        self.job_data = valid_jobs
        self.lock.release()
        
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