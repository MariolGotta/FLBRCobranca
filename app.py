import os
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db, Player, Setting

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Support a DATA_DIR env var for persistent volumes (e.g. Railway, Render)
# Falls back to local 'database/' folder for development
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(BASE_DIR, 'database'))
DB_PATH = os.path.join(DATA_DIR, 'flbr.db')

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    # ── Secret Key ──────────────────────────────────────────────────────────
    secret_key = os.environ.get('SECRET_KEY', '')
    if not secret_key or secret_key == 'flbr-dev-key-mude-em-producao':
        if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('PRODUCTION'):
            raise RuntimeError(
                'SECRET_KEY não definida! Configure a variável de ambiente SECRET_KEY '
                'com um valor aleatório seguro antes de rodar em produção.'
            )
        # Dev fallback: use a stable key so sessions survive restarts
        secret_key = 'flbr-dev-key-mude-em-producao'

    app.config['SECRET_KEY'] = secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── Session cookie security ──────────────────────────────────────────────
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    # Enable Secure flag only when served over HTTPS (production)
    app.config['SESSION_COOKIE_SECURE'] = bool(os.environ.get('PRODUCTION'))

    # ── CSRF protection ──────────────────────────────────────────────────────
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour token lifetime

    # Ensure database directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    # Flask-Login setup
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Faça login para continuar.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return Player.query.get(int(user_id))

    # ── Security headers ─────────────────────────────────────────────────────
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Basic CSP: allow self + CDNs used by the app
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        return response

    # Register blueprints
    from routes.auth import auth_bp, init_limiter
    from routes.dashboard import dashboard_bp
    from routes.players import players_bp
    from routes.events import events_bp
    from routes.payments import payments_bp
    from routes.reports import reports_bp
    from routes.settings import settings_bp
    from routes.tutorial import tutorial_bp
    from routes.doctrine import doctrine_bp
    from routes.skills import skills_bp
    from routes.api import api_bp

    init_limiter(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(players_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(tutorial_bp)
    app.register_blueprint(doctrine_bp)
    app.register_blueprint(skills_bp)
    app.register_blueprint(api_bp)

    # Exempt bot API from CSRF (uses X-Bot-Token header auth instead)
    csrf.exempt(api_bp)

    with app.app_context():
        db.create_all()
        _init_settings()
        _migrate_db()

    return app


def _init_settings():
    """Initialize default settings if not present."""
    for key, value in Setting.DEFAULTS.items():
        if not Setting.query.get(key):
            db.session.add(Setting(key=key, value=value))
    db.session.commit()


def _migrate_db():
    """Add new columns to existing tables when they don't exist yet."""
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)
    existing_cols = [c['name'] for c in inspector.get_columns('players')]
    with db.engine.connect() as conn:
        if 'skills_updated_at' not in existing_cols:
            conn.execute(text('ALTER TABLE players ADD COLUMN skills_updated_at DATETIME'))
            conn.commit()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=30000)
