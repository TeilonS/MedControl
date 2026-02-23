"""
=============================================================================
  SISTEMA DE CONTROLE DE VALIDADE DE MEDICAMENTOS
  Desenvolvido com Flask + SQLAlchemy + Bootstrap 5 + Chart.js
  Versão 1.0 | Pronto para integração com sistemas externos (ex: Consys)
=============================================================================
"""

from flask import (
    Flask, render_template, request, redirect, url_for, session, jsonify,
    send_file, flash,
)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
import io
import os
import json

# =============================================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# =============================================================================
app = Flask(__name__)
app.secret_key = os.environ.get(
    'SECRET_KEY', 'farmacia-med-secret-2024-change-in-prod')

# Banco de dados SQLite local
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medicamentos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =============================================================================
# MODELOS DE BANCO DE DADOS
# =============================================================================


class Medicamento(db.Model):
    """
    Modelo principal de medicamento.
    Campos extras (codigo_barras, fabricante, etc.) preparados para
    integração com sistemas externos como Consys, SNGPC, ANVISA, etc.
    """
    __tablename__ = 'medicamentos'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    # EAN-13 / EAN-8 / Code-128
    codigo_barras = db.Column(db.String(50), nullable=True, index=True)
    # Para integração futura
    fabricante = db.Column(db.String(150), nullable=True)
    # Para integração SNGPC/Consys
    principio_ativo = db.Column(db.String(200), nullable=True)
    lote = db.Column(db.String(50), nullable=False)
    data_validade = db.Column(db.Date, nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=0)
    preco_unitario = db.Column(db.Float, nullable=False, default=0.0)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    # Campo para rastrear origem do cadastro (manual, barcode,
    # api_consys, etc.)
    origem_cadastro = db.Column(db.String(50), default='manual')
    # Campos reservados para integração com sistemas externos
    # ID no sistema Consys ou similar
    codigo_externo = db.Column(db.String(100), nullable=True)
    # Flag de sincronização
    sincronizado = db.Column(db.Boolean, default=False)

    @property
    def status(self):
        """Retorna o status de validade do medicamento."""
        hoje = date.today()
        if self.data_validade < hoje:
            return 'vencido'
        elif self.data_validade <= hoje + timedelta(days=30):
            return 'alerta_30'
        elif self.data_validade <= hoje + timedelta(days=60):
            return 'alerta_60'
        return 'ok'

    @property
    def status_label(self):
        """Label legível para exibição."""
        labels = {
            'vencido':   'Vencido',
            'alerta_30': 'Vence em 30 dias',
            'alerta_60': 'Vence em 60 dias',
            'ok':        'OK'
        }
        return labels.get(self.status, 'OK')

    @property
    def valor_total(self):
        """Valor total em estoque (quantidade × preço)."""
        return self.quantidade * self.preco_unitario

    def to_dict(self):
        """Serialização para JSON — usada nas rotas de API para integrações."""
        return {
            'id':              self.id,
            'nome':            self.nome,
            'codigo_barras':   self.codigo_barras,
            'fabricante':      self.fabricante,
            'principio_ativo': self.principio_ativo,
            'lote':            self.lote,
            'data_validade':   self.data_validade.strftime('%Y-%m-%d'),
            'quantidade':      self.quantidade,
            'preco_unitario':  self.preco_unitario,
            'valor_total':     self.valor_total,
            'status':          self.status,
            'origem_cadastro': self.origem_cadastro,
            'codigo_externo':  self.codigo_externo,
            'sincronizado':    self.sincronizado,
        }


class Usuario(db.Model):
    """
    Modelo de usuário para autenticação.
    Preparado para expansão com perfis/permissões (ex: farmacêutico, auxiliar).
    """
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    # Em produção: usar hash bcrypt
    password = db.Column(db.String(200), nullable=False)
    # admin | farmaceutico | auxiliar
    perfil = db.Column(db.String(50), default='admin')


