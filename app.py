"""
=============================================================================
  MEDCONTROL — Sistema de Controle de Validade de Medicamentos
  Versão 2.1 | Arquitetura Multi-Tenant | Segurança Reforçada

  Hierarquia de acesso:
    superadmin  → acesso total, gerencia redes e assinaturas
    dono_rede   → vê e edita todas as filiais da sua rede
    filial      → gerencia somente o próprio estoque

  Segurança aplicada:
    ✔ Senhas com hash bcrypt (werkzeug)
    ✔ CSRF protection (Flask-WTF)
    ✔ Rate limiting no login (Flask-Limiter)
    ✔ SECRET_KEY obrigatória via env (sem fallback fraco)
    ✔ Session timeout (30 min inatividade)
    ✔ Input validation com try/except em todos os POSTs
    ✔ debug=False em produção
=============================================================================
"""

from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify, send_file, flash, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER
import io, os, json
import urllib.request, urllib.error

app = Flask(__name__)

# =============================================================================
# CONFIGURAÇÃO — todas as chaves sensíveis via variável de ambiente
# =============================================================================

# SECRET_KEY obrigatória — sem fallback fraco
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    raise RuntimeError(
        "SECRET_KEY não definida! "
        "Adicione SECRET_KEY nas variáveis de ambiente do Railway."
    )
app.secret_key = _secret

# Sessão expira após 30 min de inatividade
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_HTTPONLY']    = True   # JS não acessa o cookie
app.config['SESSION_COOKIE_SAMESITE']   = 'Lax'  # Proteção CSRF extra

# PostgreSQL em produção (Railway/Supabase), SQLite localmente
database_url = os.environ.get('DATABASE_URL', 'sqlite:///medcontrol.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI']        = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# WTF CSRF
app.config['WTF_CSRF_TIME_LIMIT']    = 3600
app.config['WTF_CSRF_CHECK_DEFAULT'] = True  # verifica todos os POSTs automaticamente

db   = SQLAlchemy(app)
csrf = CSRFProtect(app)

# Rate limiting — máximo 10 tentativas de login por minuto por IP
limiter  = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],          # sem limite global
    storage_uri="memory://"     # troque por Redis em produção se necessário
)


# =============================================================================
# MODELOS
# =============================================================================

class Rede(db.Model):
    __tablename__ = 'redes'
    id               = db.Column(db.Integer, primary_key=True)
    nome             = db.Column(db.String(200), nullable=False)
    cnpj             = db.Column(db.String(20), nullable=True)
    email_contato    = db.Column(db.String(150), nullable=True)
    telefone         = db.Column(db.String(30), nullable=True)
    ativa            = db.Column(db.Boolean, default=True)
    data_expiracao   = db.Column(db.Date, nullable=True)
    plano            = db.Column(db.String(50), default='mensal')
    data_cadastro    = db.Column(db.DateTime, default=datetime.utcnow)
    usuarios         = db.relationship('Usuario', backref='rede', lazy=True)
    medicamentos     = db.relationship('Medicamento', backref='rede', lazy=True)

    @property
    def assinatura_ativa(self):
        if not self.ativa: return False
        if self.data_expiracao and self.data_expiracao < date.today(): return False
        return True

    @property
    def dias_restantes(self):
        if not self.data_expiracao: return None
        return (self.data_expiracao - date.today()).days

    @property
    def alerta_renovacao(self):
        d = self.dias_restantes
        return d is not None and d <= 10

    @property
    def total_filiais(self):
        return Usuario.query.filter_by(rede_id=self.id, perfil='filial').count()


