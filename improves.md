# Plano de melhorias — Steely

Foco: **Segurança**, **Performance**, **Empacotamento/dependências** e **Tooling (CI/lint/testes)**.
Bug do `log` decorator (sync engole exceção vs async re-raises) e race no `intercept_stdlib` ficam fora do escopo como follow-up.

## 1. Segurança

### 1.1 Secrets fora do `build.sh` e `.env`
- `build.sh`: trocar o token PyPI hardcoded por `-p "$PYPI_TOKEN"` (env var). Deixar de assumir que o arquivo é gitignored.
- `.env`: remover o token e deixar apenas placeholders (`PYPI_TOKEN=`, etc.). Criar `.env.example` documentando as variáveis.
- **Ação manual recomendada:** rotacionar o token no PyPI — nunca foi commitado (confirmado via `git ls-files`), mas está em texto puro em 2 arquivos no disco.

### 1.2 Redigir credenciais nos FastAPI recorders
- Novo helper compartilhado `steely/fastapi/recorder/_redact.py`:
  - `SENSITIVE_HEADERS` default: `authorization`, `cookie`, `set-cookie`, `proxy-authorization`, `x-api-key`, `api-key`, `x-auth-token`.
  - `redact_body` com lista de chaves sensíveis (`password`, `token`, `secret`, `api_key`, `credit_card`, `authorization`…): valores em JSON viram `"***"`.
- Aplicar em:
  - `curl.py:157-162` (headers) e `curl.py:165-175` (body).
  - `postman.py:139-143` (headers) e `postman.py:159-174` (body).
- Novos params nos decorators: `sensitive_headers: Set[str] | None` e `redact_body: bool = True` (opt-in `keep_sensitive_headers=True` para quem realmente quer reproduzir auth no script).
- Atualizar `README.md`, `CURL_RECORDER_SUMMARY.md`, `POSTMAN_RECORDER_UPDATES.md`.

## 2. Performance

### 2.1 `time.perf_counter()` em vez de wall clock
- `cronos/__init__.py:142,146`: trocar `datetime.now()` por `time.perf_counter()`, manter formato de exibição via `timedelta(seconds=...)`.
- `scan/__init__.py:629,659`: mesmo para o elapsed em ms.
- Remover imports de `datetime` não usados.

### 2.2 Logger — lock real + sem subprocess
- Adicionar `threading.Lock` por instância (`self._lock`); envolver escrita em arquivo + print + callbacks em `log()` (`logger/__init__.py:446-492`). Isso torna a thread-safety documentada *verdadeira*.
- Trocar `os.system('clear'|'cls')` (`logger/__init__.py:400`) por sequência ANSI `\x1b[2J\x1b[H` (evita spawn de subprocess por mensagem).
- Uma chamada só de `strftime('%d-%m-%Y %H:%M:%S')` e derivar `current_date` por slicing (hoje são 2 chamadas, `logger/__init__.py:405-406`).
- Corrigir docstrings/README que prometem "logging em threads separadas / non-blocking" — hoje é 100% síncrono; documentar o comportamento real.

### 2.3 Grafana Loki — cache de labels
- `grafana/__init__.py:244-251`: cachear `(level, owner, app) → (key_json, labels_dict)` num dict pequeno, evitando `{**self._labels}` + `json.dumps(sort_keys=True)` por entrada.

### 2.4 `scan` — guarda barata de comparação
- `scan/__init__.py:482-491`: antes do `old_val != value`, para list/dict/set comparar `len()` primeiro (O(1)) e pular comparação profunda O(n) quando tamanhos divergem.

## 3. Empacotamento / dependências

### 3.1 `fastapi` como extra opcional (resolver contradição com o README)
- `pyproject.toml:56`: remover `"fastapi"` de `dependencies`; adicionar extra `fastapi = ["fastapi>=0.100"]`.
- `steely/__init__.py` não importa fastapi (confirmado) — `import steely` continua seguro.
- Lazy-import `Request` nos recorders (`curl.py:46`, `postman.py:44`) com erro claro estilo `ProviderNotAvailableError` se o extra não estiver instalado.
- `twine` também sai de `dependencies` (é ferramenta de publish) → vai para o grupo de dev.

### 3.2 Remover `setup.py` + versão com fonte única
- Deletar `setup.py` (build backend é hatchling via pyproject; `install_requires=[[...]]` está inválido).
- Fonte única de versão: `[project] dynamic = ["version"]` + `[tool.hatch.version] path = "steely/__init__.py"`, e corrigir `__version__ = "1.0.3.5"` (hoje `1.0.3.0`, drift de 3 campos).
- Validar `uv build --wheel` após as mudanças.

## 4. Tooling — CI / lint / testes

### 4.1 Ruff + dev deps
- `pyproject.toml`: adicionar `[dependency-groups] dev = ["pytest", "pytest-asyncio", "ruff", "httpx", "websockets", "fastapi", ...]` (ou `-e .[all]`).
- `[tool.ruff]`: line-length 100, target py39, selecionar `E,F,I,UP,B,SIM`.
- Rodar `uv run ruff check` e corrigir violações existentes (volume moderado — 6.8k linhas).

### 4.2 GitHub Actions CI
- Novo `.github/workflows/ci.yml`: matrix Python 3.9–3.13, `uv sync --group dev`, então `ruff check`, `ruff format --check`, `pytest`.
- `[tool.pytest.ini_options]`: `testpaths = ["test"]`, `asyncio_mode = "auto"`.

### 4.3 Testes
- `test_logger_performance.py` usa `print` em vez de `assert` — converter para asserts reais (ou mover para `examples/benchmarks`).
- Garantir que os demais testes rodem verdes no CI.

---

## Ordem de execução sugerida

1. 3.2 (remover setup.py + versão única)
2. 3.1 (fastapi extra opcional)
3. 2.x (performance)
4. 1.x (segurança)
5. 4.x (tooling)

## Follow-up fora do escopo
- Bug do `log` decorator: wrapper sync engole exceções, wrapper async re-raises (`logger/__init__.py:962,978-980`) — comportamento divergente.
- Race no `intercept_stdlib` / monkeypatch global do `dictConfig`.