# =============================================================================
# DECORADORES DE AUTENTICAÇÃO
# =============================================================================
def login_required(f):
    """Decorator que protege rotas que exigem login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# =============================================================================
# ROTAS DE AUTENTICAÇÃO
# =============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        usuario = Usuario.query.filter_by(
            username=username, password=password).first()
        if usuario:
            session['user_id'] = usuario.id
            session['username'] = usuario.username
            session['perfil'] = usuario.perfil
            return redirect(url_for('dashboard'))
        flash('Usuário ou senha incorretos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# =============================================================================
# DASHBOARD PRINCIPAL
# =============================================================================
@app.route('/')
@login_required
def dashboard():
    """
    Dashboard com listagem filtrada, estatísticas e dados para gráfico.
    Suporta filtros por nome, lote e status.
    """
    hoje = date.today()
    busca = request.args.get('busca', '').strip()
    status = request.args.get('status', '')

    # Query base
    query = Medicamento.query

    # Filtro de busca textual
    if busca:
        query = query.filter(
            db.or_(
                Medicamento.nome.ilike(f'%{busca}%'),
                Medicamento.lote.ilike(f'%{busca}%'),
                Medicamento.codigo_barras.ilike(f'%{busca}%')
            )
        )

    medicamentos = query.order_by(Medicamento.data_validade.asc()).all()

    # Aplicar filtro de status em Python (usa o @property)
    if status:
        medicamentos = [m for m in medicamentos if m.status == status]

    # ─── Estatísticas para cards do Dashboard ───────────────────────────────
    todos = Medicamento.query.all()
    stats = {
        'total':      len(todos),
        'vencidos':   sum(1 for m in todos if m.status == 'vencido'),
        'alerta_30':  sum(1 for m in todos if m.status == 'alerta_30'),
        'alerta_60':  sum(1 for m in todos if m.status == 'alerta_60'),
        'ok':         sum(1 for m in todos if m.status == 'ok'),
    }

    # ─── Dados para gráfico de perdas (Chart.js) ────────────────────────────
    prejuizo = sum(m.valor_total for m in todos if m.status == 'vencido')
    valor_ok = sum(m.valor_total for m in todos if m.status != 'vencido')
    chart_data = {
        'labels':   ['Vencidos (Prejuízo)', 'Em estoque (Válido)'],
        'values':   [round(prejuizo, 2), round(valor_ok, 2)],
        'colors':   ['#ef4444', '#10b981'],
    }

    return render_template(
        'index.html',
        medicamentos=medicamentos,
        stats=stats,
        chart_data=json.dumps(chart_data),
        hoje=hoje,
        busca=busca,
        status_filtro=status
    )


# =============================================================================
# CRUD DE MEDICAMENTOS
# =============================================================================
@app.route('/cadastro', methods=['GET', 'POST'])
@login_required
def cadastro():
    """Formulário de cadastro de novo medicamento."""
    if request.method == 'POST':
        med = Medicamento(
            nome=request.form['nome'].strip(),
            codigo_barras=request.form.get(
                'codigo_barras', '').strip() or None,
            fabricante=request.form.get('fabricante', '').strip() or None,
            principio_ativo=request.form.get(
                'principio_ativo', '').strip() or None,
            lote=request.form['lote'].strip(),
            data_validade=datetime.strptime(
                request.form['data_validade'], '%Y-%m-%d').date(),
            quantidade=int(request.form['quantidade']),
            preco_unitario=float(
                request.form['preco_unitario'].replace(',', '.')),
            origem_cadastro=request.form.get('origem_cadastro', 'manual'),
        )
        db.session.add(med)
        db.session.commit()
        flash(f'Medicamento "{med.nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('cadastro.html', med=None, modo='novo')


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    """Edição de medicamento existente."""
    med = Medicamento.query.get_or_404(id)
    if request.method == 'POST':
        med.nome = request.form['nome'].strip()
        med.codigo_barras = request.form.get(
            'codigo_barras', '').strip() or None
        med.fabricante = request.form.get('fabricante', '').strip() or None
        med.principio_ativo = request.form.get(
            'principio_ativo', '').strip() or None
        med.lote = request.form['lote'].strip()
        med.data_validade = datetime.strptime(
            request.form['data_validade'], '%Y-%m-%d').date()
        med.quantidade = int(request.form['quantidade'])
        med.preco_unitario = float(
            request.form['preco_unitario'].replace(',', '.'))
        db.session.commit()
        flash(f'Medicamento "{med.nome}" atualizado com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('cadastro.html', med=med, modo='editar')


@app.route('/excluir/<int:id>', methods=['POST'])
@login_required
def excluir(id):
    """Exclusão de medicamento."""
    med = Medicamento.query.get_or_404(id)
    nome = med.nome
    db.session.delete(med)
    db.session.commit()
    flash(f'Medicamento "{nome}" excluído.', 'warning')
    return redirect(url_for('dashboard'))


# =============================================================================
# API REST — Integração com Sistemas Externos (Consys, SNGPC, etc.)
# =============================================================================
@app.route('/api/v1/medicamentos', methods=['GET'])
@login_required
def api_listar():
    """
    [API] Lista todos os medicamentos em formato JSON.
    Endpoint preparado para consumo por sistemas externos como Consys.
    Suporta filtro por status: ?status=vencido|alerta_30|alerta_60|ok
    """
    status = request.args.get('status')
    meds = Medicamento.query.all()
    if status:
        meds = [m for m in meds if m.status == status]
    return jsonify({
        'success': True,
        'total': len(meds),
        'data': [m.to_dict() for m in meds]
    })


@app.route('/api/v1/medicamentos/barcode/<codigo>', methods=['GET'])
@login_required
def api_buscar_barcode(codigo):
    """
    [API] Busca medicamento por código de barras.
    Útil para integração com leitores de barcode em balcões.
    """
    med = Medicamento.query.filter_by(codigo_barras=codigo).first()
    if med:
        return jsonify({'success': True, 'data': med.to_dict()})
    return jsonify({
        'success': False,
        'message': 'Medicamento não encontrado'
    }), 404


@app.route('/api/v1/medicamentos', methods=['POST'])
@login_required
def api_criar():
    """
    [API] Cria medicamento via JSON.
    Endpoint para integração de sistemas externos enviarem dados
    automaticamente. Exemplo de payload vindo do Consys:
    {
        "nome": "Dipirona 500mg",
        "codigo_barras": "7891234567890",
        "lote": "LT-2024-001",
        "data_validade": "2025-12-31",
        "quantidade": 100,
        "preco_unitario": 2.50,
        "codigo_externo": "CONSYS-001",
        "origem_cadastro": "api_consys"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Payload JSON inválido'
        }), 400
    try:
        med = Medicamento(
            nome=data['nome'],
            codigo_barras=data.get('codigo_barras'),
            fabricante=data.get('fabricante'),
            principio_ativo=data.get('principio_ativo'),
            lote=data['lote'],
            data_validade=datetime.strptime(
                data['data_validade'], '%Y-%m-%d').date(),
            quantidade=data['quantidade'],
            preco_unitario=data.get('preco_unitario', 0.0),
            origem_cadastro=data.get('origem_cadastro', 'api'),
            codigo_externo=data.get('codigo_externo'),
        )
        db.session.add(med)
        db.session.commit()
        return jsonify({
            'success': True,
            'id': med.id,
            'data': med.to_dict()
        }), 201
    except KeyError as e:
        mensagem = f'Campo obrigatório ausente: {e}'
        return jsonify({'success': False, 'message': mensagem}), 400


