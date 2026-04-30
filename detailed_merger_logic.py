# detailed_merger_logic.py
import os
import fitz  # PyMuPDF
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from PyPDF2 import PdfWriter, PdfReader


class DetailedMergerLogic:
    def __init__(self, app):
        self.app = app
        # Lista de dicionários. Cada item representa uma página:
        # {
        #   'file_path': str,
        #   'page_index': int, (index original no arquivo)
        #   'display_image': ImageTk.PhotoImage,
        #   'original_filename': str
        # }
        self.pages = []

    def add_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("Arquivos PDF", "*.pdf")])
        if not file_path:
            return

        self.app.ui.update_status(f"Processando {os.path.basename(file_path)}...")

        try:
            # Usa PyMuPDF (fitz) para renderizar imagens
            doc = fitz.open(file_path)
            base_name = os.path.basename(file_path)

            new_pages = []
            for i in range(len(doc)):
                page = doc.load_page(i)
                # Renderiza a página em uma imagem (pixmap)
                # Matrix(0.3, 0.3) reduz a escala para criar uma thumbnail leve
                pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2))

                # Converte para formato PIL e depois para Tkinter
                img_data = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                tk_image = ImageTk.PhotoImage(img_data)

                page_data = {
                    'file_path': file_path,
                    'page_index': i,
                    'display_image': tk_image,
                    'original_filename': base_name
                }
                new_pages.append(page_data)

            doc.close()

            # Adiciona à lista principal
            self.pages.extend(new_pages)

            # Atualiza a interface
            self.app.ui.refresh_detailed_list()
            self.app.ui.update_status(f"Adicionado: {base_name} ({len(new_pages)} páginas).")

        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível ler o PDF:\n{e}")

    def move_page_up(self, index):
        if index > 0:
            self.pages[index], self.pages[index - 1] = self.pages[index - 1], self.pages[index]
            self.app.ui.refresh_detailed_list()

    def move_page_down(self, index):
        if index < len(self.pages) - 1:
            self.pages[index], self.pages[index + 1] = self.pages[index + 1], self.pages[index]
            self.app.ui.refresh_detailed_list()

    def remove_page(self, index):
        del self.pages[index]
        self.app.ui.refresh_detailed_list()
        self.app.ui.update_status("Página removida.")

    def clear_all(self):
        self.pages = []
        self.app.ui.refresh_detailed_list()
        self.app.ui.update_status("Lista limpa.")

    def save_pdf(self):
        if not self.pages:
            messagebox.showwarning("Atenção", "A lista de páginas está vazia.")
            return

        output_path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                                   filetypes=[("Arquivos PDF", "*.pdf")])
        if not output_path:
            return

        self.app.ui.update_status("Salvando PDF mesclado...")

        try:
            writer = PdfWriter()

            # Para otimizar, abrimos os arquivos conforme necessário
            # Agrupar leituras seria mais rápido, mas essa forma é mais simples de implementar
            # dado que a ordem pode ser totalmente aleatória.

            # Cache de leitores para não reabrir o mesmo arquivo repetidamente em sequência
            current_file_path = None
            current_reader = None
            file_handle = None

            for page_data in self.pages:
                path = page_data['file_path']
                idx = page_data['page_index']

                if path != current_file_path:
                    if file_handle:
                        file_handle.close()

                    file_handle = open(path, 'rb')
                    current_reader = PdfReader(file_handle)
                    current_file_path = path

                writer.add_page(current_reader.pages[idx])

            with open(output_path, "wb") as f_out:
                writer.write(f_out)

            if file_handle:
                file_handle.close()

            self.app.ui.update_status("PDF Salvo com sucesso!")
            messagebox.showinfo("Sucesso", f"Arquivo salvo em:\n{output_path}")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar PDF:\n{e}")
            self.app.ui.update_status("Erro ao salvar.")