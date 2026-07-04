"""
Script de Deploy Automatizado para o Bot de Cartões.

Este script é executado localmente na sua máquina Windows e realiza:
1. Compactação dos arquivos de código relevantes do projeto.
2. Upload do pacote para a máquina virtual Ubuntu na Oracle Cloud via SCP.
3. Descompactação na máquina virtual usando Python nativo no servidor.
4. Criação e atualização de um Virtual Environment (venv) no servidor.
5. Instalação das dependências do requirements.txt no servidor.
6. Instalação e reinicialização do serviço systemd (bot-cartoes.service).
7. Verificação do status do serviço remoto.

Requisitos locais:
- Python 3 instalado no Windows.
- Chave SSH configurada no caminho correto.

Uso:
  python deploy.py
"""
import os
import sys
import zipfile
import subprocess

# --- CONFIGURAÇÕES DE IMPLANTAÇÃO ---
CHAVE_SSH = r"C:\Users\777\Documents\chave-instacia-api\instancia 1\ssh-key-2026-06-26 (1).key"
USER = "ubuntu"
DESTINO = "/home/ubuntu/bot-cartoes"
ARQUIVO_ZIP = "deploy.zip"

# Lista de arquivos/diretórios a incluir no deploy
ARQUIVOS_A_INCLUIR = [
    "src",
    "requirements.txt",
    "bot-cartoes.service",
    "bot-copa.service"
]

def print_banner(msg):
    print("\n" + "=" * 60)
    print(f" {msg}")
    print("=" * 60)

def obter_ip_servidor():
    # 1. Tentar ler do arquivo .env de forma simples e manual (evitando dependências de terceiros)
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SERVER_IP="):
                        ip = line.split("=", 1)[1].strip()
                        ip = ip.split("#")[0].strip().strip('"').strip("'")
                        if ip:
                            print(f"[*] IP do Servidor obtido do .env: {ip}")
                            return ip
        except Exception as e:
            print(f"[!] Erro ao tentar ler o .env localmente: {e}")

    # 2. Se não estiver no .env, solicitar ao usuário
    print_banner("Configuração do IP do Servidor")
    print("O IP do servidor não foi encontrado na variável SERVER_IP do arquivo .env.")
    ip = input("Por favor, digite o IP público da sua instância Oracle Cloud: ").strip()
    
    if not ip:
        print("[Erro] O IP do servidor é obrigatório para continuar.")
        sys.exit(1)
        
    # Salvar no .env para futuros deploys
    try:
        with open(".env", "a", encoding="utf-8") as f:
            f.write(f"\nSERVER_IP={ip}\n")
        print(f"[+] IP {ip} salvo no arquivo .env para os próximos deploys.")
    except Exception as e:
        print(f"[!] Não foi possível salvar o IP no .env: {e}")
        
    return ip

def verificar_chave():
    if not os.path.exists(CHAVE_SSH):
        print(f"[Erro] Chave SSH não encontrada no caminho:\n  {CHAVE_SSH}")
        print("Certifique-se de que o caminho está correto ou ajuste a variável CHAVE_SSH no script.")
        sys.exit(1)
    print("[*] Chave SSH localizada com sucesso.")

