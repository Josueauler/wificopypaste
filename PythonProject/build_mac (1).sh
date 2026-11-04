#!/usr/bin/env bash
set -euo pipefail

# Execute este arquivo na pasta do projeto, ao lado de wifi.py.
cd "$(dirname "$0")"

APP_NAME="Wifi CopyPate"
ENTRY_SCRIPT="wifi.py"
VENV_DIR=".venv"

if [[ ! -f "$ENTRY_SCRIPT" ]]; then
  echo "Erro: não encontrei $ENTRY_SCRIPT em $(pwd)"
  echo "Coloque build_mac.sh na mesma pasta de wifi.py ou ajuste ENTRY_SCRIPT."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Erro: Python 3 não foi encontrado. Instale-o e tente novamente."
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# Ativa o ambiente virtual local do projeto.
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip

# Instala dependências listadas, se o arquivo existir.
if [[ -f "requirements.txt" ]]; then
  python -m pip install -r requirements.txt
else
  echo "Aviso: requirements.txt não existe; pulando instalação de dependências do projeto."
fi

python -m pip install --upgrade pyinstaller

# Gera um pacote em modo pasta (mais simples para depurar e incluir arquivos extras).
python -m PyInstaller \
  --clean \
  --noconfirm \
  --onedir \
  --name "$APP_NAME" \
  "$ENTRY_SCRIPT"

echo
echo "Build concluído. Saída: $(pwd)/dist/$APP_NAME"
echo "Teste o aplicativo dentro da pasta dist antes de distribuir."
