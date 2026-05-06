from flask import Flask

from .routes import web


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(web)
    return app