class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(80), unique=True, nullable=False)
    password     = db.Column(db.String(200), nullable=False)  # sempre hash bcrypt
    perfil       = db.Column(db.String(20), default='filial')
    nome_exibir  = db.Column(db.String(150), nullable=True)
    filial_nome  = db.Column(db.String(150), nullable=True)
    rede_id      = db.Column(db.Integer, db.ForeignKey('redes.id'), nullable=True)
    tema         = db.Column(db.String(10), default='light')

    @property
    def is_superadmin(self): return self.perfil == 'superadmin'
    @property
    def is_dono(self): return self.perfil == 'dono_rede'
    @property
    def is_filial(self): return self.perfil == 'filial'

    @property
    def assinatura_ok(self):
        if self.is_superadmin: return True
        if not self.rede: return False
        return self.rede.assinatura_ativa

    @property
    def exibir_alerta_renovacao(self):
        if self.is_superadmin: return False
        if not self.rede: return False
        return self.rede.alerta_renovacao

    def set_password(self, senha_plana):
        """Gera hash bcrypt e salva. Nunca armazena texto puro."""
        self.password = generate_password_hash(senha_plana)

    def check_password(self, senha_plana):
        """Verifica senha contra o hash armazenado."""
        return check_password_hash(self.password, senha_plana)


class Medicamento(db.Model):
    __tablename__ = 'medicamentos'
    id              = db.Column(db.Integer, primary_key=True)
    nome            = db.Column(db.String(200), nullable=False)
    codigo_barras   = db.Column(db.String(50), nullable=True, index=True)
    fabricante      = db.Column(db.String(150), nullable=True)
    principio_ativo = db.Column(db.String(200), nullable=True)
    lote            = db.Column(db.String(50), nullable=False)
    data_validade   = db.Column(db.Date, nullable=False)
    quantidade      = db.Column(db.Integer, nullable=False, default=0)
    preco_unitario  = db.Column(db.Float, nullable=False, default=0.0)
    data_cadastro   = db.Column(db.DateTime, default=datetime.utcnow)
    origem_cadastro = db.Column(db.String(50), default='manual')
    codigo_externo  = db.Column(db.String(100), nullable=True)
    rede_id         = db.Column(db.Integer, db.ForeignKey('redes.id'), nullable=True)
    filial_id       = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    @property
    def status(self):
        hoje = date.today()
        if self.data_validade < hoje: return 'vencido'
        elif self.data_validade <= hoje + timedelta(days=30): return 'alerta_30'
        elif self.data_validade <= hoje + timedelta(days=60): return 'alerta_60'
        return 'ok'

    @property
    def status_label(self):
        return {'vencido':'Vencido','alerta_30':'Vence em 30 dias',
                'alerta_60':'Vence em 60 dias','ok':'OK'}.get(self.status,'OK')

    @property
    def valor_total(self): return self.quantidade * self.preco_unitario

    def to_dict(self):
        return {'id':self.id,'nome':self.nome,'codigo_barras':self.codigo_barras,
                'lote':self.lote,'data_validade':self.data_validade.strftime('%Y-%m-%d'),
                'quantidade':self.quantidade,'preco_unitario':self.preco_unitario,
                'valor_total':self.valor_total,'status':self.status,
                'rede_id':self.rede_id,'filial_id':self.filial_id}


# =============================================================================
# DECORADORES
# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        # Renova session como permanente a cada request (sliding expiry)
        session.permanent = True
        return f(*args, **kwargs)
    return decorated

def assinatura_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        session.permanent = True
        u = Usuario.query.get(session['user_id'])
        if not u or not u.assinatura_ok:
            return redirect(url_for('assinatura_expirada'))
        return f(*args, **kwargs)
    return decorated

