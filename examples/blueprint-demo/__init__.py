from flask import Blueprint


bp = Blueprint('demo', __name__)

@bp.route('/hello')
def login():
    return "Hello world"


