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
        self.splitter_logic = self.app.splitter_logic
        self.detailed_logic = self.app.detailed_logic  # Referência à nova lógica
        self.style_config = self.app.style_config

        self.main_container = main_container
        self.views = {}

        # Construção das views
        self.create_main_menu_view()
        self.create_merger_view()
        self.create_splitter_view()
        self.create_detailed_merger_view()  # Nova tela

        self.dragging_item = None
        self.dragging_listbox = None

        self.root.bind_all("<MouseWheel>", self._on_mouse_wheel)
        self.root.bind_all("<Button-4>", self._on_mouse_wheel)
        self.root.bind_all("<Button-5>", self._on_mouse_wheel)

    def show_view(self, view_name):
        for view in self.views.values():
            view.pack_forget()
        current_view = self.views.get(view_name)
        if current_view:
            current_view.pack(fill="both", expand=True)

    def create_main_menu_view(self):
        menu_frame = ttk.Frame(self.main_container, style='Main.TFrame', padding=20)
        self.views['main_menu'] = menu_frame

        center_frame = ttk.Frame(menu_frame, style='Main.TFrame')
        center_frame.place(relx=0.5, rely=0.5, anchor='center')

        header = ttk.Label(center_frame, text="PDF Toolbox", style='Header.TLabel')
        header.pack(pady=(0, 40))

        btn_merger = ttk.Button(center_frame, text="Mesclar por Pastas", style='Menu.TButton',
                                command=lambda: self.show_view('merger'))
        btn_merger.pack(pady=5)

        # Novo botão: Mesclagem Detalhada
        btn_detailed = ttk.Button(center_frame, text="Mesclagem Detalhada", style='Menu.TButton',
                                  command=lambda: self.show_view('detailed_merger'))
        btn_detailed.pack(pady=5)

        btn_splitter = ttk.Button(center_frame, text="Separar PDF", style='Menu.TButton',
                                  command=lambda: self.show_view('splitter'))
        btn_splitter.pack(pady=5)

    def create_merger_view(self):
        # (Código original da merger view mantido igual)
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

        self.canvas_window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

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
        self.lbl_status = ttk.Label(frame_bottom, text="Aguardando...", style='Status.TLabel', anchor="center")
        self.lbl_status.pack(fill="x", expand=True)

    def create_splitter_view(self):
        # (Código original da splitter view mantido igual)
        splitter_container = ttk.Frame(self.main_container, style='Main.TFrame', padding=(10, 10, 10, 0))
        self.views['splitter'] = splitter_container

        header_frame = ttk.Frame(splitter_container, style='Main.TFrame')
        header_frame.pack(fill='x', pady=(0, 20))

        btn_back = ttk.Button(header_frame, text="< Voltar ao Menu", style='Back.TButton',
                              command=lambda: self.show_view('main_menu'))
        btn_back.pack(side='left')

        lbl_title = ttk.Label(splitter_container, text="Separar PDF em páginas", style='Header.TLabel')
        lbl_title.pack(pady=(0, 30))

        selection_frame = ttk.Frame(splitter_container, style='Secondary.TFrame', padding=20)
        selection_frame.pack(fill="x", padx=50)

        self.lbl_split_file = ttk.Label(selection_frame, text="Nenhum arquivo selecionado",
                                        style='TLabel', background=self.style_config['bg_secondary'])
        self.lbl_split_file.pack(pady=(0, 10))

        btn_select = ttk.Button(selection_frame, text="Selecionar Arquivo PDF",
                                style='Accent.TButton', command=self.select_pdf_to_split)
        btn_select.pack()

        self.btn_split_action = ttk.Button(splitter_container, text="Separar Páginas",
                                           style='Accent.TButton', state="disabled",
                                           command=self.splitter_logic.split_pdf)
        self.btn_split_action.pack(pady=30)
        self.lbl_status_splitter = ttk.Label(splitter_container, text="", style='Status.TLabel', anchor="center")
        self.lbl_status_splitter.pack(fill="x", side="bottom", pady=10)

    # --- NOVA VIEW: DETAILED MERGER ---
    def create_detailed_merger_view(self):
        container = ttk.Frame(self.main_container, style='Main.TFrame', padding=(10, 10, 10, 0))
        self.views['detailed_merger'] = container

        # Topo
        header = ttk.Frame(container, style='Main.TFrame')
        header.pack(fill='x', pady=(0, 10))
        btn_back = ttk.Button(header, text="< Voltar", style='Back.TButton',
                              command=lambda: self.show_view('main_menu'))
        btn_back.pack(side='left')

        ttk.Label(header, text="Mesclagem Detalhada (Visual)", style='Header.TLabel',
                  font=self.style_config['font_bold']).pack(side='left', padx=20)

        # Barra de Ferramentas
        toolbar = ttk.Frame(container, style='Main.TFrame', padding=(0, 0, 0, 10))
        toolbar.pack(fill='x')

        ttk.Button(toolbar, text="+ Adicionar PDF", style='Accent.TButton',
                   command=self.detailed_logic.add_pdf).pack(side='left', padx=(0, 10))

        ttk.Button(toolbar, text="Limpar Tudo", style='Back.TButton',
                   command=self.detailed_logic.clear_all).pack(side='left', padx=10)

        ttk.Button(toolbar, text="Salvar PDF Final", style='Accent.TButton',
                   command=self.detailed_logic.save_pdf).pack(side='right')

        # Área de rolagem para os "Cards" das páginas
        scroll_frame_container = ttk.Frame(container, style='Secondary.TFrame')
        scroll_frame_container.pack(fill='both', expand=True)

        self.detailed_canvas = tk.Canvas(scroll_frame_container, bg=self.style_config['bg_secondary'],
                                         highlightthickness=0)
        self.detailed_scrollbar = ttk.Scrollbar(scroll_frame_container, orient="vertical",
                                                command=self.detailed_canvas.yview)

        # Este frame interno conterá os itens
        self.detailed_scrollable_frame = ttk.Frame(self.detailed_canvas, style='Secondary.TFrame')

        self.detailed_canvas_window_id = self.detailed_canvas.create_window((0, 0),
                                                                            window=self.detailed_scrollable_frame,
                                                                            anchor="nw")

        self.detailed_scrollable_frame.bind("<Configure>", lambda e: self.detailed_canvas.configure(
            scrollregion=self.detailed_canvas.bbox("all")))
        self.detailed_canvas.bind('<Configure>',
                                  lambda e: self.detailed_canvas.itemconfig(self.detailed_canvas_window_id,
                                                                            width=e.width))

        self.detailed_canvas.configure(yscrollcommand=self.detailed_scrollbar.set)

        self.detailed_canvas.pack(side="left", fill="both", expand=True)
        self.detailed_scrollbar.pack(side="right", fill="y")

        # Barra de status
        self.lbl_status_detailed = ttk.Label(container, text="Adicione arquivos para começar.", style='Status.TLabel',
                                             anchor="center")
        self.lbl_status_detailed.pack(fill="x", pady=5)

    def refresh_detailed_list(self):
        """Redesenha a lista de páginas baseada na lógica."""
        # Limpa widgets antigos
        for widget in self.detailed_scrollable_frame.winfo_children():
            widget.destroy()

        pages = self.detailed_logic.pages

        if not pages:
            lbl = ttk.Label(self.detailed_scrollable_frame, text="A lista está vazia.",
                            style='TLabel', background=self.style_config['bg_secondary'])
            lbl.pack(pady=20)
            return

        for index, page_data in enumerate(pages):
            # Container do Item (Card)
            item_frame = tk.Frame(self.detailed_scrollable_frame, bg='#454545', bd=1, relief='solid')
            item_frame.pack(fill='x', pady=2, padx=5)

            # Coluna 1: Imagem
            if page_data.get('display_image'):
                img_lbl = tk.Label(item_frame, image=page_data['display_image'], bg='#454545')
                img_lbl.pack(side='left', padx=10, pady=5)

            # Coluna 2: Informações
            info_frame = tk.Frame(item_frame, bg='#454545')
            info_frame.pack(side='left', fill='both', expand=True, padx=10)

            tk.Label(info_frame, text=f"Pág {index + 1}", font=('Segoe UI', 12, 'bold'),
                     bg='#454545', fg='white', anchor='w').pack(fill='x')
            tk.Label(info_frame, text=f"Origem: {page_data['original_filename']}",
                     font=('Segoe UI', 9), bg='#454545', fg='#CCCCCC', anchor='w').pack(fill='x')
            tk.Label(info_frame, text=f"Pág Original: {page_data['page_index'] + 1}",
                     font=('Segoe UI', 9), bg='#454545', fg='#CCCCCC', anchor='w').pack(fill='x')

            # Coluna 3: Botões de Controle
            ctrl_frame = tk.Frame(item_frame, bg='#454545')
            ctrl_frame.pack(side='right', padx=10)

            # Usando lambda com default value (i=index) para capturar o valor atual do loop
            btn_up = ttk.Button(ctrl_frame, text="▲", width=3, style='Small.TButton',
                                command=lambda i=index: self.detailed_logic.move_page_up(i))
            btn_up.pack(pady=2)

            btn_down = ttk.Button(ctrl_frame, text="▼", width=3, style='Small.TButton',
                                  command=lambda i=index: self.detailed_logic.move_page_down(i))
            btn_down.pack(pady=2)

            btn_del = ttk.Button(ctrl_frame, text="✖", width=3, style='Small.TButton',
                                 command=lambda i=index: self.detailed_logic.remove_page(i))
            btn_del.pack(pady=2)

    # Métodos auxiliares
    def select_pdf_to_split(self):
        path = filedialog.askopenfilename(filetypes=[("Arquivos PDF", "*.pdf")])
        if path:
            self.splitter_logic.set_file(path)
            self.lbl_split_file.config(text=f"Arquivo: {os.path.basename(path)}")
            self.btn_split_action.config(state="normal")
            self.update_status("Arquivo selecionado.")

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
                self.update_status(f"{len(self.merger_logic.pdf_files_map)} pastas encontradas.")
            else:
                self.update_status(f"{sum(len(v) for v in self.merger_logic.pdf_files_map.values())} arquivos.")

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window_id, width=event.width)

    def _on_mouse_wheel(self, event):
        # Detecta qual canvas está visível para rolar o correto
        # Simplificação: tenta rolar ambos, o que não estiver visível ignora ou não tem efeito visual
        delta = 0
        if system() == 'Linux':
            delta = -1 if event.num == 4 else 1
        elif system() == 'Windows':
            delta = -int(event.delta / 120)
        elif system() == 'Darwin':
            delta = event.delta

        # Aplica rolagem
        self.canvas.yview_scroll(delta, "units")
        self.detailed_canvas.yview_scroll(delta, "units")

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
            label = ttk.Label(dir_frame, text=f"Diretório: {rel_path if rel_path != '.' else 'Raiz'}",
                              style='Header.TLabel', font=self.app.style_config['font_bold'],
                              background=self.style_config['bg_secondary'])
            label.pack(anchor="w", pady=(0, 5))
            listbox = Listbox(dir_frame, selectmode="single", height=len(files), bg='#4F4F4F',
                              fg=self.style_config['fg_color'], font=self.style_config['font_normal'],
                              highlightthickness=0, borderwidth=1, relief="solid")
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
                          borderwidth=1, relief="solid")
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
        # Atualiza labels de status em todas as views
        if hasattr(self, 'lbl_status') and self.lbl_status.winfo_exists():
            self.lbl_status.config(text=message)
        if hasattr(self, 'lbl_status_splitter') and self.lbl_status_splitter.winfo_exists():
            self.lbl_status_splitter.config(text=message)
        if hasattr(self, 'lbl_status_detailed') and self.lbl_status_detailed.winfo_exists():
            self.lbl_status_detailed.config(text=message)
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