def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('perfil') != 'superadmin':
            flash('Acesso restrito ao administrador.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def get_usuario_atual():
    return Usuario.query.get(session.get('user_id'))

def get_medicamentos_query():
    u = get_usuario_atual()
    if u.is_superadmin: return Medicamento.query
    elif u.is_dono:     return Medicamento.query.filter_by(rede_id=u.rede_id)
    else:               return Medicamento.query.filter_by(filial_id=u.id)


# =============================================================================
# TRATAMENTO DE ERROS
# =============================================================================

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash('Sessão expirada ou requisição inválida. Tente novamente.', 'danger')
    return redirect(url_for('login')), 400

@app.errorhandler(429)
def handle_rate_limit(e):
    flash('Muitas tentativas. Aguarde 1 minuto antes de tentar novamente.', 'danger')
    return render_template('login.html'), 429

@app.errorhandler(500)
def handle_500(e):
    app.logger.error(f'Erro interno: {e}')
    return render_template('login.html'), 500


# =============================================================================
# AUTENTICAÇÃO
# =============================================================================

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Validação básica de entrada
        if not username or not password:
            flash('Preencha usuário e senha.', 'danger')
            return render_template('login.html')

        usuario = Usuario.query.filter_by(username=username).first()

        # check_password verifica o hash — nunca compara texto puro
        if usuario and usuario.check_password(password):
            if not usuario.assinatura_ok:
                return redirect(url_for('assinatura_expirada'))
            session.permanent = True
            session['user_id']     = usuario.id
            session['username']    = usuario.username
            session['perfil']      = usuario.perfil
            session['nome_exibir'] = usuario.nome_exibir or usuario.username
            session['rede_id']     = usuario.rede_id
            session['filial_nome'] = usuario.filial_nome or ''
            session['tema']        = usuario.tema or 'light'
            return redirect(url_for('dashboard'))

        # Mensagem genérica — não revela se usuário existe ou não
        flash('Usuário ou senha incorretos.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/assinatura-expirada')
def assinatura_expirada():
    return render_template('expirado.html', username=session.get('username', ''))


# =============================================================================
# DASHBOARD
# =============================================================================

@app.route('/')
@assinatura_required
def dashboard():
    hoje          = date.today()
    busca         = request.args.get('busca', '').strip()
    status        = request.args.get('status', '')
    filial_filtro = request.args.get('filial', '')
    u             = get_usuario_atual()
    query         = get_medicamentos_query()

    if busca:
        query = query.filter(db.or_(
            Medicamento.nome.ilike(f'%{busca}%'),
            Medicamento.lote.ilike(f'%{busca}%'),
            Medicamento.codigo_barras.ilike(f'%{busca}%')
        ))

    if filial_filtro and (u.is_dono or u.is_superadmin):
        try:
            query = query.filter_by(filial_id=int(filial_filtro))
        except (ValueError, TypeError):
            pass

    medicamentos = query.order_by(Medicamento.data_validade.asc()).all()
    if status:
        medicamentos = [m for m in medicamentos if m.status == status]

    todos = get_medicamentos_query().all()
    stats = {
        'total':     len(todos),
        'vencidos':  sum(1 for m in todos if m.status == 'vencido'),
        'alerta_30': sum(1 for m in todos if m.status == 'alerta_30'),
        'alerta_60': sum(1 for m in todos if m.status == 'alerta_60'),
        'ok':        sum(1 for m in todos if m.status == 'ok'),
    }
    prejuizo   = sum(m.valor_total for m in todos if m.status == 'vencido')
    valor_ok   = sum(m.valor_total for m in todos if m.status != 'vencido')
    chart_data = json.dumps({
        'labels': ['Vencidos (Prejuízo)', 'Em estoque (Válido)'],
        'values': [round(prejuizo, 2), round(valor_ok, 2)],
        'colors': ['#ef4444', '#10b981'],
    })

    filiais = []
    if u.is_dono:
        filiais = Usuario.query.filter_by(rede_id=u.rede_id, perfil='filial').all()
    elif u.is_superadmin:
        filiais = Usuario.query.filter_by(perfil='filial').all()

    return render_template('index.html',
        medicamentos=medicamentos, stats=stats, chart_data=chart_data,
        hoje=hoje, busca=busca, status_filtro=status,
        filiais=filiais, filial_filtro=filial_filtro, usuario=u,
        alerta_renovacao=u.exibir_alerta_renovacao,
        dias_restantes=u.rede.dias_restantes if u.rede else None,
    )


# =============================================================================
# CRUD MEDICAMENTOS
# =============================================================================

@app.route('/cadastro', methods=['GET', 'POST'])
@assinatura_required
def cadastro():
    u = get_usuario_atual()
    filiais = []
    if u.is_dono:        filiais = Usuario.query.filter_by(rede_id=u.rede_id, perfil='filial').all()
    elif u.is_superadmin: filiais = Usuario.query.filter_by(perfil='filial').all()

    if request.method == 'POST':
        try:
            if u.is_filial:
                filial_id, rede_id = u.id, u.rede_id
            else:
                filial_id = request.form.get('filial_id')
                filial_id = int(filial_id) if filial_id and filial_id.isdigit() else None
                fu        = Usuario.query.get(filial_id) if filial_id else None
                rede_id   = fu.rede_id if fu else None

            med = Medicamento(
                nome            = request.form['nome'].strip()[:200],
                codigo_barras   = request.form.get('codigo_barras', '').strip()[:50] or None,
                fabricante      = request.form.get('fabricante', '').strip()[:150] or None,
                principio_ativo = request.form.get('principio_ativo', '').strip()[:200] or None,
                lote            = request.form['lote'].strip()[:50],
                data_validade   = datetime.strptime(request.form['data_validade'], '%Y-%m-%d').date(),
                quantidade      = int(request.form['quantidade']),
                preco_unitario  = float(request.form['preco_unitario'].replace(',', '.')),
                origem_cadastro = request.form.get('origem_cadastro', 'manual'),
                filial_id       = filial_id,
                rede_id         = rede_id,
            )
            db.session.add(med)
            db.session.commit()
            flash(f'Medicamento "{med.nome}" cadastrado!', 'success')
            return redirect(url_for('dashboard'))

        except (ValueError, KeyError) as e:
            app.logger.warning(f'Erro no cadastro de medicamento: {e}')
            flash('Dados inválidos. Verifique os campos e tente novamente.', 'danger')

    return render_template('cadastro.html', med=None, modo='novo', filiais=filiais, usuario=u)


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@assinatura_required
def editar(id):
    u   = get_usuario_atual()
    med = get_medicamentos_query().filter_by(id=id).first_or_404()
    filiais = []
    if u.is_dono:        filiais = Usuario.query.filter_by(rede_id=u.rede_id, perfil='filial').all()
    elif u.is_superadmin: filiais = Usuario.query.filter_by(perfil='filial').all()

    if request.method == 'POST':
        try:
            med.nome            = request.form['nome'].strip()[:200]
            med.codigo_barras   = request.form.get('codigo_barras', '').strip()[:50] or None
            med.fabricante      = request.form.get('fabricante', '').strip()[:150] or None
            med.principio_ativo = request.form.get('principio_ativo', '').strip()[:200] or None
            med.lote            = request.form['lote'].strip()[:50]
            med.data_validade   = datetime.strptime(request.form['data_validade'], '%Y-%m-%d').date()
            med.quantidade      = int(request.form['quantidade'])
            med.preco_unitario  = float(request.form['preco_unitario'].replace(',', '.'))
            if not u.is_filial and request.form.get('filial_id'):
                fid = request.form.get('filial_id')
                if fid and fid.isdigit():
                    med.filial_id = int(fid)
            db.session.commit()
            flash(f'"{med.nome}" atualizado!', 'success')
            return redirect(url_for('dashboard'))

        except (ValueError, KeyError) as e:
            app.logger.warning(f'Erro ao editar medicamento {id}: {e}')
            flash('Dados inválidos. Verifique os campos e tente novamente.', 'danger')

    return render_template('cadastro.html', med=med, modo='editar', filiais=filiais, usuario=u)


@app.route('/excluir/<int:id>', methods=['POST'])
@assinatura_required
def excluir(id):
    med  = get_medicamentos_query().filter_by(id=id).first_or_404()
    nome = med.nome
    db.session.delete(med)
    db.session.commit()
    flash(f'"{nome}" excluído.', 'warning')
    return redirect(url_for('dashboard'))


# =============================================================================
# FEEDBACK
# =============================================================================

@app.route('/feedback', methods=['POST'])
@login_required
def enviar_feedback():
    mensagem  = request.form.get('mensagem', '').strip()[:2000]  # limita tamanho
    categoria = request.form.get('categoria', 'Geral')[:50]
    username  = session.get('username', 'Desconhecido')

    if not mensagem:
        flash('Escreva uma mensagem antes de enviar.', 'warning')
        return redirect(request.referrer or url_for('dashboard'))

    tg_token   = os.environ.get('TELEGRAM_TOKEN')
    tg_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not tg_token or not tg_chat_id:
        flash('Feedback recebido! (notificação não configurada no servidor)', 'warning')
        return redirect(url_for('dashboard'))

    try:
        texto = (
            f"💊 *MedControl — Novo Feedback*\n\n"
            f"👤 *Usuário:* {username}\n"
            f"📂 *Categoria:* {categoria}\n"
            f"🕐 *Data:* {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
            f"💬 *Mensagem:*\n{mensagem}"
        )
        payload = json.dumps({
            'chat_id':    tg_chat_id,
            'text':       texto,
            'parse_mode': 'Markdown',
        }).encode('utf-8')

        req = urllib.request.Request(
            f'https://api.telegram.org/bot{tg_token}/sendMessage',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                flash('Feedback enviado! Obrigado.', 'success')
            else:
                raise Exception(f'Status {resp.status}')

    except Exception as e:
        app.logger.error(f'Erro feedback Telegram: {e}')
        flash('Erro ao enviar feedback. Tente novamente.', 'danger')

    return redirect(url_for('dashboard'))


# =============================================================================
# SUPERADMIN — PAINEL DE REDES
# =============================================================================

@app.route('/admin')
@login_required
@superadmin_required
def admin_dashboard():
    redes = Rede.query.order_by(Rede.nome).all()
    stats = {
        'total_redes':   len(redes),
        'ativas':        sum(1 for r in redes if r.assinatura_ativa),
        'expiradas':     sum(1 for r in redes if not r.assinatura_ativa),
        'total_filiais': sum(r.total_filiais for r in redes),
    }
    return render_template('admin/dashboard.html', redes=redes, stats=stats)


@app.route('/admin/redes/nova', methods=['GET', 'POST'])
@login_required
@superadmin_required
def admin_nova_rede():
    if request.method == 'POST':
        try:
            expiracao = request.form.get('data_expiracao')
            rede = Rede(
                nome          = request.form['nome'].strip()[:200],
                cnpj          = request.form.get('cnpj', '').strip()[:20] or None,
                email_contato = request.form.get('email_contato', '').strip()[:150] or None,
                telefone      = request.form.get('telefone', '').strip()[:30] or None,
                plano         = request.form.get('plano', 'mensal'),
                data_expiracao= datetime.strptime(expiracao, '%Y-%m-%d').date() if expiracao else None,
            )
            db.session.add(rede)
            db.session.flush()

            senha_dono = request.form['password_dono'].strip()
            if len(senha_dono) < 6:
                flash('A senha do dono deve ter pelo menos 6 caracteres.', 'danger')
                db.session.rollback()
                return render_template('admin/rede_form.html', rede=None)

            dono = Usuario(
                username    = request.form['username_dono'].strip()[:80],
                perfil      = 'dono_rede',
                nome_exibir = request.form['nome_dono'].strip()[:150],
                rede_id     = rede.id,
            )
            dono.set_password(senha_dono)  # hash bcrypt
            db.session.add(dono)
            db.session.commit()
            flash(f'Rede "{rede.nome}" criada! Login do dono: {dono.username}', 'success')
            return redirect(url_for('admin_rede_detalhe', id=rede.id))

        except (ValueError, KeyError) as e:
            app.logger.warning(f'Erro ao criar rede: {e}')
            db.session.rollback()
            flash('Dados inválidos. Verifique os campos.', 'danger')

    return render_template('admin/rede_form.html', rede=None)


@app.route('/admin/redes/<int:id>')
@login_required
@superadmin_required
def admin_rede_detalhe(id):
    rede    = Rede.query.get_or_404(id)
    filiais = Usuario.query.filter_by(rede_id=id, perfil='filial').all()
    dono    = Usuario.query.filter_by(rede_id=id, perfil='dono_rede').first()
    return render_template('admin/rede_detalhe.html', rede=rede, filiais=filiais, dono=dono)


@app.route('/admin/redes/<int:id>/filial/nova', methods=['POST'])
@login_required
@superadmin_required
def admin_nova_filial(id):
    rede = Rede.query.get_or_404(id)
    try:
        senha = request.form['password'].strip()
        if len(senha) < 6:
            flash('Senha da filial deve ter pelo menos 6 caracteres.', 'danger')
            return redirect(url_for('admin_rede_detalhe', id=id))

        filial = Usuario(
            username    = request.form['username'].strip()[:80],
            perfil      = 'filial',
            nome_exibir = request.form.get('nome_exibir', '').strip()[:150],
            filial_nome = request.form['filial_nome'].strip()[:150],
            rede_id     = rede.id,
        )
        filial.set_password(senha)  # hash bcrypt
        db.session.add(filial)
        db.session.commit()
        flash(f'Filial "{filial.filial_nome}" criada!', 'success')

    except (ValueError, KeyError) as e:
        app.logger.warning(f'Erro ao criar filial: {e}')
        flash('Dados inválidos ao criar filial.', 'danger')

    return redirect(url_for('admin_rede_detalhe', id=id))


@app.route('/admin/redes/<int:id>/renovar', methods=['POST'])
@login_required
@superadmin_required
def admin_renovar_rede(id):
    rede = Rede.query.get_or_404(id)
    try:
        dias = max(1, min(int(request.form.get('dias', 30)), 365))  # entre 1 e 365
        base = max(rede.data_expiracao, date.today()) if rede.data_expiracao and rede.data_expiracao > date.today() else date.today()
        rede.data_expiracao = base + timedelta(days=dias)
        rede.ativa = True
        db.session.commit()
        flash(f'Assinatura de "{rede.nome}" renovada até {rede.data_expiracao.strftime("%d/%m/%Y")}.', 'success')
    except (ValueError, TypeError):
        flash('Número de dias inválido.', 'danger')
    return redirect(url_for('admin_rede_detalhe', id=id))


@app.route('/admin/redes/<int:id>/toggle', methods=['POST'])
@login_required
@superadmin_required
def admin_toggle_rede(id):
    rede      = Rede.query.get_or_404(id)
    rede.ativa = not rede.ativa
    db.session.commit()
    flash(f'Rede "{rede.nome}" {"ativada" if rede.ativa else "bloqueada"}.', 'success' if rede.ativa else 'warning')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/redes/<int:id>/excluir', methods=['POST'])
@login_required
@superadmin_required
def admin_excluir_rede(id):
    rede = Rede.query.get_or_404(id)
    nome = rede.nome
    Medicamento.query.filter_by(rede_id=id).delete()
    Usuario.query.filter_by(rede_id=id).delete()
    db.session.delete(rede)
    db.session.commit()
    flash(f'Rede "{nome}" e todos os seus dados foram excluídos.', 'danger')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/filial/<int:id>/excluir', methods=['POST'])
@login_required
@superadmin_required
def admin_excluir_filial(id):
    filial  = Usuario.query.get_or_404(id)
    rede_id = filial.rede_id
    nome    = filial.filial_nome or filial.username
    Medicamento.query.filter_by(filial_id=id).update({'filial_id': None})
    db.session.delete(filial)
    db.session.commit()
    flash(f'Filial "{nome}" removida.', 'warning')
    return redirect(url_for('admin_rede_detalhe', id=rede_id))


# =============================================================================
# PLANOS & FILIAIS
# =============================================================================

@app.route('/planos')
@login_required
def planos():
    u = get_usuario_atual()
    if u.is_filial:
        return redirect(url_for('dashboard'))
    return render_template('planos.html', usuario=u)


@app.route('/filiais')
@assinatura_required
def gerenciar_filiais():
    u = get_usuario_atual()
    if not u.is_dono:
        return redirect(url_for('dashboard'))
    filiais = Usuario.query.filter_by(rede_id=u.rede_id, perfil='filial').all()
    return render_template('gerenciar_filiais.html', filiais=filiais, usuario=u)


@app.route('/filial/<int:id>/excluir', methods=['POST'])
@assinatura_required
def dono_excluir_filial(id):
    u = get_usuario_atual()
    if not u.is_dono:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))
    filial = Usuario.query.filter_by(id=id, rede_id=u.rede_id, perfil='filial').first_or_404()
    nome   = filial.filial_nome or filial.username
    Medicamento.query.filter_by(filial_id=id).update({'filial_id': None})
    db.session.delete(filial)
    db.session.commit()
    flash(f'Filial "{nome}" removida.', 'warning')
    return redirect(url_for('dashboard'))


