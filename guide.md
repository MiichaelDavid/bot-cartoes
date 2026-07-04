# Guia de Implantação e Atualizações Automatizadas (Oracle Cloud)

Este guia orienta sobre como subir atualizações futuras do **Bot de Cartões e Chutes** para o servidor remoto e executá-las de forma automática.

---

## 🚀 Como subir atualizações para o Servidor

Toda a infraestrutura de deploy foi automatizada localmente. Você não precisa acessar o terminal SSH do Linux para atualizar o código manualmente.

Basta seguir os passos abaixo:

### Passo 1: Realizar alterações locais
Faça as modificações que desejar nos códigos Python dentro da pasta `src/` (regras, APIs, modelos, etc.).

### Passo 2: Executar o Script de Deploy
Abra o seu terminal (PowerShell ou Prompt de Comando) na raiz do projeto local e digite:
```powershell
python deploy.py
```

### O que acontece por trás dos panos:
1. **Empacotamento**: O script local compacta toda a pasta `src/` (incluindo subpastas e novos módulos), o `requirements.txt` e os arquivos de serviço do systemd (`bot-cartoes.service` e `bot-copa.service`) em um arquivo temporário `deploy.zip`.
2. **Transferência**: O pacote `deploy.zip` é enviado para o diretório `/home/ubuntu/` na nuvem via SCP.
3. **Extração**: O script executa comandos SSH remotos para criar a pasta final `/home/ubuntu/bot-cartoes` e extrair os arquivos usando o interpretador Python do servidor.
4. **Preservação de Credenciais**: O script valida a existência do `.env` remoto. Se já estiver configurado com as chaves corretas, ele **não sobrescreve**, protegendo suas credenciais de produção.
5. **Configuração de Dependências**: Atualiza o ambiente virtual (`venv`) no servidor e instala novas bibliotecas do `requirements.txt` via pip.
6. **Automação de Serviços (Systemd)**:
   - Copia os arquivos `.service` para o diretório do systemd do Ubuntu (`/etc/systemd/system/`).
   - Executa `sudo systemctl daemon-reload` para carregar as novas instruções.
   - Habilita os serviços para iniciarem junto com o boot da máquina.
   - Reinicia ambos os bots (`bot-cartoes` para clubes e `bot-copa` para a Copa) para aplicar a atualização de código imediatamente.
   - Exibe o status da execução final no terminal local.

---

## ⚙️ Gerenciamento Remoto dos Bots (SSH)

Caso você queira acessar o servidor e gerenciar os bots individualmente, conecte-se com o comando:
```bash
ssh -i "C:\Users\777\Documents\chave-instacia-api\instancia 1\ssh-key-2026-06-26 (1).key" ubuntu@140.238.177.4
```

E use os comandos abaixo:

### 1. Bot de Clubes (Brasileirão, Premier League, etc.)
- **Status / Logs**: `sudo systemctl status bot-cartoes`
- **Reiniciar**: `sudo systemctl restart bot-cartoes`
- **Parar**: `sudo systemctl stop bot-cartoes`
- **Logs em Tempo Real**: `journalctl -u bot-cartoes -f`

### 2. Bot da Copa do Mundo 2026 (Standalone, ESPN keyless)
- **Status / Logs**: `sudo systemctl status bot-copa`
- **Reiniciar**: `sudo systemctl restart bot-copa`
- **Parar**: `sudo systemctl stop bot-copa`
- **Logs em Tempo Real**: `journalctl -u bot-copa -f`

> 💡 **Nota**: O bot da Copa do Mundo funciona de forma standalone e sem limites de cota da API. Quando a Copa acabar, basta desativar o serviço executando:
> ```bash
> sudo systemctl stop bot-copa
> sudo systemctl disable bot-copa
> ```
