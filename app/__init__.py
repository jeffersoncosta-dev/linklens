from flask import current_app, Blueprint, render_template
from app.config import config
def create_app(config_name="default"):
    app = Flask(__name__)

    config_class = config.get(config_name, config["default"])
    app.config.from_object(config_class)

    return app