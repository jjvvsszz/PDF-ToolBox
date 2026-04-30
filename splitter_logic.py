# splitter_logic.py
import os
from tkinter import messagebox
from PyPDF2 import PdfReader, PdfWriter


class SplitterLogic:
    def __init__(self, app):
        self.app = app
        self.file_path = ""

    def set_file(self, file_path):
        self.file_path = file_path

    def split_pdf(self):
        if not self.file_path or not os.path.exists(self.file_path):
            messagebox.showwarning("Atenção", "Selecione um arquivo PDF válido primeiro.")
            return

        self.app.ui.update_status("Separando PDF... Por favor, aguarde.")

        try:
            reader = PdfReader(self.file_path)
            total_pages = len(reader.pages)

            if total_pages < 1:
                messagebox.showerror("Erro", "O arquivo PDF parece estar vazio ou corrompido.")
                return

            base_dir = os.path.dirname(self.file_path)
            base_name = os.path.splitext(os.path.basename(self.file_path))[0]

            # Cria uma subpasta para não bagunçar o diretório original
            output_dir = os.path.join(base_dir, f"{base_name}_paginas")
            os.makedirs(output_dir, exist_ok=True)

            for i, page in enumerate(reader.pages):
                writer = PdfWriter()
                writer.add_page(page)

                # Nome do arquivo: original_pag_1.pdf, original_pag_2.pdf, etc.
                output_filename = os.path.join(output_dir, f"{base_name}_pag_{i + 1}.pdf")

                with open(output_filename, "wb") as output_file:
                    writer.write(output_file)

            self.app.ui.update_status("Processo de separação concluído.")
            messagebox.showinfo("Sucesso", f"O PDF foi separado em {total_pages} arquivos.\nSalvo em: {output_dir}")

        except Exception as e:
            error_msg = f"Ocorreu um erro ao separar o PDF: {str(e)}"
            print(error_msg)
            self.app.ui.update_status("Erro ao separar PDF.")
            messagebox.showerror("Erro", error_msg)