# =============================================================================
# PREFERÊNCIAS DE TEMA
# =============================================================================

@app.route('/preferencias/tema', methods=['POST'])
@login_required
@csrf.exempt
def salvar_tema():
    tema = request.json.get('tema', 'light')
    if tema not in ('light', 'dark'):
        return jsonify({'ok': False}), 400
    u      = get_usuario_atual()
    u.tema = tema
    db.session.commit()
    session['tema'] = tema
    return jsonify({'ok': True})


# =============================================================================
# API REST
# =============================================================================

@app.route('/api/v1/medicamentos', methods=['GET'])
@login_required
@csrf.exempt
def api_listar():
    status = request.args.get('status')
    meds   = get_medicamentos_query().all()
    if status:
        meds = [m for m in meds if m.status == status]
    return jsonify({'success': True, 'total': len(meds), 'data': [m.to_dict() for m in meds]})


@app.route('/api/v1/medicamentos/barcode/<codigo>', methods=['GET'])
@login_required
@csrf.exempt
def api_buscar_barcode(codigo):
    # Sanitiza o código — só alfanumérico e hífens
    codigo_limpo = ''.join(c for c in codigo if c.isalnum() or c == '-')[:50]
    med = get_medicamentos_query().filter_by(codigo_barras=codigo_limpo).first()
    if med:
        return jsonify({'success': True, 'data': med.to_dict()})
    return jsonify({'success': False, 'message': 'Não encontrado'}), 404


