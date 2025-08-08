from flask import render_template
from ..forms import Set_StoreForm

from . import store


@store.app_errorhandler(404)
def page_not_found(e):
    formpharm=Set_StoreForm()
    return render_template('store/404.html', formpharm=formpharm), 404


@store.app_errorhandler(401)
def unauthorized(error):
    formpharm=Set_StoreForm()
    return render_template('store/401.html', formpharm=formpharm), 401


@store.app_errorhandler(500)
def internal_server_error(e):
    formpharm=Set_StoreForm()
    return render_template('store/500.html', formpharm=formpharm), 500
