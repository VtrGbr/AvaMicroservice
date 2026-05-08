# ✝ Projeto Igreja — Sistema de Gestão de Turmas

Sistema web para gestão de turmas, frequência, planos de aula e cálculo de oferta de professores voluntários.

---

## 📦 Instalação

```bash
# 1. Entrar na pasta do backend
cd projeto-igreja/backend

# 2. Criar ambiente virtual (recomendado)
python3 -m venv venv
source venv/bin/activate       # Linux/Mac
venv\Scripts\activate          # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Rodar o sistema
python app.py
```

Acesse: **http://localhost:5000**

---

## 🔑 Usuários criados automaticamente

| Email               | Senha    | Perfil        |
|---------------------|----------|---------------|
| coord@igreja.com    | coord123 | Coordenadora  |
| prof1@igreja.com    | prof123  | Professor     |
| prof2@igreja.com    | prof123  | Professor     |
| prof3@igreja.com    | prof123  | Professor     |
| admin@igreja.com    | admin123 | Admin         |

---

## 💰 Regras de cálculo da oferta

- **Base:** R$ 30,00 por aula
- **Por criança presente:** + R$ 0,30
- **Com professor de apoio:** valor dividido igualmente (50/50)
- **Titular faltou:** sua metade vai para o substituto (titular não recebe)
- **Frequência:** 2 aulas por semana (manhã, tarde ou noite)

**Exemplo:**
- 15 crianças presentes → R$ 30 + (15 × R$ 0,30) = **R$ 34,50**
- Com apoio → cada um recebe **R$ 17,25**
- Se titular faltou e há substituto → substituto recebe **R$ 17,25**, apoio recebe **R$ 17,25**

---

## 🏗️ Estrutura do projeto

```
projeto-igreja/
├── backend/
│   ├── app.py              # Flask + todas as rotas
│   ├── models.py           # SQLAlchemy models
│   ├── oferta_service.py   # Lógica de cálculo de oferta
│   └── requirements.txt
└── frontend/
    └── templates/
        ├── login.html
        ├── professor.html
        └── coordenadora.html
```

---

## 👥 Perfis e permissões

### Professor
- ✅ Registrar frequência das crianças por aula
- 📋 Criar e enviar planos de aula
- ✍️ Adicionar resumo pós-aula
- 💰 Ver sua própria oferta do mês
- 🔔 Ver avisos da coordenadora

### Coordenadora
- 📊 Painel com visão geral
- 📋 Aprovar / solicitar revisão de planos de aula
- 💰 Calcular e visualizar oferta de todos os professores
- 👦 Cadastrar crianças e gerenciar promoção de turma
- 📢 Enviar avisos gerais ou individuais
- 🏫 Gerenciar turmas e professor de apoio
- 👤 Cadastrar novos usuários

---

## 🔄 Promoção automática de turma

As crianças são promovidas automaticamente após:
1. Completar a faixa etária da turma (ex: fazer 5 anos saindo da Turma 1)
2. Aguardar **1 mês** na turma atual

O sistema sinaliza as crianças elegíveis no painel da coordenadora.

| Turma | Faixa etária |
|-------|-------------|
| Turma 1 | 3–4 anos |
| Turma 2 | 5–6 anos |
| Turma 3 | 7–8 anos |
| Turma 4 | 9–16 anos |
# AvaMicroservice
