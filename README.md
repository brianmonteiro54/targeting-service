# Targeting Service
 
Microsserviço de regras de segmentação da plataforma **ToggleMaster**, responsável por definir para quais usuários ou grupos uma feature flag será ativada.
 
## Visão Geral
 
O Targeting Service gerencia as regras de direcionamento (targeting rules) associadas às feature flags. Ele permite criar condições como "ativar flag X apenas para usuários do grupo beta" ou "liberar para 20% dos usuários da região Sul", possibilitando releases graduais e controlados.
 
## Tecnologias
 
| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.11 |
| Framework | Flask + Gunicorn |
| Banco de Dados | PostgreSQL (RDS) |
| Container | Docker (multi-stage build) |
| Orquestração | Kubernetes (EKS) |
| Registry | Amazon ECR |
| CI/CD | GitHub Actions + ArgoCD (GitOps) |
 
## Endpoints
 
| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Health check do serviço |
| `POST` | `/targeting` | Cria uma nova regra de segmentação |
| `GET` | `/targeting` | Lista todas as regras |
| `GET` | `/targeting/<id>` | Retorna uma regra específica |
| `PUT` | `/targeting/<id>` | Atualiza uma regra |
| `DELETE` | `/targeting/<id>` | Remove uma regra |
 
## Variáveis de Ambiente
 
| Variável | Descrição |
|---|---|
| `DATABASE_URL` | String de conexão PostgreSQL |
| `AUTH_SERVICE_URL` | URL do Auth Service para validação de API Keys |
 
## Pipeline CI/CD (DevSecOps)
 
O workflow do GitHub Actions executa os seguintes estágios:
 
1. **Build & Unit Test** — Instalação de dependências e execução dos testes com `pytest`
2. **Linter** — Análise estática com `flake8`
3. **Security Scan** — SAST com `bandit` + SCA com `Trivy` (bloqueia vulnerabilidades críticas)
4. **Docker Build & Push** — Build da imagem, scan com Trivy e push para o ECR
5. **GitOps Update** — Atualiza a tag da imagem no repositório `deploy-targeting-service`
 
## Deploy (GitOps)
 
O deploy segue o modelo GitOps com ArgoCD. Ao final do pipeline de CI, a tag da imagem é atualizada automaticamente no repositório [`deploy-targeting-service`](https://github.com/brianmonteiro54/deploy-targeting-service), e o ArgoCD sincroniza a mudança no cluster EKS.
 
## Executando Localmente
 
```bash
# Configurar variáveis
cp .env.example .env
 
# Instalar dependências
pip install -r requirements.txt
 
# Rodar
python app.py
```
 
## Estrutura do Projeto
 
```
├── .github/workflows/ci.yaml   # Pipeline CI/CD
├── db/init.sql                  # Script de inicialização do banco
├── tests/test_app.py            # Testes unitários
├── Dockerfile                   # Build multi-stage (Python)
├── app.py                       # Aplicação Flask
├── requirements.txt             # Dependências Python
├── requirements-test.txt        # Dependências de teste
├── setup.cfg                    # Configuração do flake8/pytest
└── README.md
```

## 📦 Pré-requisitos (Local)

* [Python](https://www.python.org/) (versão 3.9 ou superior)
* [PostgreSQL](https://www.postgresql.org/download/)
* O `auth-service` deve estar rodando.

## 🚀 Rodando Localmente

1.  **Clone o repositório** e entre na pasta `targeting-service`.

2.  **Prepare o Banco de Dados:**
    * Crie um banco de dados no seu PostgreSQL (ex: `targeting_db`).
    * Execute o script `db/init.sql` para criar a tabela `targeting_rules`:
        ```bash
        psql -U seu_usuario -d targeting_db -f db/init.sql
        ```

3.  **Configure as Variáveis de Ambiente:**
    Crie um arquivo chamado `.env` na raiz desta pasta (`targeting-service/`) com o seguinte conteúdo:
    ```.env
    # String de conexão do seu banco de dados PostgreSQL
    DATABASE_URL="postgres://SEU_USUARIO:SUA_SENHA@localhost:5432/targeting_db"
    
    # Porta que este serviço (targeting-service) irá rodar
    PORT="8003"
    
    # URL do auth-service (que deve estar rodando na porta 8001)
    AUTH_SERVICE_URL="http://localhost:8001"
    ```

4.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Inicie o Serviço:**
    ```bash
    gunicorn --bind 0.0.0.0:8003 app:app
    ```
    O servidor estará rodando em `http://localhost:8003`.

## 🧪 Testando os Endpoints

Lembre-se de obter sua `SUA_CHAVE_API` no `auth-service` (veja o README do `flag-service`).

**1. Verifique a Saúde (Health Check):**
```bash
curl http://localhost:8003/health
```
Saída esperada: `{"status":"ok"}`

**2. Crie uma nova Regra de Segmentação:** Vamos criar uma regra para a flag enable-new-dashboard (que você criou no flag-service). Esta regra fará a flag aparecer para 50% dos usuários.
```bash
curl -X POST http://localhost:8003/rules \
-H "Content-Type: application/json" \
-H "Authorization: Bearer SUA_CHAVE_API" \
-d '{
    "flag_name": "enable-new-dashboard",
    "is_enabled": true,
    "rules": {
        "type": "PERCENTAGE",
        "value": 50
    }
}'
```
Saída esperada: (Um JSON com os dados da regra criada).

**3. Busque a Regra que você criou:**
```bash
curl http://localhost:8003/rules/enable-new-dashboard \
-H "Authorization: Bearer SUA_CHAVE_API"
```
Saída esperada: (O JSON da regra que você acabou de criar).

**4. Atualize a Regra (mude para 75%):**
```bash
curl -X PUT http://localhost:8003/rules/enable-new-dashboard \
-H "Content-Type: application/json" \
-H "Authorization: Bearer SUA_CHAVE_API" \
-d '{
    "rules": {
        "type": "PERCENTAGE",
        "value": 75
    }
}'
```
Saída esperada: (O JSON da regra atualizada, com `"value": 75`).
