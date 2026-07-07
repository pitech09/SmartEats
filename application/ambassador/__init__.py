from flask import Blueprint

ambassador = Blueprint('ambassador', __name__)

from . import views
