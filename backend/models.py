from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    perfil = db.Column(db.String(20), nullable=False)  # 'professor', 'coordenadora', 'admin'
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def checar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def to_dict(self):
        return {'id': self.id, 'nome': self.nome, 'email': self.email, 'perfil': self.perfil}


class Turma(db.Model):
    __tablename__ = 'turmas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)   # "Turma 1", etc.
    idade_min = db.Column(db.Integer, nullable=False)
    idade_max = db.Column(db.Integer, nullable=False)
    professor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    professor_apoio_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    professor = db.relationship('Usuario', foreign_keys=[professor_id], backref='turmas_titular')
    professor_apoio = db.relationship('Usuario', foreign_keys=[professor_apoio_id], backref='turmas_apoio')
    criancas = db.relationship('Crianca', backref='turma', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'idade_min': self.idade_min,
            'idade_max': self.idade_max,
            'professor': self.professor.to_dict() if self.professor else None,
            'professor_apoio': self.professor_apoio.to_dict() if self.professor_apoio else None,
            'total_criancas': len(self.criancas)
        }


class Crianca(db.Model):
    __tablename__ = 'criancas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_nascimento = db.Column(db.Date, nullable=False)
    turma_id = db.Column(db.Integer, db.ForeignKey('turmas.id'), nullable=False)
    data_entrada_turma = db.Column(db.Date, default=date.today)
    ativa = db.Column(db.Boolean, default=True)

    @property
    def idade(self):
        hoje = date.today()
        anos = hoje.year - self.data_nascimento.year
        if (hoje.month, hoje.day) < (self.data_nascimento.month, self.data_nascimento.day):
            anos -= 1
        return anos

    def turma_correta(self):
        faixas = [(3, 4, 1), (5, 6, 2), (7, 8, 3), (9, 16, 4)]
        for imin, imax, num in faixas:
            if imin <= self.idade <= imax:
                return num
        return None

    def elegivel_promocao(self):
        turma = self.turma
        if not turma:
            return False
        if self.idade > turma.idade_max:
            dias = (date.today() - self.data_entrada_turma).days
            return dias >= 30
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'data_nascimento': self.data_nascimento.isoformat(),
            'idade': self.idade,
            'turma_id': self.turma_id,
            'turma_nome': self.turma.nome if self.turma else None,
            'elegivel_promocao': self.elegivel_promocao()
        }


class Aula(db.Model):
    """Registro de uma aula realizada num determinado dia/horário."""
    __tablename__ = 'aulas'
    id = db.Column(db.Integer, primary_key=True)
    turma_id = db.Column(db.Integer, db.ForeignKey('turmas.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)
    horario = db.Column(db.String(10), nullable=False)  # 'manha', 'tarde', 'noite'
    professor_responsavel_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    professor_apoio_presente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    # Se o titular faltou, quem assumiu
    substituto_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    titular_faltou = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    turma = db.relationship('Turma', backref='aulas')
    professor = db.relationship('Usuario', foreign_keys=[professor_responsavel_id])
    professor_apoio_obj = db.relationship('Usuario', foreign_keys=[professor_apoio_presente_id])
    substituto = db.relationship('Usuario', foreign_keys=[substituto_id])
    frequencias = db.relationship('Frequencia', backref='aula', lazy=True, cascade='all, delete-orphan')

    @property
    def total_presentes(self):
        return sum(1 for f in self.frequencias if f.presente)

    def to_dict(self):
        return {
            'id': self.id,
            'turma_id': self.turma_id,
            'turma_nome': self.turma.nome if self.turma else None,
            'data': self.data.isoformat(),
            'horario': self.horario,
            'professor': self.professor.to_dict() if self.professor else None,
            'substituto': self.substituto.to_dict() if self.substituto else None,
            'titular_faltou': self.titular_faltou,
            'total_presentes': self.total_presentes,
            'total_frequencias': len(self.frequencias)
        }


class Frequencia(db.Model):
    __tablename__ = 'frequencias'
    id = db.Column(db.Integer, primary_key=True)
    aula_id = db.Column(db.Integer, db.ForeignKey('aulas.id'), nullable=False)
    crianca_id = db.Column(db.Integer, db.ForeignKey('criancas.id'), nullable=False)
    presente = db.Column(db.Boolean, default=False)
    observacao = db.Column(db.String(200), nullable=True)

    crianca = db.relationship('Crianca', backref='frequencias')

    def to_dict(self):
        return {
            'id': self.id,
            'crianca_id': self.crianca_id,
            'crianca_nome': self.crianca.nome if self.crianca else None,
            'presente': self.presente,
            'observacao': self.observacao
        }


class PlanoAula(db.Model):
    __tablename__ = 'planos_aula'
    id = db.Column(db.Integer, primary_key=True)
    professor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    turma_id = db.Column(db.Integer, db.ForeignKey('turmas.id'), nullable=False)
    data_aula = db.Column(db.Date, nullable=False)
    tema = db.Column(db.String(200), nullable=False)
    eixo = db.Column(db.String(20), nullable=False)  # espiritual, socioemocional, fisico, intelectual
    objetivos = db.Column(db.Text, nullable=False)
    metodologia = db.Column(db.Text, nullable=True)
    materiais = db.Column(db.Text, nullable=True)
    resumo_pos_aula = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='enviado')  # enviado, aprovado, revisao
    feedback_coord = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    professor = db.relationship('Usuario', backref='planos')
    turma = db.relationship('Turma', backref='planos')

    def to_dict(self):
        return {
            'id': self.id,
            'professor': self.professor.to_dict() if self.professor else None,
            'turma': {'id': self.turma_id, 'nome': self.turma.nome if self.turma else None},
            'data_aula': self.data_aula.isoformat(),
            'tema': self.tema,
            'eixo': self.eixo,
            'objetivos': self.objetivos,
            'metodologia': self.metodologia,
            'materiais': self.materiais,
            'resumo_pos_aula': self.resumo_pos_aula,
            'status': self.status,
            'feedback_coord': self.feedback_coord,
            'criado_em': self.criado_em.isoformat()
        }


class Aviso(db.Model):
    __tablename__ = 'avisos'
    id = db.Column(db.Integer, primary_key=True)
    autor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)  # None = todos
    titulo = db.Column(db.String(150), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    urgente = db.Column(db.Boolean, default=False)
    lido_por = db.Column(db.Text, default='[]')  # JSON list of user IDs
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    autor = db.relationship('Usuario', foreign_keys=[autor_id], backref='avisos_enviados')
    destinatario = db.relationship('Usuario', foreign_keys=[destinatario_id])

    def to_dict(self):
        return {
            'id': self.id,
            'autor': self.autor.to_dict() if self.autor else None,
            'destinatario': self.destinatario.to_dict() if self.destinatario else None,
            'titulo': self.titulo,
            'mensagem': self.mensagem,
            'urgente': self.urgente,
            'criado_em': self.criado_em.isoformat()
        }
