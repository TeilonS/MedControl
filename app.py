"""
=============================================================================
  MEDCONTROL — Sistema de Controle de Validade de Medicamentos
  Versão 2.0 | Arquitetura Multi-Tenant
  
  Hierarquia de acesso:
    superadmin  → acesso total, gerencia redes e assinaturas
    dono_rede   → vê e edita todas as filiais da sua rede
    filial      → gerencia somente o próprio estoque
=============================================================================
"""

from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify, send_file, flash, abort)
from flask_sqlalchemy import SQLAlchemy
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
app.secret_key = os.environ.get('SECRET_KEY', 'medcontrol-dev-secret-2024')

# PostgreSQL em produção (Railway), SQLite localmente
database_url = os.environ.get('DATABASE_URL', 'sqlite:///medcontrol.db')
# Railway usa postgres:// mas SQLAlchemy precisa de postgresql://
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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
    password     = db.Column(db.String(200), nullable=False)
    perfil       = db.Column(db.String(20), default='filial')
    nome_exibir  = db.Column(db.String(150), nullable=True)
    filial_nome  = db.Column(db.String(150), nullable=True)
    rede_id      = db.Column(db.Integer, db.ForeignKey('redes.id'), nullable=True)

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
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def assinatura_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        u = Usuario.query.get(session['user_id'])
        if not u or not u.assinatura_ok: return redirect(url_for('assinatura_expirada'))
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
    elif u.is_dono: return Medicamento.query.filter_by(rede_id=u.rede_id)
    else: return Medicamento.query.filter_by(filial_id=u.id)


# =============================================================================
# AUTENTICAÇÃO
# =============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        usuario  = Usuario.query.filter_by(username=username, password=password).first()
        if usuario:
            if not usuario.assinatura_ok: return redirect(url_for('assinatura_expirada'))
            session['user_id']     = usuario.id
            session['username']    = usuario.username
            session['perfil']      = usuario.perfil
            session['nome_exibir'] = usuario.nome_exibir or usuario.username
            session['rede_id']     = usuario.rede_id
            session['filial_nome'] = usuario.filial_nome or ''
            return redirect(url_for('dashboard'))
        flash('Usuário ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/assinatura-expirada')
def assinatura_expirada():
    return render_template('expirado.html', username=session.get('username',''))


