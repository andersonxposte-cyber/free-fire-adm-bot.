import os, json, hmac, hashlib, logging, asyncio
from datetime import datetime, timezone
from aiohttp import web, ClientSession
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=os.getenv('LOG_LEVEL','INFO'))
log=logging.getLogger('free-fire-adm')
TOKEN=os.getenv('DISCORD_TOKEN','')
WA_TOKEN=os.getenv('WHATSAPP_TOKEN','')
WA_PHONE_ID=os.getenv('WHATSAPP_PHONE_NUMBER_ID','')
WA_VERIFY=os.getenv('WHATSAPP_VERIFY_TOKEN','')
WA_APP_SECRET=os.getenv('WHATSAPP_APP_SECRET','')
WA_VERSION=os.getenv('WHATSAPP_API_VERSION','v23.0')
WA_ADMINS={x.strip().replace('+','') for x in os.getenv('WA_ADMIN_NUMBERS','').split(',') if x.strip()}
DB=os.getenv('DATABASE_PATH','data/freefire.db')
os.makedirs(os.path.dirname(DB) or '.',exist_ok=True)

import sqlite3
conn=sqlite3.connect(DB,check_same_thread=False)
conn.row_factory=sqlite3.Row
conn.executescript('''
CREATE TABLE IF NOT EXISTS players(id INTEGER PRIMARY KEY, name TEXT NOT NULL, contact TEXT UNIQUE, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tournaments(id INTEGER PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'aberto', created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, tournament_id INTEGER NOT NULL, name TEXT NOT NULL, UNIQUE(tournament_id,name), FOREIGN KEY(tournament_id) REFERENCES tournaments(id));
CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY, tournament_id INTEGER NOT NULL, team_id INTEGER NOT NULL, match_no INTEGER NOT NULL, placement INTEGER NOT NULL, kills INTEGER NOT NULL, points INTEGER NOT NULL, created TEXT NOT NULL, FOREIGN KEY(tournament_id) REFERENCES tournaments(id), FOREIGN KEY(team_id) REFERENCES teams(id));
''')
conn.commit()
def now(): return datetime.now(timezone.utc).isoformat()
def points_for(place,kills):
    placement={1:12,2:9,3:8,4:7,5:6,6:5,7:4,8:3,9:2,10:1}
    return placement.get(place,0)+kills

def current_tournament(): return conn.execute("SELECT * FROM tournaments WHERE status='aberto' ORDER BY id DESC LIMIT 1").fetchone()
def leaderboard(tid):
    return conn.execute('''SELECT teams.name, SUM(results.points) points, SUM(results.kills) kills
      FROM teams LEFT JOIN results ON results.team_id=teams.id AND results.tournament_id=teams.tournament_id
      WHERE teams.tournament_id=? GROUP BY teams.id ORDER BY points DESC,kills DESC,teams.name''',(tid,)).fetchall()
def create_tournament(name):
    cur=conn.execute('INSERT INTO tournaments(name,status,created) VALUES(?,?,?)',(name,'aberto',now())); conn.commit(); return cur.lastrowid
def register_team(tid,name):
    conn.execute('INSERT OR IGNORE INTO teams(tournament_id,name) VALUES(?,?)',(tid,name)); conn.commit()
def register_player(name,contact=None):
    if contact:
        conn.execute('INSERT INTO players(name,contact,created) VALUES(?,?,?) ON CONFLICT(contact) DO UPDATE SET name=excluded.name',(name,contact,now()))
    else: conn.execute('INSERT INTO players(name,created) VALUES(?,?)',(name,now()))
    conn.commit()
def add_result(tid,team,match,place,kills):
    row=conn.execute('SELECT id FROM teams WHERE tournament_id=? AND name=?',(tid,team)).fetchone()
    if not row: register_team(tid,team); row=conn.execute('SELECT id FROM teams WHERE tournament_id=? AND name=?',(tid,team)).fetchone()
    pts=points_for(place,kills)
    conn.execute('INSERT INTO results(tournament_id,team_id,match_no,placement,kills,points,created) VALUES(?,?,?,?,?,?,?)',(tid,row['id'],match,place,kills,pts,now())); conn.commit(); return pts

intents=discord.Intents.default()
bot=commands.Bot(command_prefix='!',intents=intents)

