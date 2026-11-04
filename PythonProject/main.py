import customtkinter as ctk
from tkinter import filedialog
import os
import subprocess

#ESSENCIAL
app = ctk.CTk()
app.title("BootMac")
app.geometry("800x600")
frame= ctk.CTkFrame(app)
frame.pack(fill="both", expand=True, padx=0, pady=0)
app.resizable(False, False)
ctk.set_default_color_theme("dark-blue")
#Funções

#Abrir arquivos
def openiso():
    arquivo = filedialog.askopenfilename(title="Selecionar arquivo ISO",
        filetypes=[("Arquivos ISO", "*.iso"), ("Todos os arquivos", "*.*")])

    if arquivo:
        pasta = os.path.basename(os.path.dirname(arquivo))
        nome_arquivo = os.path.basename(arquivo)

        caminho.delete(0, "end")
        caminho.insert(0, f"{pasta}/{nome_arquivo}")


#Elementos frame Mãe
titulo = ctk.CTkLabel(
    frame,
    text= "BootMac",
    font= ("Arial", 24, "bold"),
    text_color= "white",
)

#Barra Lateral
sidebar = ctk.CTkFrame(
    frame,
    fg_color= "#1E1E1E",
    corner_radius=0,
    width=240
)
sidebar.pack(side="left", fill="y", padx=(0,0))
sidebar.pack_propagate(False)

#DEPENDÊNCIAS SIDE BAR

ambiente= ctk.CTkButton(
    sidebar,
    text= "Ambiente",
    fg_color= "#2B2B2B",
    height= 90,
    hover= False,
)
ambiente.pack(pady=10, fill="x", padx=10)

configurar= ctk.CTkButton(
    sidebar,
    text= "Configurar",
    fg_color= "#2B2B2B",
    height= 90,
    hover= False,
)
configurar.pack(pady=(0,10), fill="x", padx=10)

configuracoes= ctk.CTkButton(
    sidebar,
    text= "Configurações",
    fg_color= "#2B2B2B",
    height= 45,
    hover= False,
)
configuracoes.pack(side="bottom",pady=(0,10), fill="x", padx=10)

#frame finder iso
finderiso = ctk.CTkFrame(
    frame,
    corner_radius=10
)

finderiso.pack(
    side="top",
    expand=False,
    padx=10,
    pady=10
)

#DEPENDÊNCIAS

#botao de ação para achar a ISO
button_iso=ctk.CTkButton(
    finderiso,
    text= "Buscar",
    width=30,
    height=30,
    font=("Arial", 14, "bold"),
    hover_color="#4DA6FF",
    command= openiso
)
button_iso.grid(row=0,column=1, padx=10,pady=10)

#Botão de confirmar e ir para o próximo frame
button_confirm=ctk.CTkButton(
    finderiso,
    text= "Confirmar",
    width=30,
    height=30,
    font=("Arial", 14),
    fg_color= "#2B2B2B",
    hover= False,
    border_width=0,
    command= openiso
)
button_confirm.grid(row=2,column=0, padx=10,pady=(0,10), sticky="w")

caminho = ctk.CTkEntry(
    finderiso,
    fg_color= "white",
    border_width=0,
    text_color= "black",
    placeholder_text="/Arquivo.ISO",
    width=450,
    height=30,
)
caminho.grid(row=0,column=0,padx=(10,0),pady=10)

#Finder pendrive
finderpen = ctk.CTkFrame(
    frame,
    corner_radius=10
)

finderpen.pack(
    side="top",
    expand=False,
    padx=10,
    pady=0
)

button_iso=ctk.CTkButton(
    finderpen,
    text= "Buscar",
    width=30,
    height=30,
    font=("Arial", 14, "bold"),
    hover_color="#4DA6FF",
    command= openiso
)
button_iso.grid(row=0,column=1, padx=10,pady=10)

#Botão de confirmar e ir para o próximo frame
button_confirm=ctk.CTkButton(
    finderpen,
    text= "Confirmar",
    width=30,
    height=30,
    font=("Arial", 14),
    fg_color= "#2B2B2B",
    hover= False,
    border_width=0,
    command= openiso
)
button_confirm.grid(row=2,column=0, padx=10,pady=(0,10), sticky="w")

#Entry do botão
caminho = ctk.CTkEntry(
    finderpen,
    fg_color= "white",
    border_width=0,
    text_color= "black",
    placeholder_text="/Desino",
    width=450,
    height=30,
)
caminho.grid(row=0,column=0,padx=(10,0),pady=10)

def openiso():
    arquivo = filedialog.askopenfilename()

    if arquivo:
        pasta = os.path.basename(os.path.dirname(arquivo))
        nome_arquivo = os.path.basename(arquivo)

        caminho.delete(0, "end")
        caminho.insert(0, f"{pasta}/{nome_arquivo}")


app.mainloop()