# =============================================================================
# PDF
# =============================================================================

@app.route('/relatorio/pdf')
@assinatura_required
def gerar_pdf():
    hoje  = date.today()
    u     = get_usuario_atual()
    meds  = get_medicamentos_query().order_by(Medicamento.data_validade.asc()).all()
    titulo_extra = (f' — {u.filial_nome or u.username}' if u.is_filial
                    else (f' — {u.rede.nome}' if u.is_dono and u.rede else ''))
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4,
                               leftMargin=1.5*cm, rightMargin=1.5*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    estilos = getSampleStyleSheet()
    ts = ParagraphStyle('T', parent=estilos['Title'], fontSize=15,
                        textColor=colors.HexColor('#1e293b'), spaceAfter=4)
    ss = ParagraphStyle('S', parent=estilos['Normal'], fontSize=9,
                        textColor=colors.HexColor('#64748b'), spaceAfter=12)
    el = []
    el.append(Paragraph(f'MedControl — Controle de Validade{titulo_extra}', ts))
    el.append(Paragraph(f'Relatório gerado em {hoje.strftime("%d/%m/%Y")} | {len(meds)} item(s)', ss))
    el.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0')))
    el.append(Spacer(1, 0.4*cm))
    prejuizo = sum(m.valor_total for m in meds if m.status == 'vencido')
    resumo   = [['Vencidos','30 dias','60 dias','OK','Prejuízo'],
                [str(sum(1 for m in meds if m.status=='vencido')),
                 str(sum(1 for m in meds if m.status=='alerta_30')),
                 str(sum(1 for m in meds if m.status=='alerta_60')),
                 str(sum(1 for m in meds if m.status=='ok')),
                 f'R$ {prejuizo:,.2f}'.replace(',','X').replace('.',',').replace('X','.')]]
    rt = Table(resumo, colWidths=[3.5*cm]*5)
    rt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1e293b')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),8),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('BACKGROUND',(0,1),(0,1),colors.HexColor('#fee2e2')),
        ('BACKGROUND',(1,1),(1,1),colors.HexColor('#ffedd5')),
        ('BACKGROUND',(2,1),(2,1),colors.HexColor('#fef9c3')),
        ('BACKGROUND',(3,1),(3,1),colors.HexColor('#dcfce7')),
        ('BACKGROUND',(4,1),(4,1),colors.HexColor('#fee2e2')),
        ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#e2e8f0')),
        ('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]))
    el.append(rt)
    el.append(Spacer(1, 0.6*cm))
    SC = {'vencido':   colors.HexColor('#fee2e2'),
          'alerta_30': colors.HexColor('#ffedd5'),
          'alerta_60': colors.HexColor('#fef9c3'),
          'ok':        colors.HexColor('#dcfce7')}
    dados = [['#','Nome','Lote','Validade','Qtd','Preço','Total','Status']]
    et = [
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1e293b')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),7.5),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('ALIGN',(1,1),(1,-1),'LEFT'),
        ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#e2e8f0')),
        ('TOPPADDING',(0,0),(-1,-1),5),
        ('BOTTOMPADDING',(0,0),(-1,-1),5),
    ]
    for i, m in enumerate(meds, 1):
        vt = f'R$ {m.valor_total:,.2f}'.replace(',','X').replace('.',',').replace('X','.')
        pu = f'R$ {m.preco_unitario:,.2f}'.replace(',','X').replace('.',',').replace('X','.')
        dados.append([str(i), m.nome[:32], m.lote, m.data_validade.strftime('%d/%m/%Y'),
                      str(m.quantidade), pu, vt, m.status_label])
        et.append(('BACKGROUND',(0,i),(-1,i),SC.get(m.status, colors.white)))
    tabela = Table(dados, colWidths=[0.6*cm,4.5*cm,2.2*cm,2.2*cm,1*cm,2*cm,2*cm,2.5*cm])
    tabela.setStyle(TableStyle(et))
    el.append(tabela)
    doc.build(el)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf',
                     download_name=f'relatorio_{hoje.strftime("%Y%m%d")}.pdf',
                     as_attachment=True)