@bot.event
async def on_ready():
    try:
        synced=await bot.tree.sync()
        log.info('Ligado como %s | %s comandos',bot.user,len(synced))
    except Exception: log.exception('Erro ao sincronizar comandos')

@bot.tree.command(name='ajuda',description='Mostra os comandos do FREE FIRE ADM')
async def ajuda(interaction:discord.Interaction):
    await interaction.response.send_message('🏆 **FREE FIRE ADM**\n/torneio_criar nome\n/jogador nome [contacto]\n/equipa nome\n/resultado equipa partida colocacao kills\n/classificacao\n/torneios',ephemeral=True)

@bot.tree.command(name='torneio_criar',description='Cria um campeonato (administradores)')
@app_commands.checks.has_permissions(administrator=True)
async def torneio_criar(interaction:discord.Interaction,nome:str):
    tid=create_tournament(nome[:80]); await interaction.response.send_message(f'🏆 Campeonato **{nome}** criado. ID: `{tid}`')

@bot.tree.command(name='jogador',description='Regista um jogador')
@app_commands.checks.has_permissions(administrator=True)
async def jogador(interaction:discord.Interaction,nome:str,contacto:str=''):
    try: register_player(nome[:80],contacto[:40] or None); await interaction.response.send_message(f'✅ Jogador **{nome}** registado.')
    except sqlite3.IntegrityError: await interaction.response.send_message('Esse contacto já está registado.',ephemeral=True)

@bot.tree.command(name='equipa',description='Inscreve uma equipa no campeonato aberto')
@app_commands.checks.has_permissions(administrator=True)
async def equipa(interaction:discord.Interaction,nome:str):
    t=current_tournament()
    if not t: return await interaction.response.send_message('Não existe campeonato aberto.',ephemeral=True)
    register_team(t['id'],nome[:80]); await interaction.response.send_message(f'✅ Equipa **{nome}** inscrita em **{t["name"]}**.')

@bot.tree.command(name='resultado',description='Regista o resultado de uma equipa')
@app_commands.checks.has_permissions(administrator=True)
async def resultado(interaction:discord.Interaction,equipa:str,partida:app_commands.Range[int,1,99],colocacao:app_commands.Range[int,1,99],kills:app_commands.Range[int,0,999]):
    t=current_tournament()
    if not t: return await interaction.response.send_message('Não existe campeonato aberto.',ephemeral=True)
    pts=add_result(t['id'],equipa,partida,colocacao,kills)
    await interaction.response.send_message(f'📊 **{equipa}** | Partida {partida} | Posição {colocacao} | {kills} kills | **{pts} pontos**')

@bot.tree.command(name='classificacao',description='Mostra a classificação do campeonato aberto')
async def classificacao(interaction:discord.Interaction):
    t=current_tournament()
    if not t: return await interaction.response.send_message('Não existe campeonato aberto.',ephemeral=True)
    rows=leaderboard(t['id'])
    if not rows: return await interaction.response.send_message('Ainda não existem equipas/resultados.')
    lines=[f'**{i}. {r["name"]}** — {r["points"] or 0} pts | {r["kills"] or 0} kills' for i,r in enumerate(rows,1)]
    await interaction.response.send_message(f'🏆 **{t["name"]} — CLASSIFICAÇÃO**\n'+'\n'.join(lines))

@bot.tree.command(name='torneios',description='Lista campeonatos')
async def torneios(interaction:discord.Interaction):
    rows=conn.execute('SELECT * FROM tournaments ORDER BY id DESC LIMIT 10').fetchall()
    await interaction.response.send_message('\n'.join([f'#{r["id"]} — **{r["name"]}** ({r["status"]})' for r in rows]) or 'Nenhum campeonato criado.')

@bot.tree.error
async def on_app_command_error(interaction,error):
    msg='Não tens permissão para executar este comando.' if isinstance(error,app_commands.MissingPermissions) else 'Ocorreu um erro. Verifica os dados e tenta novamente.'
    if interaction.response.is_done(): await interaction.followup.send(msg,ephemeral=True)
    else: await interaction.response.send_message(msg,ephemeral=True)

async def wa_send(to,text):
    if not WA_TOKEN or not WA_PHONE_ID: log.warning('WhatsApp ainda não configurado'); return
    url=f'https://graph.facebook.com/{WA_VERSION}/{WA_PHONE_ID}/messages'
    headers={'Authorization':f'Bearer {WA_TOKEN}','Content-Type':'application/json'}
    payload={'messaging_product':'whatsapp','to':to,'type':'text','text':{'body':text[:4000]}}
    async with ClientSession() as s:
        async with s.post(url,headers=headers,json=payload) as r:
            body=await r.text()
            if r.status>=300: log.error('WhatsApp API %s: %s',r.status,body)