# =============================================================================
# DASHBOARD
# =============================================================================
@app.route('/')
@assinatura_required
def dashboard():
    hoje          = date.today()
    busca         = request.args.get('busca','').strip()
    status        = request.args.get('status','')
    filial_filtro = request.args.get('filial','')
    u             = get_usuario_atual()
    query         = get_medicamentos_query()

    if busca:
        query = query.filter(db.or_(
            Medicamento.nome.ilike(f'%{busca}%'),
            Medicamento.lote.ilike(f'%{busca}%'),
            Medicamento.codigo_barras.ilike(f'%{busca}%')
        ))
    if filial_filtro and (u.is_dono or u.is_superadmin):
        query = query.filter_by(filial_id=int(filial_filtro))

    medicamentos = query.order_by(Medicamento.data_validade.asc()).all()
    if status:
        medicamentos = [m for m in medicamentos if m.status == status]

    todos = get_medicamentos_query().all()
    stats = {
        'total':     len(todos),
        'vencidos':  sum(1 for m in todos if m.status=='vencido'),
        'alerta_30': sum(1 for m in todos if m.status=='alerta_30'),
        'alerta_60': sum(1 for m in todos if m.status=='alerta_60'),
        'ok':        sum(1 for m in todos if m.status=='ok'),
    }
    prejuizo   = sum(m.valor_total for m in todos if m.status=='vencido')
    valor_ok   = sum(m.valor_total for m in todos if m.status!='vencido')
    chart_data = json.dumps({
        'labels': ['Vencidos (Prejuízo)','Em estoque (Válido)'],
        'values': [round(prejuizo,2), round(valor_ok,2)],
        'colors': ['#ef4444','#10b981'],
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
@app.route('/cadastro', methods=['GET','POST'])
@assinatura_required
def cadastro():
    u = get_usuario_atual()
    filiais = []
    if u.is_dono: filiais = Usuario.query.filter_by(rede_id=u.rede_id, perfil='filial').all()
    elif u.is_superadmin: filiais = Usuario.query.filter_by(perfil='filial').all()

    if request.method == 'POST':
        if u.is_filial:
            filial_id, rede_id = u.id, u.rede_id
        else:
            filial_id = int(request.form.get('filial_id',0)) or None
            fu        = Usuario.query.get(filial_id) if filial_id else None
            rede_id   = fu.rede_id if fu else None
        med = Medicamento(
            nome=request.form['nome'].strip(),
            codigo_barras=request.form.get('codigo_barras','').strip() or None,
            fabricante=request.form.get('fabricante','').strip() or None,
            principio_ativo=request.form.get('principio_ativo','').strip() or None,
            lote=request.form['lote'].strip(),
            data_validade=datetime.strptime(request.form['data_validade'],'%Y-%m-%d').date(),
            quantidade=int(request.form['quantidade']),
            preco_unitario=float(request.form['preco_unitario'].replace(',','.')),
            origem_cadastro=request.form.get('origem_cadastro','manual'),
            filial_id=filial_id, rede_id=rede_id,
        )
        db.session.add(med)
        db.session.commit()
        flash(f'Medicamento "{med.nome}" cadastrado!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('cadastro.html', med=None, modo='novo', filiais=filiais, usuario=u)


@app.route('/editar/<int:id>', methods=['GET','POST'])
@assinatura_required
def editar(id):
    u   = get_usuario_atual()
    med = get_medicamentos_query().filter_by(id=id).first_or_404()
    filiais = []
    if u.is_dono: filiais = Usuario.query.filter_by(rede_id=u.rede_id, perfil='filial').all()
    elif u.is_superadmin: filiais = Usuario.query.filter_by(perfil='filial').all()

    if request.method == 'POST':
        med.nome            = request.form['nome'].strip()
        med.codigo_barras   = request.form.get('codigo_barras','').strip() or None
        med.fabricante      = request.form.get('fabricante','').strip() or None
        med.principio_ativo = request.form.get('principio_ativo','').strip() or None
        med.lote            = request.form['lote'].strip()
        med.data_validade   = datetime.strptime(request.form['data_validade'],'%Y-%m-%d').date()
        med.quantidade      = int(request.form['quantidade'])
        med.preco_unitario  = float(request.form['preco_unitario'].replace(',','.'))
        if not u.is_filial and request.form.get('filial_id'):
            med.filial_id = int(request.form['filial_id'])
        db.session.commit()
        flash(f'"{med.nome}" atualizado!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('cadastro.html', med=med, modo='editar', filiais=filiais, usuario=u)


@app.route('/excluir/<int:id>', methods=['POST'])
@assinatura_required
def excluir(id):
    med = get_medicamentos_query().filter_by(id=id).first_or_404()
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
    mensagem  = request.form.get('mensagem','').strip()
    categoria = request.form.get('categoria','Geral')
    username  = session.get('username','Desconhecido')
    if not mensagem:
        flash('Escreva uma mensagem antes de enviar.','warning')
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


@app.route('/admin/redes/nova', methods=['GET','POST'])
@login_required
@superadmin_required
def admin_nova_rede():
    if request.method == 'POST':
        expiracao = request.form.get('data_expiracao')
        rede = Rede(
            nome          = request.form['nome'].strip(),
            cnpj          = request.form.get('cnpj','').strip() or None,
            email_contato = request.form.get('email_contato','').strip() or None,
            telefone      = request.form.get('telefone','').strip() or None,
            plano         = request.form.get('plano','mensal'),
            data_expiracao= datetime.strptime(expiracao,'%Y-%m-%d').date() if expiracao else None,
        )
        db.session.add(rede)
        db.session.flush()
        dono = Usuario(
            username    = request.form['username_dono'].strip(),
            password    = request.form['password_dono'].strip(),
            perfil      = 'dono_rede',
            nome_exibir = request.form['nome_dono'].strip(),
            rede_id     = rede.id,
        )
        db.session.add(dono)
        db.session.commit()
        flash(f'Rede "{rede.nome}" criada! Login do dono: {dono.username}','success')
        return redirect(url_for('admin_rede_detalhe', id=rede.id))
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
    filial = Usuario(
        username    = request.form['username'].strip(),
        password    = request.form['password'].strip(),
        perfil      = 'filial',
        nome_exibir = request.form.get('nome_exibir','').strip(),
        filial_nome = request.form['filial_nome'].strip(),
        rede_id     = rede.id,
    )
    db.session.add(filial)
    db.session.commit()
    flash(f'Filial "{filial.filial_nome}" criada!','success')
    return redirect(url_for('admin_rede_detalhe', id=id))


@app.route('/admin/redes/<int:id>/renovar', methods=['POST'])
@login_required
@superadmin_required
def admin_renovar_rede(id):
    rede = Rede.query.get_or_404(id)
    dias = int(request.form.get('dias',30))
    base = max(rede.data_expiracao, date.today()) if rede.data_expiracao and rede.data_expiracao > date.today() else date.today()
    rede.data_expiracao = base + timedelta(days=dias)
    rede.ativa = True
    db.session.commit()
    flash(f'Assinatura de "{rede.nome}" renovada até {rede.data_expiracao.strftime("%d/%m/%Y")}.','success')
    return redirect(url_for('admin_rede_detalhe', id=id))


@app.route('/admin/redes/<int:id>/toggle', methods=['POST'])
@login_required
@superadmin_required
def admin_toggle_rede(id):
    rede = Rede.query.get_or_404(id)
    rede.ativa = not rede.ativa
    db.session.commit()
    flash(f'Rede "{rede.nome}" {"ativada" if rede.ativa else "bloqueada"}.','success' if rede.ativa else 'warning')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/filial/<int:id>/excluir', methods=['POST'])
@login_required
@superadmin_required
def admin_excluir_filial(id):
    filial = Usuario.query.get_or_404(id)
    rede_id = filial.rede_id
    nome = filial.filial_nome or filial.username
    Medicamento.query.filter_by(filial_id=id).update({'filial_id': None})
    db.session.delete(filial)
    db.session.commit()
    flash(f'Filial "{nome}" removida.','warning')
    return redirect(url_for('admin_rede_detalhe', id=rede_id))


# =============================================================================
# API REST
# =============================================================================
@app.route('/api/v1/medicamentos', methods=['GET'])
@login_required
def api_listar():
    status = request.args.get('status')
    meds   = get_medicamentos_query().all()
    if status: meds = [m for m in meds if m.status == status]
    return jsonify({'success':True,'total':len(meds),'data':[m.to_dict() for m in meds]})

@app.route('/api/v1/medicamentos/barcode/<codigo>', methods=['GET'])
@login_required
def api_buscar_barcode(codigo):
    med = get_medicamentos_query().filter_by(codigo_barras=codigo).first()
    if med: return jsonify({'success':True,'data':med.to_dict()})
    return jsonify({'success':False,'message':'Não encontrado'}), 404


# =============================================================================
# PDF
# =============================================================================
@app.route('/relatorio/pdf')
@assinatura_required
def gerar_pdf():
    hoje  = date.today()
    u     = get_usuario_atual()
    meds  = get_medicamentos_query().order_by(Medicamento.data_validade.asc()).all()
    titulo_extra = f' — {u.filial_nome or u.username}' if u.is_filial else (f' — {u.rede.nome}' if u.is_dono and u.rede else '')
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=2*cm, bottomMargin=2*cm)
    estilos = getSampleStyleSheet()
    ts = ParagraphStyle('T', parent=estilos['Title'], fontSize=15, textColor=colors.HexColor('#1e293b'), spaceAfter=4)
    ss = ParagraphStyle('S', parent=estilos['Normal'], fontSize=9, textColor=colors.HexColor('#64748b'), spaceAfter=12)
    el = []
    el.append(Paragraph(f'MedControl — Controle de Validade{titulo_extra}', ts))
    el.append(Paragraph(f'Relatório gerado em {hoje.strftime("%d/%m/%Y")} | {len(meds)} item(s)', ss))
    el.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0')))
    el.append(Spacer(1, 0.4*cm))
    prejuizo = sum(m.valor_total for m in meds if m.status=='vencido')
    resumo = [['Vencidos','30 dias','60 dias','OK','Prejuízo'],
              [str(sum(1 for m in meds if m.status=='vencido')),str(sum(1 for m in meds if m.status=='alerta_30')),
               str(sum(1 for m in meds if m.status=='alerta_60')),str(sum(1 for m in meds if m.status=='ok')),
               f'R$ {prejuizo:,.2f}'.replace(',','X').replace('.',',').replace('X','.')]]
    rt = Table(resumo, colWidths=[3.5*cm]*5)
    rt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1e293b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('BACKGROUND',(0,1),(0,1),colors.HexColor('#fee2e2')),('BACKGROUND',(1,1),(1,1),colors.HexColor('#ffedd5')),
        ('BACKGROUND',(2,1),(2,1),colors.HexColor('#fef9c3')),('BACKGROUND',(3,1),(3,1),colors.HexColor('#dcfce7')),
        ('BACKGROUND',(4,1),(4,1),colors.HexColor('#fee2e2')),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#e2e8f0')),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    el.append(rt)
    el.append(Spacer(1, 0.6*cm))
    SC = {'vencido':colors.HexColor('#fee2e2'),'alerta_30':colors.HexColor('#ffedd5'),
          'alerta_60':colors.HexColor('#fef9c3'),'ok':colors.HexColor('#dcfce7')}
    dados = [['#','Nome','Lote','Validade','Qtd','Preço','Total','Status']]
    et = [('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1e293b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
          ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7.5),
          ('ALIGN',(0,0),(-1,-1),'CENTER'),('ALIGN',(1,1),(1,-1),'LEFT'),
          ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#e2e8f0')),
          ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]
    for i, m in enumerate(meds, 1):
        vt = f'R$ {m.valor_total:,.2f}'.replace(',','X').replace('.',',').replace('X','.')
        pu = f'R$ {m.preco_unitario:,.2f}'.replace(',','X').replace('.',',').replace('X','.')
        dados.append([str(i),m.nome[:32],m.lote,m.data_validade.strftime('%d/%m/%Y'),str(m.quantidade),pu,vt,m.status_label])
        et.append(('BACKGROUND',(0,i),(-1,i),SC.get(m.status,colors.white)))
    tabela = Table(dados, colWidths=[0.6*cm,4.5*cm,2.2*cm,2.2*cm,1*cm,2*cm,2*cm,2.5*cm])
    tabela.setStyle(TableStyle(et))
    el.append(tabela)
    doc.build(el)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', download_name=f'relatorio_{hoje.strftime("%Y%m%d")}.pdf', as_attachment=True)


# =============================================================================
# INICIALIZAÇÃO
# =============================================================================
def seed_database():
    if Usuario.query.filter_by(perfil='superadmin').count() == 0:
        db.session.add(Usuario(
            username    = os.environ.get('ADMIN_USER','admin'),
            password    = os.environ.get('ADMIN_PASS','admin123'),
            perfil      = 'superadmin',
            nome_exibir = 'Administrador',
        ))
    if Rede.query.count() == 0:
        hoje = date.today()
        rede_demo = Rede(nome='Farmácia Demo', email_contato='demo@medcontrol.com.br',
                         plano='mensal', data_expiracao=hoje+timedelta(days=30))
        db.session.add(rede_demo)
        db.session.flush()
        dono_demo   = Usuario(username='dono_demo', password='demo123', perfil='dono_rede',
                               nome_exibir='Dono Demo', rede_id=rede_demo.id)
        filial_demo = Usuario(username='filial_demo', password='demo123', perfil='filial',
                               nome_exibir='Filial Centro', filial_nome='Unidade Centro', rede_id=rede_demo.id)
        db.session.add_all([dono_demo, filial_demo])
        db.session.flush()
        db.session.add_all([
            Medicamento(nome='Dipirona 500mg', lote='LT-001', data_validade=hoje-timedelta(days=5),
                        quantidade=20, preco_unitario=2.50, rede_id=rede_demo.id, filial_id=filial_demo.id),
            Medicamento(nome='Amoxicilina 500mg', lote='LT-002', data_validade=hoje+timedelta(days=15),
                        quantidade=50, preco_unitario=8.90, rede_id=rede_demo.id, filial_id=filial_demo.id),
            Medicamento(nome='Omeprazol 20mg', lote='LT-003', data_validade=hoje+timedelta(days=45),
                        quantidade=100, preco_unitario=12.00, rede_id=rede_demo.id, filial_id=filial_demo.id),
            Medicamento(nome='Losartana 50mg', lote='LT-004', data_validade=hoje+timedelta(days=180),
                        quantidade=200, preco_unitario=1.80, rede_id=rede_demo.id, filial_id=filial_demo.id),
        ])
    db.session.commit()


with app.app_context():
    if os.environ.get('RESET_DB') == '1':
        db.drop_all()
    db.create_all()
    seed_database()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
