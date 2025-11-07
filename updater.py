# updater.py
import requests
import os
import sys
import zipfile
import shutil
from tkinter import messagebox

# Configurações do repositório no GitHub
GITHUB_REPO = "jjvvsszz/PDF-ToolBox"


def check_for_updates(current_version):
    """Verifica se há uma nova versão no GitHub."""
    try:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()  # Lança um erro para respostas HTTP ruins (4xx ou 5xx)

        latest_release_data = response.json()
        latest_version = latest_release_data.get("tag_name")

        print(f"Versão atual: {current_version}, Versão mais recente no GitHub: {latest_version}")

        # Compara as versões (assume formato 'vX.Y.Z')
        if latest_version and latest_version > current_version:
            return latest_version, latest_release_data.get("zipball_url")

    except requests.exceptions.RequestException as e:
        print(f"Erro ao verificar atualizações: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

    return None, None


def apply_update(zip_url):
    """Baixa e aplica a atualização."""
    try:
        # Baixa o arquivo zip da nova versão
        print(f"Baixando atualização de: {zip_url}")
        response = requests.get(zip_url, stream=True)
        response.raise_for_status()

        zip_path = "update.zip"
        with open(zip_path, "wb") as f:
            shutil.copyfileobj(response.raw, f)
        print("Download concluído.")

        # Extrai o conteúdo do zip
        extract_path = "update_extracted"
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)  # Limpa extrações antigas

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        print("Extração concluída.")

        # O GitHub empacota os arquivos dentro de uma pasta com o nome do repo e o hash do commit
        # Ex: 'jjvvsszz-PDF-ToolBox-a1b2c3d'. Precisamos encontrar essa pasta.
        extracted_root_folder = os.path.join(extract_path, os.listdir(extract_path)[0])

        # Move os arquivos extraídos para o diretório atual, sobrescrevendo os antigos
        print("Movendo novos arquivos...")
        for item in os.listdir(extracted_root_folder):
            source_item = os.path.join(extracted_root_folder, item)
            dest_item = os.path.join(os.getcwd(), item)

            # Se for um diretório, remove o antigo e move o novo
            if os.path.isdir(source_item):
                if os.path.exists(dest_item):
                    shutil.rmtree(dest_item)
                shutil.move(source_item, dest_item)
            # Se for um arquivo, simplesmente move (sobrescreve)
            else:
                shutil.move(source_item, dest_item)

        print("Arquivos atualizados.")
        return True

    except Exception as e:
        messagebox.showerror("Erro na Atualização", f"Não foi possível aplicar a atualização:\n{e}")
        return False
    finally:
        # Limpa os arquivos temporários
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        print("Limpeza concluída.")


def restart_app():
    """Reinicia a aplicação."""
    print("Reiniciando a aplicação...")
    # os.execl substitui o processo atual por um novo
    os.execl(sys.executable, sys.executable, *sys.argv)