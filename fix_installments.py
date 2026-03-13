"""
Script de correção: SRP parcelado + dívidas de Outpost
=======================================================
Execute NA VPS após o deploy:  python fix_installments.py

O que faz:
  1. Lê a coluna NOV/26 (col 75) da planilha SRP procurando anotações "X/Y"
  2. Para cada jogador com anotação X/Y:
     - Cria a parcela X (NOV/26) como SRP pago  (foi pulada pelo import)
     - Cria as parcelas X+1 até Y como SRP NÃO pago (dívidas futuras mensais)
  3. Mostra jogadores COM has_outpost=True para que o Ministro revise e
     crie as dívidas de outpost históricas se necessário.

Execute UMA VEZ. Rodar mais de uma vez é seguro — o script verifica
duplicatas antes de inserir.
"""

import os, sys
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

SRP_FILE = os.path.join(BASE_DIR, 'Lista de Membros da Corp - SRP.xlsx')

# Coluna 75 = NOV/26 (a última coluna de meses da planilha)
ANNOTATION_COL  = 75
ANNOTATION_MONTH = '2026-11'   # NOV/26

def _next_month(year_month_str, n=1):
    """Retorna YYYY-MM avançado n meses."""
    y, m = map(int, year_month_str.split('-'))
    total = y * 12 + (m - 1) + n
    return f'{total // 12:04d}-{(total % 12) + 1:02d}'


def fix_installments(app):
    from models import db, Player, Debt, Setting

    try:
        import openpyxl
    except ImportError:
        print("ERRO: openpyxl não instalado. Execute: pip install openpyxl")
        sys.exit(1)

    if not os.path.exists(SRP_FILE):
        print(f"AVISO: Planilha não encontrada: {SRP_FILE}")
        print("Coloque 'Lista de Membros da Corp - SRP.xlsx' na pasta do projeto.")
        return

    wb = openpyxl.load_workbook(SRP_FILE, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    srp_price = Setting.get('srp_price')
    now = datetime.utcnow()

    created_paid   = 0
    created_future = 0
    skipped        = 0
    not_found      = 0

    print("\n=== Correção de SRP Parcelado ===\n")

    for row in rows[1:]:
        name = row[1]
        if not name:
            continue
        name = str(name).strip()

        val = row[ANNOTATION_COL] if ANNOTATION_COL < len(row) else None
        if not val:
            continue
        val = str(val).strip()

        # Verifica padrão X/Y
        if '/' not in val or not val.split('/')[0].isdigit():
            continue

        parts = val.split('/')
        if len(parts) != 2:
            continue
        try:
            current_inst = int(parts[0])
            total_inst   = int(parts[1])
        except ValueError:
            continue

        if current_inst >= total_inst:
            print(f"  {name}: {val} — já está na última ou penúltima parcela, nada a gerar.")
            continue

        player = Player.query.filter_by(name=name).first()
        if not player:
            print(f"  AVISO: Jogador '{name}' não encontrado no banco.")
            not_found += 1
            continue

        remaining = total_inst - current_inst
        print(f"  {name}: parcela {current_inst}/{total_inst} — criando {remaining} parcela(s) futura(s)...", end='')

        # ── Parcela atual (NOV/26 = installment X) ──────────────────────────
        exists_now = Debt.query.filter_by(
            player_id=player.id,
            debt_type='srp',
            month=ANNOTATION_MONTH
        ).first()

        if not exists_now:
            db.session.add(Debt(
                player_id   = player.id,
                debt_type   = 'srp',
                amount      = srp_price,
                description = f'SRP - parcela {current_inst}/{total_inst} (parcelamento)',
                month       = ANNOTATION_MONTH,
                paid        = True,
                paid_at     = now,
            ))
            created_paid += 1

        # ── Parcelas futuras (X+1 até Y) ─────────────────────────────────────
        for i in range(1, remaining + 1):
            inst_num  = current_inst + i
            inst_month = _next_month(ANNOTATION_MONTH, i)  # DEZ/26, JAN/27, …

            exists = Debt.query.filter_by(
                player_id=player.id,
                debt_type='srp',
                month=inst_month
            ).first()

            if exists:
                skipped += 1
                continue

            # Parcelas passadas (< hoje) → marcar como pago; futuras → não pago
            month_date = datetime.strptime(inst_month + '-01', '%Y-%m-%d').date()
            is_past    = month_date < date.today()

            db.session.add(Debt(
                player_id   = player.id,
                debt_type   = 'srp',
                amount      = srp_price,
                description = f'SRP - parcela {inst_num}/{total_inst} (parcelamento)',
                month       = inst_month,
                paid        = is_past,
                paid_at     = now if is_past else None,
            ))
            created_future += 1

        print(f" OK")

    db.session.commit()

    print(f"\nResumo:")
    print(f"  Parcela NOV/26 criada como paga:    {created_paid}")
    print(f"  Parcelas futuras criadas:            {created_future}")
    print(f"  Parcelas já existentes (puladas):    {skipped}")
    print(f"  Jogadores não encontrados no banco:  {not_found}")


def show_outpost_info(app):
    from models import db, Player, Debt

    print("\n=== Status de Outpost ===\n")

    players_with_outpost = Player.query.filter_by(has_outpost=True).all()
    outpost_debts = Debt.query.filter_by(debt_type='outpost').count()

    print(f"Dívidas de outpost no banco: {outpost_debts}")
    print(f"Jogadores com has_outpost=True: {len(players_with_outpost)}")

    if not players_with_outpost:
        print("""
  ATENÇÃO: Nenhum jogador tem has_outpost=True.
  A planilha SRP não possui coluna de outpost, portanto esses dados
  precisam ser configurados manualmente:

  1. Acesse /players/<id>/edit para cada jogador com outpost
     e marque o campo "Tem Outpost".

  2. Após marcar, as cobranças de outpost (250m/mês) serão
     geradas automaticamente no dia 5 de cada mês pelo Ministro.

  3. Para lançar o histórico de outpost (meses anteriores),
     use o formulário de Pagamento Manual em /payments/add.
""")
    else:
        print("Jogadores com outpost:")
        for p in players_with_outpost:
            debts = Debt.query.filter_by(player_id=p.id, debt_type='outpost').count()
            print(f"  {p.name}: {debts} dívidas de outpost")


if __name__ == '__main__':
    from app import create_app
    app = create_app()

    with app.app_context():
        fix_installments(app)
        show_outpost_info(app)

    print("\nConcluído!")
