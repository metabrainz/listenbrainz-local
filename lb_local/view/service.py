import uuid
from time import time

import peewee
import validators
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from lb_local.model.service import Service

service_bp = Blueprint("service_bp", __name__)


@service_bp.route("/", methods=["GET"])
@login_required
def service_index():
    return render_template("service.html", page="service")


@service_bp.route("/list", methods=["GET"])
@login_required
def service_list():
    services = Service.select()
    for service in services:
        if service.last_scanned:
            service.last_scanned_text = "%s seconds ago" % int(time() - service.last_scanned)
        else:
            service.last_scanned_text = ""
    return render_template("component/service-list.html", services=services)


@service_bp.route("/add", methods=["GET"])
@login_required
def service_add():
    return render_template("service-add.html", mode="Add")


@service_bp.route("/<_uuid>/edit", methods=["GET"])
@login_required
def service_edit(_uuid):
    service = Service.get(Service.uuid == _uuid)
    return render_template("service-add.html", mode="Edit", service=service)


@service_bp.route("/<_uuid>/delete", methods=["GET"])
@login_required
def service_delete(_uuid):
    try:
        service = Service.get(Service.uuid == _uuid)
        service.delete_instance()
        flash("Service deleted")
    except peewee.DoesNotExist:
        flash("Service %s not found" % _uuid)
    except peewee.IntegrityError:
        flash("Service still in use and cannot be deleted.")

    return redirect(url_for("service_bp.service_index"))


@service_bp.route("/add", methods=["POST"])
@login_required
def service_add_post():
    name = request.form.get("name", "")
    url = request.form.get("url", "")
    _uuid = request.form.get("uuid", "")
    if not url or not name:
        flash("Both name and URL are required.")
        return render_template("service-add.html", name=name, url=url)

    if not url.startswith("https://") and not url.startswith("http://"):
        flash("URL must start with http:// or https://")
        return render_template("service-add.html", name=name, url=url)

    if not validators.url(url):
        flash("Invalid URL")
        return render_template("service-add.html", name=name, url=url)

    try:
        if _uuid:
            service = Service.get(uuid=_uuid)
            service.name = name
            service.url = url
        else:
            service = Service.create(name=name, url=url, uuid=uuid.uuid4())
        service.save()
    except peewee.IntegrityError:
        flash("Duplicate service name or service URL.")
        return render_template("service-add.html", name=name, url=url)

    return redirect(url_for("service_bp.service_index"))

@service_bp.route("/<_uuid>/sync", methods=["GET"])
@login_required
def service_scan(_uuid):
    return render_template("service-scan.html", page="service")
