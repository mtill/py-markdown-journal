# No 'bp = Blueprint(...)' here!

def register_routes(bp):
    """
    This function is called by the app factory.
    It receives the blueprint object created in app.py.
    """
    
    @bp.route('/login')
    def login():
        return "Login Page"

    @bp.route('/logout')
    def logout():
        return "Logout Page"

