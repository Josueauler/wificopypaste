# Wifi CopyPaste

Copie no celular, cole no PC. Envie textos, fotos, vídeos, PDFs e qualquer arquivo do Android para o computador pela rede Wi-Fi, sem cabo, sem nuvem e sem conta.

O projeto tem três partes que se complementam:

| Parte | Arquivo / app | O que faz |
|---|---|---|
| **Receptor para PC** | `planilha.py` (Wifi CopyPaste) | Recebe os itens enviados pelo celular, mostra tudo em uma lista e permite copiar, abrir e apagar. |
| **App para Android** | Transferência Wi-Fi (`main.py` + `buildozer.spec`) | Envia textos e arquivos do celular para o PC. |
| **Espelhar celular** | `script.py` (Glass) | Assistente que espelha a tela do celular no Mac usando scrcpy e adb. Abre pelo botão **Espelhar celular** do app para PC. |

---

## Como funciona

1. O PC abre uma porta de escuta (TCP **5055**) e mostra o endereço IP e um **PIN de 6 dígitos**.
2. O celular encontra o PC sozinho na mesma rede (descoberta por UDP, porta **5056**) ou você digita o IP.
3. O celular se identifica com o PIN. Se o PIN estiver certo, o PC aceita o texto ou o arquivo e salva em `Downloads/Transferencia`.

Tudo acontece dentro da sua rede local. Não há servidor externo, conta nem coleta de dados.

---

## Começando em 3 passos

1. **Transfira a versão do seu sistema** para o PC, usando o Bluetooth do celular (ou baixe pelo navegador do PC).
2. **Instale-o no seu PC.**
3. **Comece a usar:** abra o programa no PC, informe no celular o IP e o PIN mostrados nele e envie.

O app Android mostra esse mesmo tutorial na primeira abertura, e o botão **Ver tutorial** reabre quando quiser.

---

## Receptor para PC (`planilha.py`)

### Requisitos

- Python 3
- `pip install customtkinter pillow`
- Opcional: `pip install pymupdf` para mostrar a miniatura da primeira página dos PDFs

### Executar

```bash
python3 planilha.py
```

Na primeira abertura aparece uma **tela de boas-vindas**. Ela só é exibida uma vez; para vê-la de novo, apague o arquivo `.wifi_copypaste.json` da sua pasta de usuário.

### Recursos

- **Conexão:** mostra o endereço do PC (IP:porta) e o PIN de pareamento, com botão **Gerar novo PIN**.
- **Itens recebidos:** cada texto, imagem, vídeo ou arquivo vira um cartão com horário, aparelho de origem, tamanho e barra de progresso durante o recebimento.
- **Textos:** são copiados sozinhos para a área de transferência (opção **Copiar textos recebidos automaticamente**, que pode ser desligada).
- **Imagens:** aparecem com miniatura de bordas arredondadas. PDFs mostram a primeira página quando o `pymupdf` está instalado.
- **Copiar:** o ícone de copiar no cartão copia o texto, a imagem ou o próprio arquivo para a área de transferência. Para colar um arquivo copiado em uma pasta ou e-mail, o app usa o recurso nativo do sistema (macOS, Windows ou Linux com `xclip`/`wl-copy`).
- **Abrir e mostrar na pasta:** abre o arquivo ou revela ele no Finder/Explorer.
- **Excluir:** o ícone de lixeira remove o item do app **e apaga o arquivo da pasta**. **Excluir tudo** faz o mesmo com todos.
- **Auto-excluir:** apaga cada item depois de um tempo digitado por você (segundos, minutos ou horas), contado a partir do recebimento, com contagem regressiva no cartão.
- **Pasta de recebidos:** abre `Downloads/Transferencia`. Se já existir um arquivo com o mesmo nome, o novo recebe `(1)`, `(2)` e assim por diante.
- **Espelhar celular:** o botão com gradiente lilás e azul, no topo, abre o `script.py` em uma janela própria (veja a seção abaixo).
- **Apoie o dev:** o link **Doe um café pro dev** (na boas-vindas e na barra lateral) abre o `pix.png`.

### Imagens usadas pelo app

Coloque estes PNGs na mesma pasta do `planilha.py`. Se algum faltar, o app continua funcionando, só sem aquele ícone.

| Arquivo | Onde aparece |
|---|---|
| `icone.png` | Ícone da janela, logo da barra lateral e tela de boas-vindas |
| `mensagem.png` | Cartões de texto |
| `imagem.png` | Cartões de imagem |
| `vídeo.png` | Cartões de vídeo |
| `arquivo.png` | Cartões de PDF e de qualquer outro arquivo |
| `lixeira.png` | Botão de excluir |
| `copiar.png` | Botão de copiar |
| `ok.png` | Ao lado de "Salvo" |
| `transmitir.png` | Botão **Espelhar celular** |
| `pix.png` | Janela do Pix (QR Code ou chave) |

---

## App para Android (Transferência Wi-Fi)

### O que tem

- Tutorial de três passos na primeira abertura.
- Campos de **IP** e **PIN** (teclado numérico, 6 dígitos), botões **Buscar PC** e **Conectar**, e indicador de conexão no cabeçalho.
- **PCs salvos:** depois de conectar, o computador fica na lista (até dez). Tocar em um deles preenche o IP e vai direto ao PIN. O **PIN nunca é salvo**.
- **Barra de escrever** fixa embaixo, como num chat, que sobe junto com o teclado: grampo para anexar arquivos, campo de texto e botão de enviar.
- **Balões** do histórico da sessão, com miniaturas das imagens, cartões por tipo de arquivo e o estado **Enviado** ou **Falhou**.
- Emojis nas mensagens; o texto original é enviado ao PC sem alterações.
- Confirmação ao sair do app.
- Visual escuro com a mesma identidade do app para PC.