async def handle_wa_message(msg):
    sender=msg.get('from',''); text=(msg.get('text') or {}).get('body','').strip(); cmd=text.split()
    if not sender or not text: return
    key=cmd[0].upper()
    if key in ('AJUDA','MENU','HELP'):
        answer='🏆 FREE FIRE ADM\nCLASSIFICACAO — ver tabela\nTORNEIO — ver campeonato aberto\nREGISTAR NOME — registar jogador\nEQUIPA NOME — inscrever equipa (admin)\nRESULTADO EQUIPA PARTIDA POSICAO KILLS — (admin)'
    elif key=='TORNEIO':
        t=current_tournament(); answer=f'🏆 Campeonato: {t["name"]}' if t else 'Não existe campeonato aberto.'
    elif key=='CLASSIFICACAO':
        t=current_tournament(); rows=leaderboard(t['id']) if t else []
        answer=('🏆 '+t['name']+'\n'+'\n'.join(f'{i}. {r["name"]}: {r["points"] or 0} pts ({r["kills"] or 0} kills)' for i,r in enumerate(rows,1))) if t else 'Não existe campeonato aberto.'
    elif key=='REGISTAR' and len(cmd)>=2:
        try: register_player(' '.join(cmd[1:]),sender); answer='✅ Jogador registado com sucesso.'
        except Exception: answer='Não foi possível registar. Tenta novamente.'
    elif sender in WA_ADMINS and key=='CRIAR' and len(cmd)>=2:
        tid=create_tournament(' '.join(cmd[1:])); answer=f'🏆 Campeonato criado. ID: {tid}'
    elif sender in WA_ADMINS and key=='EQUIPA' and len(cmd)>=2:
        t=current_tournament()
        if t: register_team(t['id'],' '.join(cmd[1:])); answer='✅ Equipa inscrita.'
        else: answer='Cria primeiro um campeonato com CRIAR NOME.'
    elif sender in WA_ADMINS and key=='RESULTADO' and len(cmd)==5:
        t=current_tournament()
        try:
            if not t: raise ValueError()
            pts=add_result(t['id'],cmd[1],int(cmd[2]),int(cmd[3]),int(cmd[4])); answer=f'✅ Resultado guardado: {pts} pontos.'
        except Exception: answer='Formato: RESULTADO EQUIPA PARTIDA POSICAO KILLS'
    else: answer='Comando não reconhecido. Escreve AJUDA para ver as opções.'
    await wa_send(sender,answer)

async def webhook(request):
    if request.method=='GET':
        if request.query.get('hub.mode')=='subscribe' and hmac.compare_digest(request.query.get('hub.verify_token',''),WA_VERIFY):
            return web.Response(text=request.query.get('hub.challenge',''))
        return web.Response(status=403,text='Verificação inválida')
    raw=await request.read()
    if WA_APP_SECRET:
        signature=request.headers.get('X-Hub-Signature-256','')
        expected='sha256='+hmac.new(WA_APP_SECRET.encode(),raw,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,expected): return web.Response(status=401,text='Assinatura inválida')
    try:
        data=json.loads(raw)
        for entry in data.get('entry',[]):
            for change in entry.get('changes',[]):
                value=change.get('value',{})
                for msg in value.get('messages',[]): asyncio.create_task(handle_wa_message(msg))
    except Exception: log.exception('Webhook inválido')
    return web.Response(text='EVENT_RECEIVED')

async def start_web():
    app=web.Application(); app.router.add_route('*','/webhook',webhook); app.router.add_get('/health',lambda r:web.json_response({'status':'ok','service':'FREE FIRE ADM'}))
    runner=web.AppRunner(app); await runner.setup(); site=web.TCPSite(runner,'0.0.0.0',int(os.getenv('PORT','8080'))); await site.start(); return runner

async def main():
    if not TOKEN: raise RuntimeError('Define DISCORD_TOKEN nas variáveis de ambiente.')
    runner=await start_web()
    try: await bot.start(TOKEN)
    finally: await runner.cleanup(); await bot.close()

if __name__=='__main__': asyncio.run(main())
