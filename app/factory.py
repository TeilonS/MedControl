import os
from flask import Flask, render_template
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from .extensions import db, csrf, limiter

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    
    # ── SENTRY MONITORING ───────────────────────────────────────────────
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    if SENTRY_DSN:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[FlaskIntegration()],
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )

    # Configurações básicas
    app.secret_key = os.environ.get('SECRET_KEY', 'dev_key')
    
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///medcontrol.db')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600

    # Inicializar extensões
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Registrar Blueprints
    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.admin import admin_bp
    from .routes.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Filtros Globais
    @app.template_filter('datefmt_ptbr')
    def datefmt_ptbr(d):
        if not d: return ""
        DIAS_PT   = ['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo']
        MESES_PT  = ['','Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                      'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
        dia_semana = DIAS_PT[d.weekday()]
        return f"{dia_semana}, {d.day:02d} de {MESES_PT[d.month]} de {d.year}"

    return app
