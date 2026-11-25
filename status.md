## Objetivo Atual
Estabilizar segurança, contratos de rota e hot path identificados na auditoria de código antes de expandir a suíte de testes da Fase 8 (Pytest).

## Progresso
- **Infraestrutura de Testes (Fase 8 iniciada):**
  - Banco isolado `linklens_test` criado no container PostgreSQL.
  - `app/config.py` refatorado com `TestingConfig` isolada (Postgres `linklens_test`, Redis DB `/15`, `RATELIMIT_ENABLED = False`).
  - `start_click_worker(app)` protegido por `if not app.config.get("TESTING"):` no `app/__init__.py`.
  - `tests/conftest.py` criado com fixtures `app` (`session`), `client` (`function`) e `clean_env` (`function`, `autouse=True`).
  - `tests/test_health.py` (`test_health_ok`) implementado e passando (`1 passed`).
- **Correções Aplicadas:**
  - Bug de referência de `redis_conn` (`NoneType`) corrigido no `health.py`.
  - Validação HTTP/HTTPS adicionada na criação/atualização em `urls.py`.
  - Logout em `auth.py` ajustado para revogar refresh token além do access token.
  - Hash de IP em `tracker.py` migrado de SHA-256 puro para HMAC-SHA256 com segredo.

## Decisões Técnicas
- **Isolamento de testes com paridade de produção:** PostgreSQL dedicado (`linklens_test`) + Redis DB `/15` no lugar de SQLite em memória, garantindo compatibilidade com tipos UUID, `cast(..., Date)` e comportamento real de TTL/cache.
- **Triagem de auditoria:** Itens de Fase 9 (Dockerfile/entrypoint), Fase 10 (README), cache eventual de 300s no analytics e import de models no `create_app` (necessário para Alembic) foram mantidos intencionalmente fora do escopo de correção imediata.

## Próximo Passo
1. **Definir 2 pontos de escopo:**
   - Manter ou cortar URLs anônimas (`user_id` nullable) e rota de QR Code (`/urls/<slug>/qr`).
   - Escolher estratégia de GeoIP sem vazamento de IP: banco local `.mmdb` (DB-IP/GeoLite2) ou headers de reverse proxy/CDN.
2. **Executar plano de estabilização (em ordem):**
   - **Bloco 1 (Segurança):** Corrigir vazamento de cache antes de ownership (IDOR) em `analytics.py`; validar e-mail, ajustar TTL dinâmico de logout e avaliar refresh token rotation em `auth.py`; validar segredos em produção no `create_app` e definir política *fail-closed* na blocklist do Redis.
   - **Bloco 2 (Models/HATEOAS):** Ajustar `user_id` (se aplicável + migration) e corrigir nomes de endpoints no `url_for()` em `user.py` e `url.py`.
   - **Bloco 3 (Hot Path/Core):** Colocar cache-first no `redirects.py`; trocar `click_count += 1` por UPDATE SQL atômico, remover IP puro da fila Redis e eliminar chamada externa HTTP no `tracker.py`; capturar `RedisError` e reforçar `validate_url` no `shortener.py`.
   - **Bloco 4 (Contrato API):** Alinhar `urls.py` (chave `redirect:<slug>`, `extensions.redis_conn`, `PATCH`, paginação, `expires_at`/`max_clicks`/`is_active`) e `analytics.py` (rota `/urls/<slug>/analytics`, janela de 30 dias).
   - **Bloco 5 (Qualidade):** Corrigir os 16 avisos do Ruff, commitar estabilização e retomar Fase 8 (fixtures `user`/`auth_headers`/`sample_url` + testes de `health` 503, `auth`, `urls`, `redirects` e `analytics`).