# =============================================================================
# GERAÇÃO DE RELATÓRIO PDF
# =============================================================================
@app.route('/relatorio/pdf')
@login_required
def gerar_pdf():
    """
    Gera relatório PDF completo com status visual e análise de prejuízo.
    Usa ReportLab para montagem de tabela formatada.
    """
    hoje = date.today()
    meds = Medicamento.query.order_by(Medicamento.data_validade.asc()).all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=2*cm,    bottomMargin=2*cm
    )

    estilos = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        'Titulo', parent=estilos['Title'],
        fontSize=16, textColor=colors.HexColor('#1e293b'),
        spaceAfter=4)
    sub_style = ParagraphStyle(
        'Sub', parent=estilos['Normal'],
        fontSize=9, textColor=colors.HexColor('#64748b'),
        spaceAfter=12)

    elementos = []

    # ─── Cabeçalho ──────────────────────────────────────────────────────────
    elementos.append(
        Paragraph('MedControl — Controle de Validade', titulo_style))
    elementos.append(Paragraph(
        f'Relatório gerado em {hoje.strftime("%d/%m/%Y")} | '
        f'Total de itens: {len(meds)}',
        sub_style
    ))
    elementos.append(HRFlowable(width="100%", thickness=1,
                     color=colors.HexColor('#e2e8f0')))
    elementos.append(Spacer(1, 0.4*cm))

    # ─── Resumo de prejuízo ─────────────────────────────────────────────────
    prejuizo = sum(m.valor_total for m in meds if m.status == 'vencido')
    resumo_data = [
        ['Vencidos', 'Próx. 30 dias', 'Próx. 60 dias', 'OK',
         'Prejuízo estimado'],
        [
            str(sum(1 for m in meds if m.status == 'vencido')),
            str(sum(1 for m in meds if m.status == 'alerta_30')),
            str(sum(1 for m in meds if m.status == 'alerta_60')),
            str(sum(1 for m in meds if m.status == 'ok')),
            f'R$ {prejuizo:,.2f}'.replace(',', 'X').replace(
                '.', ',').replace('X', '.'),
        ]
    ]
    resumo_tabela = Table(resumo_data, colWidths=[3.5*cm]*5)
    resumo_tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTSIZE',   (0, 0), (-1, -1), 8),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#fee2e2')),
        ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#ffedd5')),
        ('BACKGROUND', (2, 1), (2, 1), colors.HexColor('#fef9c3')),
        ('BACKGROUND', (3, 1), (3, 1), colors.HexColor('#dcfce7')),
        ('BACKGROUND', (4, 1), (4, 1), colors.HexColor('#fee2e2')),
        ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white]),
        ('TOPPADDING',  (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elementos.append(resumo_tabela)
    elementos.append(Spacer(1, 0.6*cm))

    # ─── Tabela principal ───────────────────────────────────────────────────
    STATUS_CORES = {
        'vencido':   colors.HexColor('#fee2e2'),
        'alerta_30': colors.HexColor('#ffedd5'),
        'alerta_60': colors.HexColor('#fef9c3'),
        'ok':        colors.HexColor('#dcfce7'),
    }

    cabecalho = ['#', 'Nome', 'Lote', 'Validade',
                 'Qtd', 'Preço Unit.', 'Total', 'Status']
    dados = [cabecalho]
    estilos_linhas = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 7.5),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN',      (1, 1), (1, -1), 'LEFT'),
        ('GRID',       (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
        ('TOPPADDING',  (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]

    for i, m in enumerate(meds, 1):
        vt = f'R$ {m.valor_total:,.2f}'.replace(
            ',', 'X').replace('.', ',').replace('X', '.')
        pu = f'R$ {m.preco_unitario:,.2f}'.replace(
            ',', 'X').replace('.', ',').replace('X', '.')
        dados.append([
            str(i), m.nome[:35], m.lote,
            m.data_validade.strftime('%d/%m/%Y'),
            str(m.quantidade), pu, vt, m.status_label
        ])
        cor = STATUS_CORES.get(m.status, colors.white)
        linha = i  # header é 0
        estilos_linhas.append(('BACKGROUND', (0, linha), (-1, linha), cor))

    tabela = Table(dados, colWidths=[
                   0.6*cm, 4.8*cm, 2.2*cm, 2.2*cm, 1*cm, 2*cm, 2*cm, 2.2*cm])
    tabela.setStyle(TableStyle(estilos_linhas))
    elementos.append(tabela)

    doc.build(elementos)
    buffer.seek(0)
    nome_arquivo = f'relatorio_validade_{hoje.strftime("%Y%m%d")}.pdf'
    return send_file(buffer, mimetype='application/pdf',
                     download_name=nome_arquivo, as_attachment=True)


# =============================================================================
# INICIALIZAÇÃO
# =============================================================================
def seed_database():
    """Popula o banco com dados de exemplo caso esteja vazio."""
    if Usuario.query.count() == 0:
        db.session.add(
            Usuario(username='admin', password='admin123', perfil='admin'))

    if Medicamento.query.count() == 0:
        hoje = date.today()
        exemplos = [
            Medicamento(
                nome='Dipirona 500mg',
                codigo_barras='7891234567890',
                fabricante='EMS',
                lote='LT-2024-001',
                data_validade=hoje - timedelta(days=5),
                quantidade=20,
                preco_unitario=2.50,
                origem_cadastro='manual'),
            Medicamento(
                nome='Amoxicilina 500mg',
                codigo_barras='7897654321098',
                fabricante='Medley',
                lote='LT-2024-002',
                data_validade=hoje + timedelta(days=15),
                quantidade=50,
                preco_unitario=8.90,
                origem_cadastro='barcode'),
            Medicamento(
                nome='Omeprazol 20mg',
                codigo_barras='7891111222333',
                fabricante='Aché',
                lote='LT-2024-003',
                data_validade=hoje + timedelta(days=45),
                quantidade=100,
                preco_unitario=12.00,
                origem_cadastro='manual'),
            Medicamento(
                nome='Losartana 50mg',
                codigo_barras='7894444555666',
                fabricante='Eurofarma',
                lote='LT-2024-004',
                data_validade=hoje + timedelta(days=180),
                quantidade=200,
                preco_unitario=1.80,
                origem_cadastro='manual'),
            Medicamento(
                nome='Metformina 850mg',
                codigo_barras='7897777888999',
                fabricante='Neo Química',
                lote='LT-2024-005',
                data_validade=hoje + timedelta(days=365),
                quantidade=150,
                preco_unitario=3.40,
                origem_cadastro='barcode'),
        ]
        db.session.add_all(exemplos)

    db.session.commit()

# Garante criação do banco em produção (Railway e Render)
with app.app_context():
    db.create_all()
    seed_database()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_database()
    app.run(debug=True, host='0.0.0.0', port=5000)
