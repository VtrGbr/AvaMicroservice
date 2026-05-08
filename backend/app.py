from flask import Flask, request, jsonify, session, redirect, url_for, render_template,send_from_directory
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import date, datetime, timedelta
import senhaApi
import os
import json

from models import db, Usuario, Turma, Crianca, Aula, Frequencia, PlanoAula, Aviso
from oferta_service import calcular_oferta_mensal, detalhe_oferta_professor, calcular_valor_aula
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
app.secret_key = senhaApi.chaveAPi
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///projeto_igreja.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Configuração de upload
UPLOAD_FOLDER = 'uploads/planos'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Certifique-se de que a pasta existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─── Decorators de autenticação ───────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def perfil_required(*perfis):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'erro': 'Não autenticado'}), 401
            if session.get('perfil') not in perfis:
                return jsonify({'erro': 'Sem permissão'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─── Páginas HTML ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    perfil = session.get('perfil')
    if perfil == 'professor':
        return render_template('professor.html', usuario=session.get('nome'), perfil=perfil)
    elif perfil in ('coordenadora', 'admin'):
        return render_template('coordenadora.html', usuario=session.get('nome'), perfil=perfil)
    return redirect(url_for('login_page'))


# ─── Auth API ──────────────────────────────────────────────────────────────────

@app.route('/api/auth/login', methods=['POST'])
def login():
    dados = request.get_json()
    usuario = Usuario.query.filter_by(email=dados.get('email')).first()
    if not usuario or not usuario.checar_senha(dados.get('senha', '')):
        return jsonify({'erro': 'Email ou senha inválidos'}), 401
    session['user_id'] = usuario.id
    session['nome'] = usuario.nome
    session['perfil'] = usuario.perfil
    return jsonify({'usuario': usuario.to_dict()})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/auth/me')
@login_required
def me():
    usuario = Usuario.query.get(session['user_id'])
    return jsonify(usuario.to_dict())


# ─── Turmas API ────────────────────────────────────────────────────────────────

@app.route('/api/turmas')
@login_required
def listar_turmas():
    turmas = Turma.query.all()
    return jsonify([t.to_dict() for t in turmas])


@app.route('/api/turmas/<int:turma_id>')
@login_required
def get_turma(turma_id):
    turma = Turma.query.get_or_404(turma_id)
    return jsonify(turma.to_dict())


@app.route('/api/turmas', methods=['POST'])
@perfil_required('coordenadora', 'admin')
def criar_turma():
    dados = request.get_json()
    turma = Turma(
        nome=dados['nome'],
        idade_min=dados['idade_min'],
        idade_max=dados['idade_max'],
        professor_id=dados['professor_id'],
        professor_apoio_id=dados.get('professor_apoio_id')
    )
    db.session.add(turma)
    db.session.commit()
    return jsonify(turma.to_dict()), 201


@app.route('/api/turmas/<int:turma_id>', methods=['PUT'])
@perfil_required('coordenadora', 'admin')
def editar_turma(turma_id):
    turma = Turma.query.get_or_404(turma_id)
    dados = request.get_json()
    for campo in ['nome', 'idade_min', 'idade_max', 'professor_id', 'professor_apoio_id']:
        if campo in dados:
            setattr(turma, campo, dados[campo])
    db.session.commit()
    return jsonify(turma.to_dict())


# ─── Crianças API ──────────────────────────────────────────────────────────────

@app.route('/api/criancas')
@login_required
def listar_criancas():
    turma_id = request.args.get('turma_id')
    q = Crianca.query.filter_by(ativa=True)
    if turma_id:
        q = q.filter_by(turma_id=turma_id)
    return jsonify([c.to_dict() for c in q.all()])


@app.route('/api/criancas', methods=['POST'])
@perfil_required('coordenadora', 'admin')
def criar_crianca():
    dados = request.get_json()
    dn = datetime.strptime(dados['data_nascimento'], '%Y-%m-%d').date()
    crianca = Crianca(
        nome=dados['nome'],
        data_nascimento=dn,
        turma_id=dados['turma_id'],
        data_entrada_turma=date.today()
    )
    db.session.add(crianca)
    db.session.commit()
    return jsonify(crianca.to_dict()), 201


@app.route('/api/criancas/<int:crianca_id>/promover', methods=['POST'])
@perfil_required('coordenadora', 'admin')
def promover_crianca(crianca_id):
    crianca = Crianca.query.get_or_404(crianca_id)
    if not crianca.elegivel_promocao():
        return jsonify({'erro': 'Criança não elegível para promoção ainda'}), 400
    nova_num = crianca.turma_correta()
    nova_turma = Turma.query.filter_by(nome=f'Turma {nova_num}').first()
    if not nova_turma:
        return jsonify({'erro': 'Turma destino não encontrada'}), 404
    crianca.turma_id = nova_turma.id
    crianca.data_entrada_turma = date.today()
    db.session.commit()
    return jsonify({'ok': True, 'nova_turma': nova_turma.nome})


# ─── Aulas & Frequência API ───────────────────────────────────────────────────

@app.route('/api/aulas')
@login_required
def listar_aulas():
    perfil = session.get('perfil')
    user_id = session.get('user_id')
    if perfil == 'professor':
        turmas_ids = [t.id for t in Turma.query.filter(
            (Turma.professor_id == user_id) | (Turma.professor_apoio_id == user_id)
        ).all()]
        aulas = Aula.query.filter(Aula.turma_id.in_(turmas_ids)).order_by(Aula.data.desc()).limit(20).all()
    else:
        aulas = Aula.query.order_by(Aula.data.desc()).limit(50).all()
    return jsonify([a.to_dict() for a in aulas])


@app.route('/api/aulas', methods=['POST'])
@login_required
def criar_aula():
    dados = request.get_json()
    data_aula = datetime.strptime(dados['data'], '%Y-%m-%d').date()
    aula = Aula(
        turma_id=dados['turma_id'],
        data=data_aula,
        horario=dados['horario'],
        professor_responsavel_id=dados['professor_responsavel_id'],
        professor_apoio_presente_id=dados.get('professor_apoio_presente_id'),
        substituto_id=dados.get('substituto_id'),
        titular_faltou=dados.get('titular_faltou', False)
    )
    db.session.add(aula)
    db.session.flush()

    # Criar registros de frequência para todas as crianças da turma
    criancas = Crianca.query.filter_by(turma_id=dados['turma_id'], ativa=True).all()
    for crianca in criancas:
        freq = Frequencia(aula_id=aula.id, crianca_id=crianca.id, presente=False)
        db.session.add(freq)

    db.session.commit()
    return jsonify(aula.to_dict()), 201


@app.route('/api/aulas/<int:aula_id>/frequencia')
@login_required
def get_frequencia(aula_id):
    aula = Aula.query.get_or_404(aula_id)
    return jsonify({
        'aula': aula.to_dict(),
        'frequencias': [f.to_dict() for f in aula.frequencias]
    })


@app.route('/api/aulas/<int:aula_id>/frequencia', methods=['PUT'])
@login_required
def salvar_frequencia(aula_id):
    aula = Aula.query.get_or_404(aula_id)
    dados = request.get_json()  # lista de {crianca_id, presente, observacao}
    for item in dados:
        freq = Frequencia.query.filter_by(aula_id=aula_id, crianca_id=item['crianca_id']).first()
        if freq:
            freq.presente = item.get('presente', False)
            freq.observacao = item.get('observacao', '')
    db.session.commit()
    return jsonify({'ok': True, 'presentes': aula.total_presentes})


# ─── Planos de Aula API ────────────────────────────────────────────────────────

@app.route('/api/planos')
@login_required
def listar_planos():
    perfil = session.get('perfil')
    user_id = session.get('user_id')
    if perfil == 'professor':
        planos = PlanoAula.query.filter_by(professor_id=user_id).order_by(PlanoAula.criado_em.desc()).all()
    else:
        planos = PlanoAula.query.order_by(PlanoAula.criado_em.desc()).all()
    return jsonify([p.to_dict() for p in planos])

# Rota para o Coordenador/Professor baixar/ver o arquivo
@app.route('/uploads/planos/<filename>')
@login_required
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/planos', methods=['POST'])
@login_required
def criar_plano():
    # Quando há arquivos, usamos request.form em vez de request.get_json()
    dados = request.form 
    arquivo = request.files.get('arquivo')
    nome_arquivo = None

    if arquivo and allowed_file(arquivo.filename):
        filename = secure_filename(f"{datetime.now().timestamp()}_{arquivo.filename}")
        arquivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        nome_arquivo = filename

    plano = PlanoAula(
        professor_id=session['user_id'],
        turma_id=int(dados['turma_id']),
        data_aula=datetime.strptime(dados['data_aula'], '%Y-%m-%d').date(),
        tema=dados['tema'],
        eixo=dados['eixo'],
        objetivos=dados['objetivos'],
        metodologia=dados.get('metodologia', ''),
        materiais=dados.get('materiais', ''),
        status='enviado',
        arquivo_anexo=nome_arquivo # Salva o nome do arquivo
    )

    db.session.add(plano)
    db.session.commit()
    return jsonify(plano.to_dict()), 201


@app.route('/api/planos/<int:plano_id>', methods=['PUT'])
@login_required
def atualizar_plano(plano_id):
    plano = PlanoAula.query.get_or_404(plano_id)
    dados = request.get_json()
    perfil = session.get('perfil')

    if perfil == 'professor':
        for campo in ['tema', 'eixo', 'objetivos', 'metodologia', 'materiais', 'resumo_pos_aula']:
            if campo in dados:
                setattr(plano, campo, dados[campo])
    elif perfil in ('coordenadora', 'admin'):
        if 'status' in dados:
            plano.status = dados['status']
        if 'feedback_coord' in dados:
            plano.feedback_coord = dados['feedback_coord']

    db.session.commit()
    return jsonify(plano.to_dict())


# ─── Oferta API ────────────────────────────────────────────────────────────────

@app.route('/api/oferta')
@perfil_required('coordenadora', 'admin')
def oferta_mensal():
    mes = int(request.args.get('mes', date.today().month))
    ano = int(request.args.get('ano', date.today().year))
    return jsonify(calcular_oferta_mensal(mes, ano))


@app.route('/api/oferta/<int:professor_id>')
@login_required
def oferta_professor(professor_id):
    # Professor só vê a própria; coord vê todos
    if session.get('perfil') == 'professor' and session.get('user_id') != professor_id:
        return jsonify({'erro': 'Sem permissão'}), 403
    mes = int(request.args.get('mes', date.today().month))
    ano = int(request.args.get('ano', date.today().year))
    return jsonify(detalhe_oferta_professor(professor_id, mes, ano))


# ─── Avisos API ────────────────────────────────────────────────────────────────

@app.route('/api/avisos')
@login_required
def listar_avisos():
    user_id = session.get('user_id')
    avisos = Aviso.query.filter(
        (Aviso.destinatario_id == None) | (Aviso.destinatario_id == user_id)
    ).order_by(Aviso.criado_em.desc()).limit(20).all()
    return jsonify([a.to_dict() for a in avisos])


@app.route('/api/avisos', methods=['POST'])
@perfil_required('coordenadora', 'admin')
def criar_aviso():
    dados = request.get_json()
    aviso = Aviso(
        autor_id=session['user_id'],
        destinatario_id=dados.get('destinatario_id'),
        titulo=dados['titulo'],
        mensagem=dados['mensagem'],
        urgente=dados.get('urgente', False)
    )
    db.session.add(aviso)
    db.session.commit()
    return jsonify(aviso.to_dict()), 201


# ─── Professores API ───────────────────────────────────────────────────────────

@app.route('/api/professores')
@login_required
def listar_professores():
    profs = Usuario.query.filter(
        Usuario.perfil.in_(['professor', 'coordenadora'])
    ).filter_by(ativo=True).all()
    return jsonify([p.to_dict() for p in profs])


@app.route('/api/usuarios', methods=['POST'])
@perfil_required('admin', 'coordenadora')
def criar_usuario():
    dados = request.get_json()
    if Usuario.query.filter_by(email=dados['email']).first():
        return jsonify({'erro': 'Email já cadastrado'}), 400
    u = Usuario(nome=dados['nome'], email=dados['email'], perfil=dados['perfil'])
    u.set_senha(dados['senha'])
    db.session.add(u)
    db.session.commit()
    return jsonify(u.to_dict()), 201


# ─── Seed inicial ──────────────────────────────────────────────────────────────

def seed_inicial():
    if Usuario.query.count() > 0:
        return

    # Admin / Coordenadora
    coord = Usuario(nome='Coordenadora', email='coord@igreja.com', perfil='coordenadora')
    coord.set_senha('coord123')
    db.session.add(coord)

    admin = Usuario(nome='Admin', email='admin@igreja.com', perfil='admin')
    admin.set_senha('admin123')
    db.session.add(admin)

    # Professores
    profs = []
    for i, nome in enumerate(['Ana Silva', 'Carlos Souza', 'Maria Lima', 'João Pires'], 1):
        p = Usuario(nome=nome, email=f'prof{i}@igreja.com', perfil='professor')
        p.set_senha('prof123')
        db.session.add(p)
        profs.append(p)

    db.session.flush()

    # Turmas
    turmas_dados = [
        ('Turma 1', 3, 4, profs[0].id, None),
        ('Turma 2', 5, 6, profs[1].id, profs[2].id),
        ('Turma 3', 7, 8, profs[2].id, None),
        ('Turma 4', 9, 16, profs[3].id, profs[0].id),
    ]
    turmas = []
    for nome, imin, imax, pid, paid in turmas_dados:
        t = Turma(nome=nome, idade_min=imin, idade_max=imax,
                  professor_id=pid, professor_apoio_id=paid)
        db.session.add(t)
        turmas.append(t)

    db.session.flush()

    # Crianças de exemplo
    from datetime import timedelta
    import random
    nomes = ['Lucas', 'Ana', 'Pedro', 'Sofia', 'Miguel', 'Beatriz',
             'Rafael', 'Julia', 'Mateus', 'Larissa', 'Gabriel', 'Isabella']
    for i, nome in enumerate(nomes):
        t = turmas[i % 4]
        idade_media = (t.idade_min + t.idade_max) // 2
        dn = date.today().replace(year=date.today().year - idade_media)
        c = Crianca(nome=nome, data_nascimento=dn, turma_id=t.id)
        db.session.add(c)

    db.session.commit()
    print("✅ Dados iniciais criados!")
    print("   coord@igreja.com / coord123")
    print("   prof1@igreja.com / prof123")
    print("   admin@igreja.com / admin123")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_inicial()
    app.run(debug=True, port=5000)
