from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db

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
    trial            = db.Column(db.Boolean, default=True)
    trial_inicio     = db.Column(db.DateTime, nullable=True)
    mp_assinatura_id = db.Column(db.String(100), nullable=True)
    mp_payer_email   = db.Column(db.String(150), nullable=True)
    token_api        = db.Column(db.String(64), nullable=True, unique=True)
    
    usuarios         = db.relationship('Usuario', backref='rede', lazy=True)
    medicamentos     = db.relationship('Medicamento', backref='rede', lazy=True)

    @property
    def em_trial(self):
        if not self.trial or not self.trial_inicio: return False
        limite = self.trial_inicio + timedelta(days=30)
        return datetime.utcnow() < limite

    @property
    def dias_trial_restantes(self):
        if not self.trial or not self.trial_inicio: return 0
        limite = self.trial_inicio + timedelta(days=30)
        restam = (limite - datetime.utcnow()).days
        return max(0, restam)

    @property
    def assinatura_ativa(self):
        if not self.ativa: return False
        if self.em_trial: return True
        if self.data_expiracao and self.data_expiracao >= date.today(): return True
        return False

    @property
    def dias_restantes(self):
        if not self.data_expiracao: return None
        return (self.data_expiracao - date.today()).days

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(80), unique=True, nullable=False)
    email        = db.Column(db.String(150), nullable=True)
    password     = db.Column(db.String(200), nullable=False)
    perfil       = db.Column(db.String(20), default='filial')
    nome_exibir  = db.Column(db.String(150), nullable=True)
    filial_nome  = db.Column(db.String(150), nullable=True)
    rede_id      = db.Column(db.Integer, db.ForeignKey('redes.id'), nullable=True)
    tema              = db.Column(db.String(10), default='light')
    termos_aceitos    = db.Column(db.Boolean, default=False, nullable=False)
    termos_aceitos_em = db.Column(db.DateTime, nullable=True)
    email_confirmado  = db.Column(db.Boolean, default=False, nullable=False)
    email_codigo      = db.Column(db.String(10), nullable=True)
    email_codigo_exp  = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)

    @property
    def is_superadmin(self): return self.perfil == 'superadmin'
    @property
    def is_dono(self): return self.perfil == 'dono_rede'
    @property
    def is_filial(self): return self.perfil == 'filial'

class Medicamento(db.Model):
    __tablename__ = 'medicamentos'
    id              = db.Column(db.Integer, primary_key=True)
    nome            = db.Column(db.String(200), nullable=False)
    fabricante      = db.Column(db.String(150), nullable=True)
    principio_ativo = db.Column(db.String(200), nullable=True)
    codigo_barras   = db.Column(db.String(50),  nullable=True)
    lote            = db.Column(db.String(100), nullable=False)
    data_validade   = db.Column(db.Date,        nullable=False)
    quantidade      = db.Column(db.Integer,     default=0)
    preco_unitario  = db.Column(db.Float,       default=0.0)
    origem_cadastro = db.Column(db.String(50),  default='manual')
    codigo_externo  = db.Column(db.String(100), nullable=True)
    rede_id         = db.Column(db.Integer, db.ForeignKey('redes.id'), nullable=True)
    filial_id       = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    @property
    def valor_total(self):
        return (self.quantidade or 0) * (self.preco_unitario or 0.0)

    @property
    def status(self):
        hoje = date.today()
        if self.data_validade < hoje: return 'vencido'
        if self.data_validade <= hoje + timedelta(days=30): return 'alerta_30'
        if self.data_validade <= hoje + timedelta(days=60): return 'alerta_60'
        return 'ok'

    @property
    def status_label(self):
        labels = {'vencido':'Vencido','alerta_30':'Vence em 30 dias','alerta_60':'Vence em 60 dias','ok':'OK'}
        return labels.get(self.status, 'Desconhecido')

class IntegracaoConsys(db.Model):
    __tablename__ = 'integracoes_consys'
    id              = db.Column(db.Integer, primary_key=True)
    rede_id         = db.Column(db.Integer, db.ForeignKey('redes.id'), unique=True, nullable=False)
    ativa           = db.Column(db.Boolean, default=False)
    base_url        = db.Column(db.String(300), nullable=True)
    api_key         = db.Column(db.String(500), nullable=True)
    cod_empresa     = db.Column(db.String(50),  nullable=True)
    ultimo_sync     = db.Column(db.DateTime,    nullable=True)
    sync_status     = db.Column(db.String(50),  default='nunca')
    sync_mensagem   = db.Column(db.String(500), nullable=True)
    criado_em       = db.Column(db.DateTime,    default=datetime.utcnow)
    atualizado_em   = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)
