# FREE FIRE ADM BOT — Discord + WhatsApp

Projeto inicial funcional com um único serviço Python, SQLite, bot Discord com slash commands e webhook da WhatsApp Cloud API.

## Funcionalidades
- Discord: `/ajuda`, `/torneio_criar`, `/jogador`, `/equipa`, `/resultado`, `/classificacao`, `/torneios`.
- WhatsApp: `AJUDA`, `TORNEIO`, `CLASSIFICACAO`, `REGISTAR NOME`; administradores podem usar `CRIAR NOME`, `EQUIPA NOME` e `RESULTADO EQUIPA PARTIDA POSICAO KILLS`.
- Uma base de dados partilhada.
- Verificação de assinatura do webhook WhatsApp quando `WHATSAPP_APP_SECRET` está definido.
- GitHub Actions valida a sintaxe do projeto.

## Pontuação inicial
Posição: 1.º=12, 2.º=9, 3.º=8, 4.º=7, 5.º=6, 6.º=5, 7.º=4, 8.º=3, 9.º=2, 10.º=1. Cada kill vale 1 ponto. Confirme e altere esta tabela em `points_for()` para corresponder ao regulamento do seu campeonato.

## Segurança
- Nunca publique tokens no código, README, issues ou commits.
- Configure os tokens como Environment Variables no serviço de alojamento.
- Ative 2FA no Discord, Meta e GitHub.
- Só números incluídos em `WA_ADMIN_NUMBERS` podem criar campeonatos, inscrever equipas e registar resultados pelo WhatsApp.
- Para operação real, use armazenamento persistente. O SQLite local sem disco persistente pode perder dados quando o serviço reinicia.

## Executar localmente
1. Python 3.11+.
2. `pip install -r requirements.txt`
3. Copie `.env.example` para `.env` e preencha as variáveis.
4. `python bot.py`

## Deploy
Use um serviço de hospedagem Python com processo contínuo, URL HTTPS pública e disco persistente. Configure `python bot.py` como comando de início e as variáveis do `.env.example` no painel do serviço. Configure o webhook Meta para `https://SEU-DOMINIO/webhook` e o token de verificação correspondente.

GitHub Actions valida o código; não é o alojamento contínuo do bot.
