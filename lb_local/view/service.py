from time import time

import peewee
import validators
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.exceptions import BadRequest, NotFound

from lb_local.model.service import Service
from lb_local.model.credential import Credential
from lb_local.view.credential import load_credentials

service_bp = Blueprint("service_bp", __name__)


@service_bp.route("/", methods=["GET"])
@login_required
def service_index():
    if not current_user.is_admin:
        raise NotFound
    return render_template("service.html", page="service")


@service_bp.route("/list", methods=["GET"])
@login_required
def service_list():
    if not current_user.is_admin:
        raise NotFound
    services = Service.select()
    for service in services:
        if service.last_synched:
            service.last_synched_text = "%s seconds ago" % int(time() - service.last_synched)
        else:
            service.last_synched_text = ""
    return render_template("component/service-list.html", services=services)


@service_bp.route("/add", methods=["GET"])
@login_required
def service_add():
    if not current_user.is_admin:
        raise NotFound
    return render_template("service-add.html", mode="Add")


@service_bp.route("/<slug>/edit", methods=["GET"])
@login_required
def service_edit(slug):
    if not current_user.is_admin:
        raise NotFound
    service = Service.get(Service.slug == slug)
    return render_template("service-add.html", mode="Edit", service=service, slug=slug)


@service_bp.route("/<slug>/delete", methods=["GET"])
@login_required
def service_delete(slug):
    if not current_user.is_admin:
        raise NotFound
    try:
        service = Service.get(Service.slug == slug)
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
    if not current_user.is_admin:
        raise NotFound
    mode = request.form.get("mode", "")
    old_slug = request.form.get("old_slug", "")
    print("add save: mode '%s' '%s'" % (mode, old_slug))
    slug = request.form.get("slug", "")
    print("new slug '%s'" % slug)
    url = request.form.get("url", "")
    if not url or not slug:
        flash("Both URL and nickname are required.")
        return render_template("service-add.html", slug=slug, url=url)

    if not url.startswith("https://") and not url.startswith("http://"):
        flash("URL must start with http:// or https://")
        return render_template("service-add.html", slug=slug, url=url)

    if not validators.url(url, simple_host=True):
        flash("Invalid URL")
        return render_template("service-add.html", slug=slug, url=url)

    if mode == "Add":
        try:
            service = Service.create(slug=slug, url=url)
            service.save()
        except peewee.IntegrityError:
            flash("Service nickname is already being used, please provide a unique one.")
            return render_template("service-add.html", slug=slug, url=url)
    else:
        try:
            service = Service.get(slug=old_slug)
            service.slug = slug
            service.url = url
        except peewee.DoesNotExist:
            flash("Service does not exist. Internal error.")
            return render_template("service-add.html", slug=slug, url=url)
        service.save()

    load_credentials(current_user.user_id)

    return redirect(url_for("service_bp.service_index"))

@service_bp.route("/<slug>/sync", methods=["GET"])
@login_required
def service_sync(slug):
    if not current_user.is_admin:
        raise NotFound
    return render_template("service-sync.html", page="service", slug=slug)

@service_bp.route("/<slug>/sync/start", methods=["POST"])
@login_required
def service_sync_start(slug):
    if not current_user.is_admin:
        raise NotFound
    service = Service.get(Service.slug == slug)
    credential = Credential.select().where(Credential.owner == current_user.user_id and Credential.service == service.id)
    added = current_app.config["SYNC_MANAGER"].request_service_scan(service, credential, current_user.user_id)
    if not added:
        return render_template("component/sync-log.html", logs="There is a sync already queued, it should start soon.", update=True, slug=slug)

    return render_template("component/sync-log.html", logs="The sync has been enqueued, it should start soon.", update=True, slug=slug)

@service_bp.route("/<slug>/sync/log")
@login_required
def service_sync_log(slug):
    if not current_user.is_admin:
        raise NotFound
    try:
        logs, completed = current_app.config["SYNC_MANAGER"].get_sync_log(slug)
    except TypeError:
        print("bad request")
        return BadRequest("What are you smoking?")

    if logs is None:
        print("empty logs")
        raise BadRequest("Cannot find service with slug %s" % slug)

    return render_template("component/sync-log.html", logs=logs, update=(not completed), slug=slug)
