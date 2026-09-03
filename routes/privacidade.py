from flask import render_template

import db as db_module
from helpers import buscar_configuracao


def register(app):
    @app.route("/privacidade")
    def privacidade():
        db = db_module.get_db()
        return render_template("privacidade.html", config=buscar_configuracao(db))
