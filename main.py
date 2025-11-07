# main.py
import tkinter as tk
from tkinter import messagebox
from app import PDFToolboxApp
import updater  # Importa o novo módulo

# --- IMPORTANTE: Defina a versão atual da sua aplicação aqui ---
# A cada nova release no GitHub, você deve incrementar esta versão no seu código.
CURRENT_VERSION = "v1.0.0"


def main():
    """Função principal que inicia a aplicação."""
    # Oculta a janela principal temporariamente enquanto verifica a atualização
    root = tk.Tk()
    root.withdraw()

    # 1. Verifica se há atualizações
    latest_version, zip_url = updater.check_for_updates(CURRENT_VERSION)

    if latest_version:
        # 2. Se houver, pergunta ao usuário se deseja atualizar
        msg = f"Uma nova versão ({latest_version}) está disponível. Você está usando a versão {CURRENT_VERSION}. Deseja atualizar agora?"
        if messagebox.askyesno("Atualização Disponível", msg):
            # 3. Se sim, aplica a atualização
            if updater.apply_update(zip_url):
                messagebox.showinfo("Sucesso", "A aplicação foi atualizada e será reiniciada.")
                # 4. Reinicia a aplicação
                root.destroy()
                updater.restart_app()
                return  # Encerra a execução atual
            else:
                # Se a atualização falhar, informa o usuário e continua com a versão atual
                messagebox.showwarning("Falha na Atualização",
                                       "Não foi possível atualizar. A aplicação continuará com a versão atual.")

    # Se não houver atualização ou o usuário recusar, inicia a aplicação normalmente
    root.deiconify()  # Mostra a janela principal novamente
    app = PDFToolboxApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()