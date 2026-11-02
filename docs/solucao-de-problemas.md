# Solução de problemas

## Conexão

### “Não foi possível conectar pela USB”

Causas mais comuns:

1. **Firmware Bluetooth ou Wi-Fi:** o rádio não responde pelo cabo com esses firmwares, mesmo que a porta apareça na lista. Grave o **Companion USB** com o MeshCore Flasher.
2. **Porta ocupada:** outro programa está usando o rádio, como o MeshCore Web App no navegador ou um monitor serial. Feche-o e tente de novo.
3. **Rádio iniciando:** espere alguns segundos depois de ligar o rádio.

### O rádio não aparece na lista

- Clique em **Procurar** na tela de Conexão.
- Troque o cabo. Alguns cabos USB só carregam e não transmitem dados.
- No Windows, placas com chip conversor podem precisar do driver CP210x ou CH340.

### Ubuntu: sem acesso à porta

- Desconecte e conecte o rádio depois de instalar o pacote.
- Se o erro continuar, rode `sudo usermod -aG dialout $USER`, saia e entre na sessão.
- O serviço ModemManager pode ocupar a porta por alguns segundos ao ligar o rádio. Se isso se repetir, teste com `sudo systemctl stop ModemManager`.

### A conexão Bluetooth falha ou cai

- **Pareamento:** no Windows, o programa pede o PIN ao conectar um rádio sem pareamento. No Ubuntu, pareie nas configurações de Bluetooth do sistema. Se não funcionar, remova o pareamento antigo nas configurações do sistema e faça de novo.
- **"O rádio recusou o pareamento":** confira o PIN. Em rádios sem tela, o padrão costuma ser `123456`.
- **"O rádio não atendeu ao pareamento":** confira se ele está ligado, perto do computador e sem outro aparelho conectado.
- **Pareia, mas cai ao reconectar:** se o rádio pareia e a conexão cai em cerca de 1 segundo, mesmo refazendo o pareamento, ele pode ter dados antigos de pareamento. Em um dos rádios testados, atualizar o firmware não bastou, e funcionou apagar os dados e regravar. Exporte antes o que puder, porque isso pode apagar os contatos e a identidade do node. Depois, remova o rádio nas configurações do sistema e no celular.
- **Depois de suspender o computador:** a conexão cai durante a suspensão, e o programa tenta reconectar ao voltar. Enquanto o computador estiver suspenso, nenhum pedido de telemetria é enviado. Para rastreamento contínuo, ajuste as opções de energia do sistema.
- **Outro aparelho conectado:** desconecte o celular e o MeshCore Web App. O rádio só aceita uma conexão, e o app do celular pode reconectar sozinho.
- **Firmware:** confira se é o **Companion Bluetooth**.
- **Sinal:** aproxime o rádio do computador. Wi-Fi e outros aparelhos Bluetooth podem interferir.
- **Falhas em sequência:** aguarde um pouco. O programa tenta reconectar sozinho a cada 15 segundos enquanto o rádio estiver salvo, e cada rodada pode levar até cerca de 1 minuto. Se persistir, desligue e ligue o rádio ou o Bluetooth do computador.
- **Uso contínuo:** se a instabilidade continuar, prefira a conexão USB.

### O rádio não aparece na lista de Bluetooth

Um rádio conectado a outro aparelho não anuncia. Desconecte-o, espere alguns segundos e clique em **Procurar**.

No Ubuntu, confira se o Bluetooth está ligado e se o pacote `bluez` está instalado.

## Automação

### “Sem resposta”

- Confira se o outro node está ligado e ao alcance da malha.
- Clique em **Pedir agora** para testar de novo.
- Com 2 falhas seguidas, o programa apaga a rota e tenta por flood.
- Confira se o contato autorizou este rádio a pedir telemetria.

### “Respondeu sem GPS”

O node respondeu, mas sem posição. Normalmente, é por um destes motivos:

- O GPS está sem sinal. Leve o node para um lugar aberto.
- A permissão de localização não foi dada a este rádio.
- O node não tem GPS, nem posição configurada.

### “Não está no rádio”

O contato saiu da lista do rádio, por exemplo depois de gravar o firmware. Faça o node aparecer de novo no rádio, clique em **Atualizar lista** e, se preciso, remova e adicione o contato no programa.

### O intervalo real é maior que o escolhido

É o esperado em uma rota lenta. Veja [Como a automação funciona](automacao.md).

## Mapa e tela

### O mapa fica em branco

O mapa do OpenStreetMap precisa de internet. A automação continua funcionando sem ela.

### “Sem comunicação com o programa”

O programa foi encerrado. Abra de novo pelo Menu Iniciar ou pelo menu de aplicativos.

### O programa abriu no navegador

O motor da janela não foi encontrado, e o programa continua funcionando no navegador:

- **Windows:** instale o [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/).
- **Ubuntu:** rode `sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1`.

Nesse modo, fechar a aba não encerra o programa. Use **Sair** no menu da engrenagem.

### A janela não abre

Se outro programa estiver usando a porta 8790, o Meshcore Tracker não consegue iniciar. Veja o arquivo de registro abaixo.

## Windows

### O SmartScreen bloqueia o instalador

Veja [Instalação](instalacao.md#aviso-do-smartscreen).

## Registros e dados

O programa instalado grava os erros em `tracker.log`, na pasta de dados:

- **Windows:** `%LOCALAPPDATA%\MeshcoreTracker`
- **Ubuntu:** `~/.local/share/meshcore-tracker`

O banco `tracker.db`, na mesma pasta, guarda os contatos rastreados e a posição deles. Não publique esses arquivos em uma issue sem revisar, porque contêm nomes e localizações.

## Relatar um problema

Abra uma [issue](https://github.com/tchellow/meshcore-tracker/issues) com o sistema, a versão (no menu da engrenagem), o modelo do rádio e os passos que levam ao erro.
