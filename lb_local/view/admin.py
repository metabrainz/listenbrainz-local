from flask import request, redirect, url_for
from flask_admin.contrib.peewee import ModelView
from flask_login import current_user, logout_user


class UserModelView(ModelView):

    form_excluded_columns = ('user_id', 'login_id', 'access_token', 'refresh_token', 'access_token_expires_at')

    def is_accessible(self):
        try:
            return current_user.is_admin
        except AttributeError:
            return False

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("index_bp.index", next=request.url))

    def after_model_delete(self, model):
        # TODO: Revoke session for user
        logout_user()
        pass


class ServiceCredentialModelView(ModelView):

    form_excluded_columns = ('uuid', )
    can_create = False

    def is_accessible(self):
        try:
            return current_user.is_admin
        except AttributeError:
            return False

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('index_bp.index', next=request.url))
