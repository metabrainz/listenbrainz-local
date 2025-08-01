import datetime
import timeago
from time import time, monotonic
from urllib.parse import urlparse

import peewee
from playhouse.shortcuts import model_to_dict
import validators
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, Response, make_response
from flask_login import login_required, current_user
from werkzeug.exceptions import BadRequest, NotFound, Forbidden

from lb_local.model.service import Service
from lb_local.model.credential import Credential
from lb_local.view.credential import load_credentials
from lb_local.sync import SyncClient, SubmitMessage

service_bp = Blueprint("service_bp", __name__)

LOG_EXPIRY_DURATION = 60 * 60  # in s


@service_bp.route("/", methods=["GET"])
@login_required
def service_index():
    if not current_user.is_service_user and not current_user.is_admin:
        raise NotFound
    return render_template("service.html", page="service")


@service_bp.route("/list", methods=["GET"])
@login_required
def service_list():
    if not current_user.is_service_user and not current_user.is_admin:
        raise NotFound
    if current_user.is_admin:
        services = Service.select()
    else:
        services = Service.select().where(Service.owner == current_user)
    for service in services:
        if service.last_synched:
            sync_date = datetime.datetime.fromtimestamp(service.last_synched)
            service.last_synched_text = timeago.format(sync_date, datetime.datetime.now())
        else:
            service.last_synched_text = ""
    return render_template("component/service-list.html", services=services)


@service_bp.route("/add", methods=["GET"])
@login_required
def service_add():
    if not current_user.is_service_user and not current_user.is_admin:
        raise NotFound
    return render_template("service-add.html", mode="Add")


@service_bp.route("/<slug>/edit", methods=["GET"])
@login_required
def service_edit(slug):
    if not current_user.is_service_user and not current_user.is_admin:
        raise NotFound
    service = Service.get(Service.slug == slug)
    if not current_user.is_admin and service.owner.user_id != current_user.user_id:
        raise Forbidden
    return render_template("service-add.html", mode="Edit", url=service.url, slug=slug)


@service_bp.route("/<slug>/delete", methods=["GET"])
@login_required
def service_delete(slug):
    if not current_user.is_service_user and not current_user.is_admin:
        raise NotFound
    try:
        service = Service.get(Service.slug == slug)
        if not current_user.is_admin and service.owner.user_id != current_user.user_id:
            raise Forbidden
        service.delete_instance()
        flash("Service deleted")
    except peewee.DoesNotExist:
        flash("Service %s not found" % slug)
    except peewee.IntegrityError:
        flash("Service still in use and cannot be deleted.")

    return redirect(url_for("service_bp.service_index"))


@service_bp.route("/add", methods=["POST"])
@login_required
def service_add_post():
    if not current_user.is_service_user and not current_user.is_admin:
        raise NotFound
    mode = request.form.get("mode", "")
    old_slug = request.form.get("old_slug", "")
    slug = request.form.get("slug", "").strip()
    url = request.form.get("url", "").strip()
    if not url or not slug:
        flash("Both URL and nickname are required.")
        return render_template("service-add.html", slug=slug, url=url, mode=mode)

    if not url.startswith("https://") and not url.startswith("http://"):
        flash("URL must start with http:// or https://")
        return render_template("service-add.html", slug=slug, url=url, mode=mode)

    if not validators.url(url, simple_host=True):
        flash("Invalid URL")
        return render_template("service-add.html", slug=slug, url=url, mode=mode)

    parsed_url = urlparse(url)
    if parsed_url.port is None:
        flash("The service URL must contain a port number. Use 443 for https installations.")
        return render_template("service-add.html", slug=slug, url=url, mode=mode)

    if mode == "Add":
        try:
            service = Service.create(slug=slug, owner=current_user.user_id, url=url)
            service.save()
        except peewee.IntegrityError as err:
            flash("Service nickname or URL is already being used, please provide unique values.")
            print(err)
            return render_template("service-add.html", slug=slug, url=url, mode=mode)
    else:
        try:
            service = Service.get(slug=old_slug)
            service.slug = slug
            service.url = url
        except peewee.DoesNotExist:
            flash("Service does not exist. Internal error.")
            return render_template("service-add.html", slug=slug, url=url, mode=mode)
        service.save()

    load_credentials(current_user.user_id)

    return redirect(url_for("service_bp.service_index"))

