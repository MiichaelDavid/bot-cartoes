# Bot de Cartões e Chutes ⚽🟨🎯

Monitora partidas de futebol **ao vivo**, calcula a **probabilidade em tempo real de cada jogador levar cartão amarelo** ou **dar chutes a gol** (usando estatísticas do jogo, posições, ritmo da partida e distribuição de Poisson/heurísticas) e envia **sinais formatados** diretamente para seu **Discord** e/ou **WhatsApp**.

> ⚠️ **Aviso de Responsabilidade:** Os sinais são baseados em estimativas probabilísticas e heurísticas para auxílio de análise de valor esperado (EV+). Não há garantia de lucro. Sempre faça a gestão de banca e aposte de forma responsável.

---

## 📂 Estrutura e Hierarquia do Projeto

O projeto é organizado seguindo as melhores práticas de modularidade para código em Python, separando regras de negócios, integrações, envio de mensagens e utilitários gerais:

```
bot-cartoes/
├── src/                          # Todo o código-fonte da aplicação
│   ├── __init__.py
│   ├── monitor.py                # Orquestrador central (Loop geral e monitoramento)
│   ├── config.py                 # Leitura do .env e variáveis globais
│   ├── models/                   # Lógica matemática e probabilística
│   │   ├── __init__.py
│   │   ├── cartoes.py            # Modelo heurístico para cartões amarelos
│   │   └── chutes.py             # Modelo de Poisson para chutes a gol
│   ├── sources/                  # Integração com APIs externas de dados
│   │   ├── __init__.py
│   │   ├── apifootball.py        # Integração com a API-Football (Copa do Mundo)
│   │   └── espn.py               # Integração com a API da ESPN (Clubes)
│   ├── services/                 # Serviços de notificações e disparo de alertas
│   │   ├── __init__.py
│   │   ├── whatsapp.py           # Envio de mensagens WhatsApp (CallMeBot)
│   │   └── discord_notifier.py   # Envio de banners ao Discord (Webhooks)
│   └── utils/                    # Utilitários de persistência e conferência
│       ├── __init__.py
│       └── registro.py           # Gravação de sinais e calibração de modelos
├── docs/                         # Documentações do sistema
│   └── projeto_e_servidor.md     # Especificações da nuvem e arquitetura
├── .env                          # Variáveis de ambiente locais (Ignorado no Git)
├── .env.example                  # Exemplo de configuração das variáveis
├── .gitignore                    # Regras de ocultação de arquivos temporários do Git
├── requirements.txt              # Bibliotecas Python necessárias
├── deploy.py                     # Script automatizado de deploy para nuvem (local)
├── bot-cartoes.service           # Template do serviço Systemd para a VM Linux
└── README.md                     # Documentação geral do projeto (este arquivo)
```

---

## 🚀 Como Funciona

```
                               Jogos Ao Vivo
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
       [API pública ESPN] (Clubes)            [API-Football] (Copa)
       Gratuita & Sem limite de cota           Requer API Key (100 req/dia)
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     ▼
                            [Orquestrador: monitor.py]
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
    [Estratégia 1: Cartões]                 [Estratégia 2: Chutes]
    Calcula P(Cartão) heurística            Poisson de chutes a gol
    Min. faltas, tempo restante             Histórico por posição + ritmo
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     ▼
                      Disparo se Prob ≥ Prob_Mínima
                                     │
               ┌─────────────────────┼─────────────────────┐
               ▼                     ▼                     ▼
      [Registro Local]         [Notificação]         [Notificação]
      sinais_log.jsonl           WhatsApp               Discord
```

---

## 🛠️ Recursos e Funcionalidades

1. **Estratégias Ao Vivo**:
   - **Cartões**: Heurística baseada em faltas acumuladas, ritmo de cartões da partida, minutos restantes e pesos de agressividade por posição.
   - **Chutes a Gol**: Distribuição probabilística de Poisson calculada a partir de uma taxa base por posição misturada ao ritmo do jogador no jogo.
2. **Prevenção Inteligente de Spam**:
   - O bot mantém controle em memória de quem já foi notificado.
   - **Persistência**: Ao iniciar ou reiniciar o bot, ele lê o histórico gravado em `sinais_log.jsonl` (salvo na raiz) para repopular a lista e **evitar o envio de sinais duplicados** para partidas em andamento.
3. **Múltiplos Canais**: Envio de banners para o Discord (webhook) e mensagens no WhatsApp (via CallMeBot).
4. **Calibração pós-jogo (`src/utils/registro.py`)**: Valida se as previsões do modelo bateram nos resultados oficiais ao final do jogo para verificar a calibração de odds.

