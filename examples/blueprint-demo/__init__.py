def register_routes(bp):

    @bp.route('/hello')
    def login():
        return "Hello world"


