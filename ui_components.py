# ui_components.py
import tkinter as tk
from tkinter import filedialog, Listbox, messagebox
from tkinter import ttk
from platform import system
import os


class UIComponents:
    def __init__(self, root, app, main_container):
        self.root = root
        self.app = app
        self.merger_logic = self.app.merger_logic
        self.style_config = self.app.style_config

        self.main_container = main_container
        self.views = {}  # Dicionário para armazenar todas as telas (views)

        # Construção das views
        self.create_main_menu_view()
        self.create_merger_view()
        # Chame aqui a criação de outras ferramentas no futuro
        # self.create_splitter_view()

        self.dragging_item = None
        self.dragging_listbox = None

        # Bind da rolagem do mouse
        self.root.bind_all("<MouseWheel>", self._on_mouse_wheel)
        self.root.bind_all("<Button-4>", self._on_mouse_wheel)
        self.root.bind_all("<Button-5>", self._on_mouse_wheel)

    def show_view(self, view_name):
        """Esconde todas as views e exibe apenas a view solicitada."""
        # Esconde todas as views
        for view in self.views.values():
            view.pack_forget()

        # Exibe a view desejada
        current_view = self.views.get(view_name)
        if current_view:
            current_view.pack(fill="both", expand=True)

    def create_main_menu_view(self):
        """Cria a tela do menu principal com botões para cada ferramenta."""
        menu_frame = ttk.Frame(self.main_container, style='Main.TFrame', padding=20)
        self.views['main_menu'] = menu_frame

        # Frame para centralizar o conteúdo
        center_frame = ttk.Frame(menu_frame, style='Main.TFrame')
        center_frame.place(relx=0.5, rely=0.5, anchor='center')

        header = ttk.Label(center_frame, text="PDF Toolbox", style='Header.TLabel')
        header.pack(pady=(0, 40))

        # Botão para a ferramenta de mesclagem
        btn_merger = ttk.Button(center_frame, text="Mesclar PDFs", style='Menu.TButton',
                                command=lambda: self.show_view('merger'))
        btn_merger.pack(pady=5)

    def create_merger_view(self):
        """Cria a view completa da ferramenta de mesclagem."""
        merger_container = ttk.Frame(self.main_container, style='Main.TFrame', padding=(10, 10, 10, 0))
        self.views['merger'] = merger_container

        header_frame = ttk.Frame(merger_container, style='Main.TFrame')
        header_frame.pack(fill='x', pady=(0, 10))

        btn_back = ttk.Button(header_frame, text="< Voltar ao Menu", style='Back.TButton',
                              command=lambda: self.show_view('main_menu'))
        btn_back.pack(side='left')

        frame_top = ttk.Frame(merger_container, style='Main.TFrame')
        frame_top.pack(fill="x", pady=(0, 10))

        self.btn_select_dir = ttk.Button(frame_top, text="Selecionar Diretório", command=self.select_directory,
                                         style='Accent.TButton')
        self.btn_select_dir.pack(side="left", padx=(0, 10))
        self.lbl_dir_path = ttk.Label(frame_top, text="Nenhum diretório selecionado", style='Info.TLabel')
        self.lbl_dir_path.pack(side="left", fill="x", expand=True)

        switch_frame = ttk.Frame(merger_container, style='Switch.TFrame')
        switch_frame.pack(fill='x', pady=5)
        self.merge_all_var = tk.BooleanVar(value=False)
        self.switch_button = ttk.Checkbutton(switch_frame, text="Mesclar todos os arquivos em um único",
                                             variable=self.merge_all_var, style='Switch.TCheckbutton',
                                             command=self.toggle_merge_mode)
        self.switch_button.pack()

        main_frame = ttk.Frame(merger_container, style='Secondary.TFrame')
        main_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(main_frame, bg=self.style_config['bg_secondary'], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style='Secondary.TFrame')

        # --- [INÍCIO DA CORREÇÃO 1/2] ---
        # Guardamos o ID da "janela" que o canvas irá gerenciar
        self.canvas_window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        # --- [FIM DA CORREÇÃO 1/2] ---

        self.scrollable_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        frame_bottom = ttk.Frame(merger_container, style='Main.TFrame')
        frame_bottom.pack(fill="x", pady=(10, 10))

        self.btn_merge = ttk.Button(frame_bottom, text="Mesclar PDFs", command=self.merger_logic.merge_pdfs,
                                    state="disabled", style='Accent.TButton')
        self.btn_merge.pack(pady=5)
        self.lbl_status = ttk.Label(frame_bottom, text="Aguardando seleção de diretório...", style='Status.TLabel',
                                    anchor="center")
        self.lbl_status.pack(fill="x", expand=True)

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        # --- [INÍCIO DA CORREÇÃO 2/2] ---
        # Usamos o ID guardado para redimensionar a "janela" correta
        self.canvas.itemconfig(self.canvas_window_id, width=event.width)
        # --- [FIM DA CORREÇÃO 2/2] ---

    def _on_mouse_wheel(self, event):
        delta = 0
        if system() == 'Linux':
            delta = -1 if event.num == 4 else 1
        elif system() == 'Windows':
            delta = -int(event.delta / 120)
        elif system() == 'Darwin':
            delta = event.delta
        self.canvas.yview_scroll(delta, "units")

    def select_directory(self):
        path = filedialog.askdirectory()
        if path:
            self.merger_logic.directory_path = path
            self.lbl_dir_path.config(text=self.merger_logic.directory_path)
            self.update_status("Buscando arquivos PDF...")
            self.merger_logic.find_pdf_files()
            self.display_pdf_lists()
            self.btn_merge.config(state="normal")
            if not self.merge_all_var.get():
                self.update_status(f"{len(self.merger_logic.pdf_files_map)} diretório(s) com PDFs encontrados.")
            else:
                self.update_status(
                    f"Encontrados {sum(len(v) for v in self.merger_logic.pdf_files_map.values())} arquivos.")

    def display_pdf_lists(self):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        if self.merge_all_var.get():
            self.display_all_pdfs_in_one_list()
        else:
            self.display_pdfs_by_folder()

    def display_pdfs_by_folder(self):
        for dirpath, files in self.merger_logic.pdf_files_map.items():
            dir_frame = ttk.Frame(self.scrollable_frame, style='Secondary.TFrame', padding=10)
            dir_frame.pack(fill="x", expand=True, padx=10, pady=5)
            rel_path = os.path.relpath(dirpath, self.merger_logic.directory_path)
            label = ttk.Label(dir_frame, text=f"Diretório: {rel_path if rel_path != '.' else 'Diretório Raiz'}",
                              style='Header.TLabel', font=self.app.style_config['font_bold'],
                              background=self.style_config['bg_secondary'])
            label.pack(anchor="w", pady=(0, 5))
            listbox = Listbox(dir_frame, selectmode="single", height=len(files), bg='#4F4F4F',
                              fg=self.style_config['fg_color'], font=self.style_config['font_normal'],
                              highlightthickness=0, borderwidth=1, relief="solid",
                              selectbackground=self.style_config['accent_color'],
                              selectforeground=self.style_config['accent_fg'])
            listbox.dirpath = dirpath
            for file in files: listbox.insert("end", file)
            listbox.bind("<Button-1>", self.on_listbox_press)
            listbox.bind("<B1-Motion>", self.on_listbox_drag)
            listbox.bind("<ButtonRelease-1>", self.on_listbox_release)
            listbox.pack(fill="both", expand=True)

    def display_all_pdfs_in_one_list(self):
        all_files_frame = ttk.Frame(self.scrollable_frame, style='Secondary.TFrame', padding=10)
        all_files_frame.pack(fill="x", expand=True, padx=10, pady=5)
        label = ttk.Label(all_files_frame, text="Todos os arquivos PDF", style='Header.TLabel',
                          font=self.app.style_config['font_bold'], background=self.style_config['bg_secondary'])
        label.pack(anchor="w", pady=(0, 5))
        all_files = [os.path.join(dp, f) for dp, fl in self.merger_logic.pdf_files_map.items() for f in fl]
        listbox = Listbox(all_files_frame, selectmode="single", height=len(all_files), bg='#4F4F4F',
                          fg=self.style_config['fg_color'], font=self.style_config['font_normal'], highlightthickness=0,
                          borderwidth=1, relief="solid", selectbackground=self.style_config['accent_color'],
                          selectforeground=self.style_config['accent_fg'])
        for file_path in all_files: listbox.insert("end", os.path.relpath(file_path, self.merger_logic.directory_path))
        listbox.bind("<Button-1>", self.on_listbox_press)
        listbox.bind("<B1-Motion>", self.on_listbox_drag)
        listbox.bind("<ButtonRelease-1>", self.on_listbox_release)
        listbox.pack(fill="both", expand=True)

    def toggle_merge_mode(self):
        if self.merger_logic.directory_path:
            self.display_pdf_lists()
            if self.merge_all_var.get():
                self.update_status("Modo de mesclagem único ativado.")
            else:
                self.update_status("Modo de mesclagem por pasta ativado.")

    def update_status(self, message):
        self.lbl_status.config(text=message)
        self.root.update_idletasks()

    def on_listbox_press(self, event):
        self.dragging_listbox = event.widget
        self.dragging_item = self.dragging_listbox.nearest(event.y)

    def on_listbox_drag(self, event):
        if self.dragging_item is not None:
            new_index = self.dragging_listbox.nearest(event.y)
            if new_index != self.dragging_item:
                item_text = self.dragging_listbox.get(self.dragging_item)
                self.dragging_listbox.delete(self.dragging_item)
                self.dragging_listbox.insert(new_index, item_text)
                self.dragging_item = new_index

    def on_listbox_release(self, event):
        self.dragging_item = None
        self.dragging_listbox = None