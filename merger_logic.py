# merger_logic.py
import os
import collections
from tkinter import messagebox, Listbox
from PyPDF2 import PdfWriter

class MergerLogic:
    def __init__(self, app):
        self.app = app
        self.directory_path = ""
        self.pdf_files_map = collections.OrderedDict()

    def find_pdf_files(self):
        self.pdf_files_map = collections.OrderedDict()
        for dirpath, _, filenames in os.walk(self.directory_path):
            pdf_files = sorted([f for f in filenames if f.lower().endswith('.pdf')])
            if pdf_files:
                self.pdf_files_map[dirpath] = pdf_files

    def merge_pdfs(self):
        if self.app.ui.merge_all_var.get():
            self.merge_all_into_one()
        else:
            self.merge_by_folder()

    def merge_by_folder(self):
        self.app.ui.update_status("Mesclando PDFs por pasta... Por favor, aguarde.")
        merged_count = 0
        error_list = []

        for dir_frame in self.app.ui.scrollable_frame.winfo_children():
            listbox_widget = next((w for w in dir_frame.winfo_children() if isinstance(w, Listbox)), None)
            if not listbox_widget: continue

            ordered_files = listbox_widget.get(0, "end")
            dirpath = listbox_widget.dirpath

            if len(ordered_files) > 1:
                merger = PdfWriter()
                has_error_in_group = False
                for filename in ordered_files:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        merger.append(filepath)
                    except Exception as e:
                        error_message = f"Erro ao ler '{filename}': {e}"
                        error_list.append(error_message)
                        has_error_in_group = True
                        break

                if not has_error_in_group:
                    folder_name = os.path.basename(dirpath)
                    output_filename = os.path.join(dirpath, f"{folder_name}_merged.pdf")
                    try:
                        with open(output_filename, "wb") as output_file:
                            merger.write(output_file)
                        merged_count += 1
                    except Exception as e:
                        error_message = f"Erro ao salvar '{output_filename}': {e}"
                        error_list.append(error_message)
                merger.close()

        self.show_completion_message(merged_count, error_list)
        self.app.ui.update_status("Processo de mesclagem por pasta concluído.")

    def merge_all_into_one(self):
        self.app.ui.update_status("Mesclando todos os PDFs... Por favor, aguarde.")

        listbox_widget = next((w for w in self.app.ui.scrollable_frame.winfo_children()[0].winfo_children() if isinstance(w, Listbox)), None)
        if not listbox_widget:
            messagebox.showerror("Erro", "Nenhuma lista de arquivos encontrada.")
            return

        ordered_files_rel = listbox_widget.get(0, "end")
        if not ordered_files_rel or len(ordered_files_rel) <= 1:
            messagebox.showwarning("Atenção", "Selecione mais de um arquivo para mesclar.")
            return

        merger = PdfWriter()
        error_list = []
        has_error = False

        for file_rel_path in ordered_files_rel:
            filepath = os.path.join(self.directory_path, file_rel_path)
            try:
                merger.append(filepath)
            except Exception as e:
                error_message = f"Erro ao ler '{file_rel_path}': {e}"
                error_list.append(error_message)
                has_error = True
                break

        if not has_error:
            try:
                output_filename = os.path.join(self.directory_path, "merged_all.pdf")
                with open(output_filename, "wb") as output_file:
                    merger.write(output_file)
                self.show_completion_message(1, [])
            except Exception as e:
                error_list.append(f"Erro ao salvar o arquivo final: {e}")
                self.show_completion_message(0, error_list)

        merger.close()
        self.app.ui.update_status("Processo de mesclagem de todos os arquivos concluído.")

    def show_completion_message(self, merged_count, error_list):
        if error_list:
            messagebox.showerror("Erro na Mesclagem", "Ocorreram erros:\n\n" + "\n".join(error_list))
        elif merged_count > 0:
            if self.app.ui.merge_all_var.get():
                 messagebox.showinfo("Sucesso", "Todos os PDFs foram mesclados em um único arquivo com sucesso!")
            else:
                messagebox.showinfo("Sucesso", f"{merged_count} grupo(s) de PDFs foram mesclados com sucesso!")