def criar_pacote_zip():
    print("[*] Criando pacote compactado para upload...")
    with zipfile.ZipFile(ARQUIVO_ZIP, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for caminho in ARQUIVOS_A_INCLUIR:
            if os.path.exists(caminho):
                if os.path.isdir(caminho):
                    for raiz, dirs, arquivos in os.walk(caminho):
                        # Ignora caches (__pycache__) e pastas ocultas do git
                        if "__pycache__" in raiz or ".git" in raiz:
                            continue
                        for arquivo in arquivos:
                            caminho_completo = os.path.join(raiz, arquivo)
                            caminho_relativo = os.path.relpath(caminho_completo, os.path.dirname(caminho) or ".")
                            zipf.write(caminho_completo, caminho_relativo)
                            print(f"  -> {caminho_relativo} adicionado.")
                else:
                    zipf.write(caminho, caminho)
                    print(f"  -> {caminho} adicionado.")
            else:
                print(f"  [AVISO] {caminho} não encontrado localmente e será ignorado.")
    print(f"[+] Pacote {ARQUIVO_ZIP} criado com sucesso.")

def executar_comando_ssh(ip, comando, descreve_erro="Erro"):
    cmd = [
        "ssh", "-i", CHAVE_SSH,
        "-o", "StrictHostKeyChecking=no",
        f"{USER}@{ip}", comando
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if res.returncode != 0:
        print(f"[Erro] {descreve_erro}")
        print(f"Código de retorno: {res.returncode}")
        print(f"Stderr: {res.stderr}")
        print(f"Stdout: {res.stdout}")
        return False, res.stdout
    return True, res.stdout

def realizar_deploy():
    verificar_chave()
    ip = obter_ip_servidor()
    criar_pacote_zip()

    # 1. Enviar deploy.zip para o servidor
    print_banner("1/5: Enviando arquivos para a VM...")
    cmd_scp = [
        "scp", "-i", CHAVE_SSH,
        "-o", "StrictHostKeyChecking=no",
        ARQUIVO_ZIP, f"{USER}@{ip}:/home/ubuntu/"
    ]
    print(f"Executando SCP de {ARQUIVO_ZIP} para /home/ubuntu/...")
    res = subprocess.run(cmd_scp)
    if res.returncode != 0:
        print("[Erro] Falha ao enviar o pacote compactado via SCP.")
        sys.exit(1)
    print("[+] Arquivos copiados para a VM.")

    # 2. Descompactar arquivos remotos
    print_banner("2/5: Descompactando no servidor...")
    cmd_descompactar = (
        f"mkdir -p {DESTINO} && "
        f"python3 -c \"import zipfile; zipfile.ZipFile('/home/ubuntu/{ARQUIVO_ZIP}').extractall('{DESTINO}')\" && "
        f"rm -f /home/ubuntu/{ARQUIVO_ZIP}"
    )
    ok, _ = executar_comando_ssh(ip, cmd_descompactar, "Falha ao descompactar no servidor.")
    if not ok:
        sys.exit(1)
    print("[+] Arquivos descompactados em " + DESTINO)

    # 3. Verificar/Enviar arquivo .env caso não exista
    print_banner("3/5: Verificando arquivo de configuração (.env)...")
    # Verificar se o .env já existe no servidor
    ok_env, _ = executar_comando_ssh(ip, f"test -f {DESTINO}/.env", "Checando .env")
    if not ok_env:
        # Se não existe, envia o .env local
        if os.path.exists(".env"):
            print("[*] .env não encontrado no servidor. Enviando arquivo .env local...")
            cmd_scp_env = [
                "scp", "-i", CHAVE_SSH,
                "-o", "StrictHostKeyChecking=no",
                ".env", f"{USER}@{ip}:{DESTINO}/.env"
            ]
            res = subprocess.run(cmd_scp_env)
            if res.returncode == 0:
                print("[+] Arquivo .env inicial configurado no servidor.")
            else:
                print("[AVISO] Falha ao enviar .env via SCP.")
        else:
            print("[AVISO] Nenhum arquivo .env local encontrado para enviar. Certifique-se de criá-lo manualmente no servidor.")
    else:
        print("[+] Arquivo .env já existe no servidor. Preservado para evitar perda de chaves de API.")

    # 4. Configurar dependências e Virtual Environment
    print_banner("4/5: Configurando dependências no servidor...")
    cmd_deps = (
        f"cd {DESTINO} && "
        f"python3 -m venv venv && "
        f"venv/bin/pip install --upgrade pip && "
        f"venv/bin/pip install -r requirements.txt"
    )
    print("Criando/atualizando Virtualenv e instalando pacotes via Pip (isso pode levar de 1 a 2 minutos)...")
    ok, _ = executar_comando_ssh(ip, cmd_deps, "Falha ao instalar dependências no servidor.")
    if not ok:
        sys.exit(1)
    print("[+] Dependências instaladas com sucesso.")

    # 5. Configurar e reiniciar o Serviço Systemd
    print_banner("5/5: Configurando os serviços do Systemd (Clubes + Copa)...")
    cmd_service = (
        f"sudo cp {DESTINO}/bot-cartoes.service /etc/systemd/system/bot-cartoes.service && "
        f"sudo cp {DESTINO}/bot-copa.service /etc/systemd/system/bot-copa.service && "
        f"sudo systemctl daemon-reload && "
        f"sudo systemctl enable bot-cartoes bot-copa && "
        f"sudo systemctl restart bot-cartoes bot-copa && "
        f"sleep 2 && "
        f"sudo systemctl status bot-cartoes --no-pager -l && "
        f"echo '----------------------------------------' && "
        f"sudo systemctl status bot-copa --no-pager -l"
    )
    ok, output_status = executar_comando_ssh(ip, cmd_service, "Falha ao configurar/reiniciar serviços.")
    if not ok:
        sys.exit(1)
        
    print_banner("Deploy Concluído com Sucesso! Status do Bot:")
    try:
        print(output_status)
    except UnicodeEncodeError:
        print(output_status.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))

    # Limpar zip local
    if os.path.exists(ARQUIVO_ZIP):
        os.remove(ARQUIVO_ZIP)

if __name__ == "__main__":
    try:
        realizar_deploy()
    except KeyboardInterrupt:
        print("\n[!] Deploy cancelado pelo usuário.")
        if os.path.exists(ARQUIVO_ZIP):
            os.remove(ARQUIVO_ZIP)
        sys.exit(0)
