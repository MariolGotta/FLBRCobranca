from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, TextContent

tutorial_bp = Blueprint('tutorial', __name__, url_prefix='/tutorial')

TUTORIAL_KEY = 'tutorial_novato'

TUTORIAL_DEFAULT = """<h5>Bem-vindos à FLBR Corp!</h5>

<p>Decidam se serão <strong>PVE</strong> ou <strong>MINERADORES</strong>.</p>

<ul>
  <li>Se forem <strong>PVE</strong>, leiam a sala
    <a href="https://discord.com/channels/623909210777976832/1250967936651493397" target="_blank">
      ⁠〔🧩〕fits-padrão
    </a>
    para escolherem a arma que usarão. Depois de ler, abra um ticket pedindo sua nave de farm para a corp.
  </li>
  <li>
    <strong>Mineradores</strong> e jogadores <strong>PVE</strong> podem ler os requisitos para a nave em
    <a href="https://discord.com/channels/623909210777976832/850043656982626336" target="_blank">
      ⁠〔👶〕projeto-novato-feliz
    </a>
  </li>
</ul>

<p>Para abrir ticket da nave é em
  <a href="https://discord.com/channels/623909210777976832/857069837352173578" target="_blank">
    ⁠〔⚒〕requisição-de-serviços
  </a>
</p>

<p>Se tiverem dúvidas, podem mandar em:</p>
<ul>
  <li><a href="https://discord.com/channels/623909210777976832/887033880752844851" target="_blank">⁠〔❔〕dúvidas</a></li>
  <li><a href="https://discord.com/channels/623909210777976832/1115712896580730961" target="_blank">〔👶〕sala-do-novato</a></li>
  <li><a href="https://discord.com/channels/623909210777976832/977936790457561108" target="_blank">〔🐻〕check-dos-novatos</a></li>
</ul>

<hr>

<h5>⚠️ Mudança no Projeto Novato Feliz</h5>
<p><strong>@Pilotos</strong> — Se não seguirem esse passo a passo, <strong>não vão ganhar nave</strong>.</p>

<ol>
  <li>Terminar o tutorial do jogo em High Sec / Low Sec.</li>
  <li>Quando estiver pronto para jogar em Null na base da corp, abrir um ticket em
    <a href="https://discord.com/channels/623909210777976832/857069837352173578" target="_blank">
      ⁠〔⚒〕requisição-de-serviços
    </a>.
  </li>
  <li>Ter os skills necessários:
    <ul>
      <li><strong>Básico de Mineração (Venture):</strong>
        <ul>
          <li>Engenharia, Comando e Defesa de Nave Industria</li>
          <li>Skill Mineração</li>
        </ul>
      </li>
      <li><strong>PVE (Cruzador):</strong>
        <ul>
          <li>Comando de Cruzador 4</li>
          <li>Engenharia de Cruzador 4</li>
          <li>Defesa de Cruzador 4</li>
          <li>Skill da Arma Média que for usar: nível 4 (podem ser mais de 1 skill por arma)</li>
          <li>De acordo com a arma escolhida, terá que ter as 2 skills de Escudo ou Blindagem no nível 4 também.</li>
        </ul>
      </li>
    </ul>
  </li>
</ol>

<div class="alert alert-warning mt-3">
  <strong>Obs.:</strong> Não adianta dar ping, mandar mensagem várias vezes ou qualquer coisa do tipo.
  Só irá receber nave quem seguir o passo a passo e mostrar que merece.
  Prazo: <strong>48 horas</strong> para entrega da nave.
</div>"""


@tutorial_bp.route('/', methods=['GET'])
@login_required
def view():
    content = TextContent.get(TUTORIAL_KEY, TUTORIAL_DEFAULT)
    row = TextContent.query.get(TUTORIAL_KEY)
    return render_template('tutorial.html',
                           content=content,
                           row=row,
                           is_admin=current_user.is_admin)


@tutorial_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('tutorial.view'))

    content = TextContent.get(TUTORIAL_KEY, TUTORIAL_DEFAULT)

    if request.method == 'POST':
        new_content = request.form.get('content', '').strip()
        TextContent.set(TUTORIAL_KEY, new_content, updated_by=current_user.name)
        flash('Tutorial atualizado com sucesso!', 'success')
        return redirect(url_for('tutorial.view'))

    return render_template('tutorial_edit.html', content=content)