---

## 💻 Configuração Local (Setup)

### 1. Clonar e Instalar Dependências
```bash
git clone https://github.com/MiichaelDavid/bot-cartoes.git
cd bot-cartoes
python -m venv venv
venv\Scripts\activate      # No Windows
source venv/bin/activate   # No Linux/macOS
pip install -r requirements.txt
```

### 2. Configurar o Arquivo `.env`
Crie um arquivo `.env` na raiz do projeto (use o `.env.example` como base) e preencha suas configurações:
```ini
# Configurações de execução
FONTE_FALTAS=hibrido
LIGAS_ESPN=bra.1,usa.1,arg.1,mex.1,nor.1,swe.1,uefa.europa,uefa.champions,eng.1,esp.1,ita.1,ger.1,fra.1
API_FOOTBALL_KEY=sua_chave_aqui
LIGAS_FILTRO=world cup

# Notificações (Preencha pelo menos um)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxxx
CALLMEBOT_PHONE=5511999999999
CALLMEBOT_APIKEY=sua_chave_callmebot

# Regras de limite de valor
PROB_MINIMA=0.50
MIN_FALTAS=2
INTERVALO_SEG=300
INTERVALO_OCIOSO=600

# [Deploy] Configuração do IP da Instância Oracle Cloud
SERVER_IP=123.456.78.90
```

### 3. Executar o Monitor Localmente
```bash
python src/monitor.py
```

---

## ☁️ Infraestrutura de Nuvem (Oracle Cloud)

O bot está preparado para rodar de forma contínua em uma VM da Oracle Cloud com as seguintes especificações:

- **Nome do Servidor**: `meu-site-server` (Ubuntu 22.04 LTS, 1 OCPU, 1 GB RAM, shape `VM.Standard.E2.1.Micro`)
- **VCN**: `vcn-meu-site`
- **Usuário SSH padrão**: `ubuntu`
- **Chave Privada SSH**: Localizada em `C:\Users\777\Documents\chave-instacia-api\instancia 1\ssh-key-2026-06-26 (1).key`
- **Comando de conexão direta**:
  ```bash
  ssh -i "C:\Users\777\Documents\chave-instacia-api\instancia 1\ssh-key-2026-06-26 (1).key" ubuntu@<IP_PUBLICO_DA_INSTANCIA>
  ```

---

## 🚢 Deploy Automatizado (`deploy.py`)

Para enviar atualizações locais diretamente para o servidor de produção, você pode usar o script `deploy.py` executando localmente na sua máquina Windows.

### Como Executar o Deploy:
1. Abra o PowerShell ou Prompt de Comando na raiz do projeto.
2. Certifique-se de que a chave SSH está na pasta correspondente.
3. Certifique-se de que a variável `SERVER_IP` está preenchida no seu arquivo `.env`.
4. Execute:
   ```bash
   python deploy.py
   ```

### O que o Script de Deploy faz automaticamente:
- Compacta os códigos Python do diretório `src/`, dependências e arquivos de configuração importantes no arquivo `deploy.zip`.
- Envia o ZIP via SCP para a VM em `/home/ubuntu/`.
- Extrai os arquivos na pasta de destino no servidor remetente `/home/ubuntu/bot-cartoes` de forma limpa.
- **Segurança do .env**: Se já existir um `.env` na máquina virtual, ele **não é sobrescrito**, garantindo que as chaves de produção sejam mantidas.
- Cria ou atualiza o Virtual Environment no Ubuntu e instala pacotes com pip.
- Copia o arquivo `bot-cartoes.service` para a pasta do systemd no Linux (`/etc/systemd/system/`).
- Atualiza o daemon (`daemon-reload`), habilita para iniciar com o boot da máquina (`enable`) e reinicia o bot (`restart`).
- Imprime o status do serviço.

---

## ⚙️ Gerenciamento do Serviço no Servidor (Ubuntu)

Caso precise gerenciar o bot manualmente acessando o servidor SSH, use os seguintes comandos do Systemd no terminal Ubuntu:

* **Iniciar o bot**:
  ```bash
  sudo systemctl start bot-cartoes
  ```
* **Parar o bot**:
  ```bash
  sudo systemctl stop bot-cartoes
  ```
* **Reiniciar o bot**:
  ```bash
  sudo systemctl restart bot-cartoes
  ```
* **Verificar o status / logs ao vivo**:
  ```bash
  sudo systemctl status bot-cartoes
  ```
* **Ver os logs de execução históricos (Journald)**:
  ```bash
  journalctl -u bot-cartoes -n 100 -f
  ```
