import hashlib
import uuid
from urllib.parse import urlparse

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import peewee
from flask_login import login_required, current_user
from werkzeug.exceptions import Forbidden

from lb_local.model.credential import Credential
from lb_local.model.service import Service

credential_bp = Blueprint("credential_bp", __name__)

def load_credentials(user_id, credentials=None):

    msg = ""
    
    if credentials is None:
        print("credential is not provided")
        credentials = Credential.select().where((Credential.owner == user_id) | (Credential.shared == True))
        if not credentials:
            msg = "There are no credentials available. Please add your own credential."

    config = {}
    service_count = 0
    for credential in credentials:
        print(credential)
        url = urlparse(credential.service.url)
        salt = str(uuid.uuid4())
        h = hashlib.new('md5')
        h.update(bytes(credential.password, "utf-8"))
        h.update(bytes(salt, "utf-8"))
        token = h.hexdigest()

        config[credential.service.slug] = {
            "host": "%s://%s" % (url.scheme, url.hostname),
            "url": credential.service.url,
            "port": int(url.port),
            "username": credential.user_name,
            "password": credential.password,
            "shared": credential.shared,
            "owner_id": credential.owner.user_id,
            "salt": salt,
            "token": token
        }
        service_count += 1
        print(config)

    # This function could be called outside the app context, then don't update the session
    try:
        session["subsonic"] = config
        if service_count == 1: 
            session["cors_url"] = "%s://%s" % (url.scheme, url.hostname)
        else:
            session["cors_url"] = "*"
    except RuntimeError:
        pass
        
    return { "SUBSONIC_SERVERS" : config}, msg


@credential_bp.route("/", methods=["GET"])
@login_required
def credential_index():
    if not current_user.is_authorized:
        raise NotFound
    services = Service.select()
    if not services:
        flash("You need to add a service before adding a credential")
    return render_template("credential.html", page="credential", services=services)


@credential_bp.route("/list", methods=["GET"])
@login_required
def credential_list():
    if not current_user.is_authenticated:
        raise NotFound
    return render_template("component/credential-list.html", 
        credentials=Credential.select().where(Credential.owner == current_user.user_id))


@credential_bp.route("/add", methods=["GET"])
@login_required
def credential_add():
    if not current_user.is_authenticated:
        raise NotFound
    services = Service.select()
    if not services:
        flash("You need to add a service before adding a credential")
    return render_template("credential-add.html", mode="Add", services=services)


@credential_bp.route("/<id>/edit", methods=["GET"])
@login_required
def credential_edit(id):
    if not current_user.is_authenticated:
        raise NotFound
    credential = Credential.get(Credential.id == id)
    services = Service.select()
    return render_template("credential-add.html",
                           mode="Edit",
                           credential=credential,
                           services=services)


@credential_bp.route("/<id>/delete", methods=["GET"])
@login_required
def credential_delete(id):
    if not current_user.is_authenticated:
        raise NotFound
    try:
        credential = Credential.get(Credential.id == id)
        credential.delete_instance()
        flash("Credential deleted")
    except peewee.DoesNotExist:
        flash("Credential %s not found" % id)
    except peewee.IntegrityError:
        flash("Credential still in use and cannot be deleted.")

    load_credentials(current_user.user_id)

    return redirect(url_for("credential_bp.credential_index"))


@credential_bp.route("/add", methods=["POST"])
@login_required
def credential_add_post():
    if not current_user.is_authenticated:
        raise NotFound
    _id = int(request.form.get("id", "-1"))
    service_id = request.form.get("service", None)
    user_name = request.form.get("user_name", "").strip()
    password = request.form.get("password", "").strip()
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
            if credential.owner.user_id != current_user.user_id:
                raise Forbidden()

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
        if str(err).startswith("UNIQUE constraint failed"):
            flash("Cannot create more than one credential per user/service.")
        else:
            flash("Database error. (%s)" % err)
        return render_template("credential-add.html", user_name=user_name, service=service, password=password)

    load_credentials(current_user.user_id)

    return redirect(url_for("credential_bp.credential_index"))