"""
Script para corrigir as datas de entrada dos jogadores no banco.
'-' na planilha = jogador NÃO estava na corp naquele mês.
Primeira célula com valor diferente de '-' = mês em que entrou na corp.

Uso: python fix_join_dates.py
"""

import os
import sys
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db, Player

SRP_FILE = os.path.join(BASE_DIR, 'Lista de Membros da Corp - SRP.xlsx')

NOT_IN_CORP = {'-', '', 'none'}

MONTH_MAP = {
    'JAN': '01', 'FEV': '02', 'MAR': '03', 'ABR': '04',
    'MAI': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
    'SET': '09', 'OUT': '10', 'NOV': '11', 'DEZ': '12',
    'FEB': '02', 'APR': '04', 'MAY': '05', 'AUG': '08',
    'SEP': '09', 'OCT': '10', 'DEC': '12',
}


def parse_month_header(h):
    if not h:
        return None
    val = str(h).strip().upper()
    if '/' in val:
        parts = val.split('/')
        if len(parts) == 2:
            abbr = parts[0][:3]
            yr = parts[1]
            if abbr in MONTH_MAP:
                year = int('20' + yr) if len(yr) == 2 else int(yr)
                return f'{year:04d}-{MONTH_MAP[abbr]}'
    return None


def infer_join_date(row, month_cols):
    for col_idx, month_str in sorted(month_cols.items(), key=lambda x: x[1]):
        if col_idx < len(row) and row[col_idx] is not None:
            val = str(row[col_idx]).strip().lower()
            if val and val not in NOT_IN_CORP:
                try:
                    return datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
                except Exception:
                    pass
    return None  # can't determine


def main():
    import openpyxl

    app = create_app()
    with app.app_context():
        print("=== Corrigindo datas de entrada dos jogadores ===\n")

        wb = openpyxl.load_workbook(SRP_FILE, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        header = rows[0]
        month_cols = {}
        for i, h in enumerate(header):
            if h and i >= 5:
                parsed = parse_month_header(str(h))
                if parsed:
                    month_cols[i] = parsed

        print(f"Meses identificados: {len(month_cols)}")
        print(f"Intervalo: {min(month_cols.values())} a {max(month_cols.values())}\n")

        updated = 0
        not_found = 0
        unchanged = 0

        def safe_print(text):
            try:
                print(text)
            except UnicodeEncodeError:
                print(text.encode('ascii', errors='replace').decode('ascii'))

        for row in rows[1:]:
            if not row[1]:
                continue
            name = str(row[1]).strip()

            player = Player.query.filter_by(name=name).first()
            if not player:
                not_found += 1
                continue

            new_date = infer_join_date(row, month_cols)
            if new_date is None:
                safe_print(f"  AVISO: {name} - nao foi possivel determinar data de entrada")
                continue

            old_date = player.join_date
            if old_date != new_date:
                safe_print(f"  {name}: {old_date} -> {new_date}")
                player.join_date = new_date
                updated += 1
            else:
                unchanged += 1

        db.session.commit()

        print(f"\nResultado:")
        print(f"  Atualizados: {updated}")
        print(f"  Sem alteracao: {unchanged}")
        print(f"  Nao encontrados no banco: {not_found}")
        print("\nConcluido! Reinicie o servidor para ver as mudancas.")


if __name__ == '__main__':
    main()
