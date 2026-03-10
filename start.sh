#!/bin/bash
# Startup script for production deployment (Railway, Render, etc.)
# Handles DB persistence when a volume is mounted at $DATA_DIR

set -e

DATA_DIR="${DATA_DIR:-database}"

echo "=== FLBR Corp - Iniciando servidor ==="
echo "Data dir: $DATA_DIR"

mkdir -p "$DATA_DIR"

# If the volume is empty (first deploy), copy bundled DB from the repo
if [ ! -f "$DATA_DIR/flbr.db" ]; then
    echo "Banco de dados nao encontrado no volume."
    if [ -f "database/flbr.db" ]; then
        echo "Copiando banco de dados inicial do repositorio..."
        cp database/flbr.db "$DATA_DIR/flbr.db"
        echo "OK - Banco copiado com sucesso."
    else
        echo "Criando banco de dados vazio..."
        # The app will create the DB schema on startup via db.create_all()
    fi
else
    echo "OK - Banco de dados encontrado: $DATA_DIR/flbr.db"
fi

echo "Iniciando gunicorn..."
exec gunicorn -w 2 -b "0.0.0.0:${PORT:-30000}" --timeout 120 "app:create_app()"
