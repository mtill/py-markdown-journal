#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from .notesserver import create_app
import sys


if __name__ == '__main__':
    app = create_app()
    app.run(debug=False, host='127.0.0.1', port=int(sys.argv[1]) if len(sys.argv) > 1 else 5000)


