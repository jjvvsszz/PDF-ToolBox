# app.py
import tkinter as tk
from tkinter import ttk
from ui_components import UIComponents
from merger_logic import MergerLogic


class PDFToolboxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Toolbox")
        self.root.geometry("900x700")
        self.root.minsize(700, 550)

        self.setup_styles()

        # Container principal que ocupará toda a janela.
        # As diferentes "views" (menu, merger, etc.) serão exibidas aqui.
        main_container = ttk.Frame(self.root, style='Main.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True)

        # Inicializa a lógica e a UI
        self.merger_logic = MergerLogic(self)
        self.ui = UIComponents(self.root, self, main_container)

        # Exibe o menu principal ao iniciar a aplicação
        self.ui.show_view('main_menu')

    def setup_styles(self):
        self.style_config = {
            'bg_color': '#2E2E2E', 'bg_secondary': '#3C3C3C', 'fg_color': '#EAEAEA',
            'accent_color': '#007ACC', 'accent_fg': '#FFFFFF',
            'font_normal': ('Segoe UI', 10), 'font_bold': ('Segoe UI', 11, 'bold'),
            'font_info': ('Segoe UI', 9), 'font_header': ('Segoe UI', 18, 'bold')
        }
        self.root.configure(bg=self.style_config['bg_color'])
        style = ttk.Style()
        style.theme_use('clam')

        # Estilos gerais
        style.configure('Main.TFrame', background=self.style_config['bg_color'])
        style.configure('Secondary.TFrame', background=self.style_config['bg_secondary'])
        style.configure('TLabel', background=self.style_config['bg_color'], foreground=self.style_config['fg_color'],
                        font=self.style_config['font_normal'])
        style.configure('Info.TLabel', font=self.style_config['font_info'])
        style.configure('Status.TLabel', font=self.style_config['font_info'])
        style.configure('Header.TLabel', font=self.style_config['font_header'], anchor='center')

        # Estilos de Botões
        style.configure('Accent.TButton', font=self.style_config['font_bold'],
                        background=self.style_config['accent_color'], foreground=self.style_config['accent_fg'],
                        borderwidth=0, padding=10)
        style.map('Accent.TButton', background=[('active', '#005f9e')])

        # Estilo para os botões do Menu Principal
        style.configure('Menu.TButton', font=self.style_config['font_bold'], padding=(20, 15), width=20)

        # Estilo para o botão "Voltar"
        style.configure('Back.TButton', font=('Segoe UI', 9), padding=8)

        # Estilo para o switch
        style.configure('Switch.TFrame', background=self.style_config['bg_color'])
        style.configure('Switch.TCheckbutton', background=self.style_config['bg_color'],
                        foreground=self.style_config['fg_color'], font=self.style_config['font_normal'],
                        indicatoron=False, borderwidth=0, padding=5)
        style.map('Switch.TCheckbutton',
                  background=[('active', self.style_config['accent_color']),
                              ('selected', self.style_config['accent_color'])],
                  foreground=[('active', self.style_config['accent_fg']), ('selected', self.style_config['accent_fg'])])