import hashlib
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import peewee
from flask_login import login_required, current_user

from lb_local.model.credential import Credential
from lb_local.model.service import Service

credential_bp = Blueprint("credential_bp", __name__)

# TODO: After editing credential, update session


def load_current_credentials_for_user():
    user_id = current_user.user_id
    return Credential.select().where((Credential.owner == user_id) | (Credential.shared == True))


@credential_bp.route("/", methods=["GET"])
@login_required
def credential_index():
    services = Service.select()
    if not services:
        flash("You need to add a service before adding a credential")
    return render_template("credential.html", page="credential", services=services)


@credential_bp.route("/list", methods=["GET"])
@login_required
def credential_list():
    credentials = load_current_credentials_for_user()
    return render_template("component/credential-list.html", credentials=credentials)


@credential_bp.route("/add", methods=["GET"])
@login_required
def credential_add():
    services = Service.select()
    if not services:
        flash("You need to add a service before adding a credential")
    return render_template("credential-add.html", mode="Add", services=services)


@credential_bp.route("/<id>/edit", methods=["GET"])
@login_required
def credential_edit(id):
    credential = Credential.get(Credential.id == id)
    services = Service.select()
    return render_template("credential-add.html", mode="Edit", credential=credential, services=services)


@credential_bp.route("/<id>/delete", methods=["GET"])
@login_required
def credential_delete(id):
    try:
        credential = Credential.get(Credential.id == id)
        credential.delete_instance()
        flash("Credential deleted")
    except peewee.DoesNotExist:
        flash("Credential %s not found" % id)
    except peewee.IntegrityError:
        flash("Credential still in use and cannot be deleted.")

    return redirect(url_for("credential_bp.credential_index"))


@credential_bp.route("/add", methods=["POST"])
@login_required
def credential_add_post():
    _id = int(request.form.get("id", "-1"))
    service_id = request.form.get("service", None)
    user_name = request.form.get("user_name", "")
    password = request.form.get("password", "")
    owner = current_user.user_id
    shared = request.form.get("shared", "off")
    shared = True if shared == "on" else False
    if not user_name or ((not password) and _id == -1):
        if _id == -1:
            flash("Both user name and password are required.")
        else:
            flash("User name is required.")
        services = Service.select()
        return render_template("credential-add.html",
                               user_name=user_name,
                               service_id=service_id,
                               password=password,
                               services=services)

    service = Service.get(Service.id == service_id)

    try:
        if _id >= 1:
            credential = Credential.get(id=_id)
            credential.service = service_id
            credential.owner = owner
            credential.user_name = user_name
            credential.shared = shared
            if password:
                credential.password = password
        else:
            credential = Credential.create(service=service, owner=owner, user_name=user_name, password=password, shared=shared)

        credential.save()
    except peewee.IntegrityError as err:
        flash("Bummer dude. (%s)" % err)
        return render_template("credential-add.html", user_name=user_name, service=service, password=password)

    return redirect(url_for("credential_bp.credential_index"))


def load_credential():
    # TODO: Add the DB file support as well
    credential = Credential.select().first()
    subsonic = {}
    if credential is not None:
        subsonic = {"user": credential.user_name, "password": credential.password}
        service = Service.get(Service.id == credential.service.id)
        if service is not None:
            subsonic["url"] = service.url

    session["subsonic"] = subsonic