@service_bp.route("/<slug>/sync", methods=["GET"])
@login_required
def service_sync(slug):
    if not current_user.is_service_user and not current_user.is_admin:
        raise NotFound

    service = Service.get(Service.slug == slug)
    if not current_user.is_admin and current_user.user_id != service.owner.user_id:
        raise NotFound
        
    client = SyncClient(current_app.config["SUBMIT_QUEUE"],
                        current_app.config["STATS_REQ_QUEUE"],
                        current_app.config["STATS_QUEUE"])
    current_status = client.sync_status(slug)
    return render_template("service-sync.html",
                           page="service",
                           slug=slug,
                           complete=(current_status and current_status.complete) or True)

@service_bp.route("/<slug>/sync/start", methods=["POST"])
@service_bp.route("/<slug>/sync/start/metadata-only", methods=["POST"])
@login_required
def service_sync_start(slug):
    if not current_user.is_service_user and not current_user.is_admin:
        raise NotFound
    
    if request.path.endswith("metadata-only"):
        type = "metadata_only"
    else:
        type = "full"

    service = Service.get(Service.slug == slug)
    if not current_user.is_admin and current_user.user_id != service.owner.user_id:
        raise NotFound
    credential = Credential.get(Credential.owner == current_user.user_id and Credential.service == service.id)
    
    expire_at = monotonic() + LOG_EXPIRY_DURATION
    submit_msg = SubmitMessage(service=model_to_dict(service),
                               credential=model_to_dict(credential),
                               user_id=current_user.user_id,
                               type=type,
                               expire_at=expire_at)

    client = SyncClient(current_app.config["SUBMIT_QUEUE"],
                        current_app.config["STATS_REQ_QUEUE"],
                        current_app.config["STATS_QUEUE"])
    msg = client.request_sync(submit_msg)
    if msg:
        return render_template("component/sync-status.html", logs=msg, update=True, slug=slug)

    return render_template("component/sync-status.html", update=True, slug=slug)

@service_bp.route("/<slug>/sync/log")
@login_required
def service_sync_log(slug):
    if not current_user.is_service_user and not current_user.is_admin:
        raise NotFound
    
    service = Service.get(Service.slug == slug)
    if not current_user.is_admin and current_user.user_id != service.owner.user_id:
        raise NotFound

    client = SyncClient(current_app.config["SUBMIT_QUEUE"],
                        current_app.config["STATS_REQ_QUEUE"],
                        current_app.config["STATS_QUEUE"])
    current_status = client.sync_status(slug)
    print("got status: ", current_status)
    if current_status is None:
        return "", 204
    
    headers = {} 
    if current_status.complete:
        headers['HX-Trigger-After-Swap'] = 'sync-complete'

    response = Response(render_template("component/sync-status.html",
                                        stats=current_status.stats, 
                                        complete=current_status.complete,
                                        slug=slug),
                        headers=headers)
    return response

@service_bp.route("/<slug>/sync/full-log")
@login_required
def service_sync_full_log(slug):
    if not current_user.is_service_user and not current_user.is_admin:
        raise NotFound

    service = Service.get(Service.slug == slug)
    if not current_user.is_admin and current_user.user_id != service.owner.user_id:
        raise NotFound

    client = SyncClient(current_app.config["SUBMIT_QUEUE"],
                        current_app.config["STATS_REQ_QUEUE"],
                        current_app.config["STATS_QUEUE"])
    current_status = client.sync_status(slug)
    if current_status.logs is None:
        logs = "No log file available."
    else:
        logs = current_status.logs
    
    response = make_response(logs, 200)
    response.mimetype = "text/plain"
    return response