### Instalar e usar

1. Instale o APK e autorize aplicativos de fontes externas, se o Android pedir.
2. Deixe o celular e o PC na **mesma rede Wi-Fi** e abra o Wifi CopyPaste no PC.
3. No celular, toque em um PC salvo ou em **Buscar PC** (ou digite o IP), informe o PIN mostrado no PC e toque em **Conectar**.
4. Para mandar arquivos, fotos ou vídeos, toque no **grampo**. Para mandar texto, escreva no campo e toque no botão de enviar.

### Compilar o APK

O app é feito em Kivy e compilado com Buildozer.

```bash
buildozer android debug
```

Pontos de atenção:

- As permissões usadas são de internet e de estado da rede Wi-Fi (incluindo multicast para a busca do PC).
- Se o `buildozer.spec` tiver a linha `p4a.source_dir` apontando para uma pasta local, remova-a ou ajuste o caminho no seu computador.
- Todos os PNGs e a fonte de emojis (`emoji_text.ttf`, licença em `OFL.txt`) precisam ir junto no pacote.
- O APK de depuração ainda deve ser testado em um aparelho físico.

---

## Espelhar celular (`script.py`, Glass)

Assistente em customtkinter para **macOS** que usa o **scrcpy** e o **adb** para mostrar a tela do celular no computador.

### Requisitos

- `pip install customtkinter pillow`
- Pasta do scrcpy para macOS (com os arquivos `scrcpy` e `adb`) extraída, por exemplo, em `~/Downloads`
- Depuração USB / depuração sem fio ativada no celular

### Como usar

Pelo botão **Espelhar celular** do app para PC, ou direto com `python3 script.py`.

O assistente tem as etapas **Aparelho**, **Preparar ferramentas**, **Parear com o celular**, **Conectar**, **Espelhamento** e **Contribua**. Aparelhos já salvos só pedem a porta na hora de conectar, e há uma tela com os detalhes do aparelho conectado.

### Opções de espelhamento

- Resolução: **Monitor**, **Original**, 1920, 1280 ou 1024.
- Apagar a tela do celular durante o espelhamento.
- Manter o celular acordado.
- Manter a janela sempre por cima.

### Modo Monitor (como o DeX)

Ajusta o tamanho da tela do celular ao do seu monitor. O app só faz isso **depois que o aparelho é desbloqueado**; com a tela bloqueada, o espelho mantém o tamanho do próprio aparelho. Se o celular bloquear de novo, o tamanho volta ao normal, e ao parar o espelhamento ou fechar o app tudo é restaurado.

Em **Tamanho dos elementos** (Pequenos, Médios, Grandes) você controla o tamanho de ícones e textos no modo Monitor.

Se o app fechar de repente e o celular ficar com a tela estranha, rode:

```bash
adb shell wm size reset
adb shell wm density reset
```

O app também tenta restaurar sozinho na próxima conexão com o mesmo aparelho. Se o modo Monitor não funcionar bem no seu celular, escolha **Original**.

---

## Estrutura do projeto

```
projeto/
├── planilha.py            # Wifi CopyPaste (receptor para PC)
├── script.py              # Glass: espelhar celular
├── icone.png, mensagem.png, imagem.png, vídeo.png, arquivo.png,
│   lixeira.png, copiar.png, ok.png, transmitir.png, pix.png
└── android/
    ├── main.py            # app Android (Kivy)
    ├── buildozer.spec
    ├── icon.png, presplash.png, logo.png
    ├── send.png, paperclip.png, computer.png
    └── emoji_text.ttf, OFL.txt, FONT_LICENSES.txt
```

Arquivos de configuração criados na pasta do usuário:

- `~/.wifi_copypaste.json`: lembra se a boas-vindas já foi exibida.
- `~/.espelhar_celular.json`: aparelhos salvos e preferências do espelhamento.

---

## Solução de problemas

- **O celular não encontra o PC:** confirme que os dois estão na mesma rede Wi-Fi, que o app do PC está aberto e que o firewall permite as portas TCP 5055 e UDP 5056. Se a busca falhar, digite o IP mostrado no PC.
- **"PIN incorreto":** o PIN muda quando você clica em **Gerar novo PIN** e quando o app do PC é reaberto. Use o valor atual da tela.
- **O PDF não aparece no PC:** confira se o celular está enviando o arquivo completo. Para ver a miniatura do PDF no PC, instale `pymupdf`.
- **Ícones faltando:** coloque os PNGs na mesma pasta do programa, com os nomes da tabela acima.
- **O Glass não abre pelo botão:** o `script.py` precisa estar na mesma pasta do `planilha.py`.

---

## Segurança e privacidade

- Os dados ficam na sua rede local e vão direto do celular para o PC.
- O PIN é verificado a cada envio e **nunca é gravado** no celular.
- O tráfego da rede **não é criptografado**. Use em redes de confiança, como a sua casa, e evite Wi-Fi público.

---

## Apoie o projeto

Se o app foi útil, **doe um café pro dev**: o link está na tela de boas-vindas e na barra lateral do app para PC e abre o Pix.

---

## Licenças de terceiros

- Fonte de emojis do app Android: licença SIL OFL (`OFL.txt`).
- scrcpy e adb são projetos independentes, com suas próprias licenças.
- customtkinter, Pillow, Kivy e PyMuPDF seguem as licenças de cada projeto.
