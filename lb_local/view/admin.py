from flask import request, redirect, url_for
from flask_admin.contrib.peewee import ModelView
from flask_login import current_user


class UserModelView(ModelView):

    form_excluded_columns = ('user_id', 'login_id', 'access_token', 'refresh_token', 'access_token_expires_at')

    def is_accessible(self):
        return current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("index", next=request.url))

    def after_model_delete(self, model):
        # TODO: Revoke session for user
        pass


class ServiceModelView(ModelView):

    form_excluded_columns = ('uuid', )
    can_create = False

    def is_accessible(self):
        return current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('index', next=request.url))
