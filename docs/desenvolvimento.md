# Desenvolvimento

## Estrutura

| Arquivo | Função |
|---|---|
| `app.py` | Servidor web, rotas e início do programa |
| `automacao.py` | Laço da automação e cálculos de tempo |
| `radio.py` | Conexão com o rádio pela biblioteca `meshcore` |
| `portas.py` | Lista as portas seriais com o nome USB |
| `banco.py` | Banco SQLite e migrações |
| `versao.py` | Versão do programa |
| `static/` | Interface e ícone |
| `teste_telemetria.py` | Teste de bancada com o rádio, sem interface |
| `instalador/` | Instalador do Windows e pacote `.deb` |
| `scripts/` | Compilação, teste do programa compilado e geração de ícones |

O programa usa [meshcore](https://github.com/meshcore-dev/meshcore_py), Starlette, Uvicorn, SQLite e Leaflet.

## Rodar

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt    # Windows: .venv\Scripts\pip
.venv/bin/python app.py --dados ./dados-dev  # Windows: .venv\Scripts\python
```

Opções de `app.py`:

| Opção | Efeito |
|---|---|
| `--porta-web N` | Porta da interface. O padrão é 8790 |
| `--dados PASTA` | Pasta do banco. Use uma separada em testes |
| `--sem-navegador` | Não abre o navegador |

## Testes

```bash
python -m unittest discover -s tests -t .
```

Os testes não usam rádio. Para testar o programa compilado, sem abrir portas nem transmitir:

```bash
python scripts/testar_binario.py caminho/do/executavel
```

Ao testar com rádio, lembre que cada pedido transmite pela malha. Use só os seus nodes.

## Compilar

```bash
pip install pyinstaller
python scripts/compilar.py
```

O PyInstaller não gera binário de um sistema estando no outro. Compile em cada sistema. Depois:

```bash
# Ubuntu
bash instalador/criar_deb.sh 0.1.0

# Windows, com o Inno Setup 6 instalado
iscc /DVersao=0.1.0 instalador\windows.iss
```

Os instaladores ficam em `instalador-saida/`.

## Publicar uma versão

1. Atualize `VERSAO` em `versao.py`.
2. Inclua a seção `## [X.Y.Z] - AAAA-MM-DD` no `CHANGELOG.md`.
3. Envie a alteração e crie a tag:

```bash
git tag vX.Y.Z
git push origin main vX.Y.Z
```

O workflow `release.yml` confere a versão, roda os testes, compila, instala e desinstala em cada sistema e publica os instaladores com o `SHA256SUMS.txt`. Se algo falhar, nada é publicado.

## Contribuir

Issues e pull requests são bem-vindos. Inclua testes quando mudar a lógica de tempo, o banco ou as portas. Contribuições ficam sob a GPL-3.0.
