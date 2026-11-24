import os
from pathlib import Path

import click
from flask import Flask, jsonify, redirect, request, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message_category = "info"


def create_app(config_override=None):
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object("config.Config")
    if config_override:
        app.config.update(config_override)

    database_path = app.config["SQLALCHEMY_DATABASE_URI"]
    if database_path.startswith("sqlite:///") and ":memory:" not in database_path:
        Path(database_path.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(error="Authentication required."), 401
        return redirect(url_for("main.login", next=request.full_path))

    from backend.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from backend.routes import main

    app.register_blueprint(main)

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables and load a small, repeatable demonstration catalog."""
        from backend.seed import seed_catalog

        db.create_all()
        seed_catalog()
        click.echo("Database tables and starter catalog are ready.")

    @app.cli.command("make-admin")
    @click.argument("email")
    def make_admin_command(email):
        """Promote an existing account to administrator."""
        user = User.query.filter_by(email=email.strip().lower()).first()
        if user is None:
            raise click.ClickException("No account exists for that email.")
        user.role = "admin"
        db.session.commit()
        click.echo(f"Administrator access granted to {user.email}.")

    @app.cli.command("create-admin")
    @click.argument("email")
    @click.password_option()
    def create_admin_command(email, password):
        """Create an administrator account using a hidden password prompt."""
        if User.query.filter_by(email=email.strip().lower()).first():
            raise click.ClickException("An account already exists for that email.")
        if len(password) < 10:
            raise click.ClickException("Password must contain at least 10 characters.")
        user = User(email=email.strip().lower(), full_name="Platform Administrator", role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrator account created for {user.email}.")

    return app
