#!/usr/bin/env python3

from lb_local.server import app

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=7200)
