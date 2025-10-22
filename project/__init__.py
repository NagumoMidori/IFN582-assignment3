from flask import Flask, render_template
from flask_bootstrap import Bootstrap5
from flask_mysqldb import MySQL

mysql = MySQL()

def create_app():
    app = Flask(__name__)
    app.debug = True
    app.secret_key = 'BetterSecretNeeded123'

    # MySQL configurations
    app.config['MYSQL_USER'] = 'root'
    app.config['MYSQL_PASSWORD'] = 'mysqlroot'   # <-- change to your local password
    app.config['MYSQL_DB'] = 'assessment3_group4'       
    app.config['MYSQL_HOST'] = 'localhost'
    app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

    mysql.init_app(app)
    Bootstrap5(app)

    from . import views
    app.register_blueprint(views.bp)

    #Expose delivery_cost_from_session() to Jinja templates
    from .session import delivery_cost_from_session
    app.jinja_env.globals['delivery_cost_from_session'] = delivery_cost_from_session

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template("500.html"), 500

    return app
