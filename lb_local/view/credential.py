import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import peewee
from flask_login import login_required

from lb_local.model.credential import Credential
from lb_local.model.service import Service

credential_bp = Blueprint("credential_bp", __name__)

# TODO: After editing credential, update session

@credential_bp.route("/", methods=["GET"])
@login_required
def credential_index():
    return render_template("credential.html", page="credential")

@credential_bp.route("/add", methods=["GET"])
@login_required
def credential_add():
    services = Service.select()
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
        flash("Credential %s not found" % uuid)
    except peewee.IntegrityError as err:
        flash("Credential still in use and cannot be deleted.")

    return redirect(url_for("credential_bp.credential_index"))

@credential_bp.route("/add", methods=["POST"])
@login_required
def credential_add_post():
    _id = int(request.form.get("id", "-1"))
    service_id = request.form.get("service", None)
    user_name = request.form.get("user_name", "")
    password = request.form.get("password", "")
    if not user_name or not password:
        flash("Both user name and password are required.")
        return render_template("credential-add.html",
                               user_name=user_name,
                               service_id=service_id,
                               password=password)

    print(service_id)
    service = Service.get(Service.id == service_id)
    subsonic = subsonic_credentials_url_args(user_name, password, service.url)
    try:
        if _id >= 1:
            credential = Credential.get(id=_id)
            credential.service = service_id
            credential.user_name = user_name
            credential.salt = subsonic["salt"]
            credential.token = subsonic["token"]
        else:
            credential = Credential.create(service=service,
                                           user_name=user_name,
                                           salt=subsonic["salt"],
                                           token=subsonic["token"])

        credential.save()
    except peewee.IntegrityError as err:
        flash("Bummer dude.")
        return render_template("credential-add.html", user_name=user_name, service=service, password=password)

    return redirect(url_for("credential_bp.credential_index"))

@credential_bp.route("/list", methods=["GET"])
@login_required
def credential_list():
    credentials = Credential.select()
    return render_template("component/credential-list.html", credentials=credentials)

def load_credential(user):
    credential = Credential.select().first()
    service = Service.get(Service.id == credential.service.id)
    session["user"]["subsonic_url"] = service.url
    session["user"]["subsonic_user"] = credential.user_name
    session["user"]["subsonic_salt"] = credential.salt
    session["user"]["subsonic_token"] = credential.token
    print(session["user"])