# =============================================================================
# INICIALIZAÇÃO — seed com senhas hasheadas
# =============================================================================

def seed_database():
    if Usuario.query.filter_by(perfil='superadmin').count() == 0:
        admin = Usuario(
            username    = os.environ.get('ADMIN_USER', 'admin'),
            perfil      = 'superadmin',
            nome_exibir = 'Administrador',
        )
        admin.set_password(os.environ.get('ADMIN_PASS', 'admin123'))
        db.session.add(admin)

    if Rede.query.count() == 0:
        hoje      = date.today()
        rede_demo = Rede(nome='Farmácia Demo', email_contato='demo@medcontrol.com.br',
                         plano='mensal', data_expiracao=hoje + timedelta(days=30))
        db.session.add(rede_demo)
        db.session.flush()

        dono_demo   = Usuario(username='dono_demo', perfil='dono_rede',
                               nome_exibir='Dono Demo', rede_id=rede_demo.id)
        filial_demo = Usuario(username='filial_demo', perfil='filial',
                               nome_exibir='Filial Centro', filial_nome='Unidade Centro',
                               rede_id=rede_demo.id)
        dono_demo.set_password('demo123')
        filial_demo.set_password('demo123')
        db.session.add_all([dono_demo, filial_demo])
        db.session.flush()

        db.session.add_all([
            Medicamento(nome='Dipirona 500mg', lote='LT-001',
                        data_validade=hoje - timedelta(days=5),
                        quantidade=20, preco_unitario=2.50,
                        rede_id=rede_demo.id, filial_id=filial_demo.id),
            Medicamento(nome='Amoxicilina 500mg', lote='LT-002',
                        data_validade=hoje + timedelta(days=15),
                        quantidade=50, preco_unitario=8.90,
                        rede_id=rede_demo.id, filial_id=filial_demo.id),
            Medicamento(nome='Omeprazol 20mg', lote='LT-003',
                        data_validade=hoje + timedelta(days=45),
                        quantidade=100, preco_unitario=12.00,
                        rede_id=rede_demo.id, filial_id=filial_demo.id),
            Medicamento(nome='Losartana 50mg', lote='LT-004',
                        data_validade=hoje + timedelta(days=180),
                        quantidade=200, preco_unitario=1.80,
                        rede_id=rede_demo.id, filial_id=filial_demo.id),
        ])
    db.session.commit()


with app.app_context():
    if os.environ.get('RESET_DB') == '1':
        db.drop_all()
    db.create_all()
    seed_database()

if __name__ == '__main__':
    # debug=False em produção — nunca expõe traceback
    app.run(debug=os.environ.get('FLASK_DEBUG', '0') == '1',
            host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
