# Histórico de versões

## [0.3.1] - 2026-11-01

### Correções

- **Bluetooth preso em "Reconectando...":** depois de uma falha na conexão, como ao voltar da suspensão do computador, o programa segurava a conexão antiga. O rádio parava de anunciar e só voltava ao fechar o programa. Agora a conexão é sempre liberada antes de tentar de novo.
- **Falso erro de pareamento:** quando o Windows conclui o pareamento sem avisar, o programa agora confere o estado real em vez de mostrar uma falha.

### Situação dos testes

- **Windows:** a queda foi reproduzida com rádio real (T1000-E): a v0.3.0 reconectou 0 de 3 vezes, e esta versão, 3 de 3. A falha foi simulada; a volta de uma suspensão real ainda não foi testada.
- **Windows, pareamento:** a nova conferência só atua quando o Windows não responde a tempo, e essa situação não se repetiu nos testes.
- **Windows, reconexão com o pareamento guardado:** T-Deck, T1000-E e ProMicro NRF52840 reconectaram, mas o ProMicro oscilou em um dos testes (2 de 6, depois 6 de 6). Para uso contínuo, prefira a USB.
- **Ubuntu:** instalação e janela testadas automaticamente, sem rádio real. O Bluetooth não foi testado nesse sistema.

## [0.3.0] - 2026-11-01

### Novidades

- Conexão por Bluetooth, além do USB, com busca dos rádios por perto.
- **Windows:** ao conectar um rádio Bluetooth sem pareamento, o programa pede o PIN e faz o pareamento. O PIN não fica guardado no programa.
- **Ubuntu:** o pareamento continua sendo feito nas configurações de Bluetooth do sistema.
- O status mostra **Conectando...** enquanto a conexão é feita.

### Correções

- Rádios com muitos contatos não falham mais ao conectar. Por Bluetooth, uma lista com centenas de contatos pode levar perto de um minuto.
- A mensagem de falha na USB agora orienta a verificar se o firmware é Bluetooth ou Wi-Fi em vez de USB.
- A janela não mostra mais uma página antiga guardada em cache depois de uma atualização.

### Situação dos testes

- **Windows, Bluetooth:** pareamento e conexão testados com rádio real (ProMicro NRF52840 e T-Deck).
- **Windows, USB:** conexão testada com rádio real (ProMicro NRF52840 e T-Deck). Telemetria testada pelo ProMicro.
- **Ubuntu:** instalação e janela testadas automaticamente, sem rádio real. O Bluetooth não foi testado nesse sistema.
- **Rádio que pareava, mas caía ao reconectar:** um dos rádios testados só voltou a funcionar depois de apagar os dados e regravar o firmware. Veja [Solução de problemas](docs/solucao-de-problemas.md#a-conexão-bluetooth-falha-ou-cai).
- **Pareamento instável:** o Windows às vezes recusa o pedido sem motivo aparente, e o programa tenta de novo sozinho. Se o rádio for regravado, remova o pareamento antigo nas configurações do Windows.

## [0.2.2] - 2026-10-31

As versões 0.2.0 e 0.2.1 não foram publicadas e não têm instaladores. A tag `v0.2.0` aponta para um commit incorreto, e a `v0.2.1` não passou nos testes do instalador.

### Novidades

- O programa abre em janela própria, maximizada, com ícone na barra de título.
- Fechar a janela encerra o programa, e os pedidos de telemetria param.
- Abrir o programa de novo traz a janela aberta para a frente, sem iniciar outra cópia.
- O ícone aparece ao lado do nome, no cabeçalho.
- **Sair** agora pede confirmação no próprio menu.

### Mudanças na instalação

- **Windows:** a janela usa o Microsoft Edge WebView2. Sem ele, o programa abre no navegador.
- **Ubuntu:** o pacote agora usa o Python e o WebKitGTK do sistema, instalados pelo `apt`. Sem eles, o programa abre no navegador.

### Situação dos testes

- **Windows:** janela e telemetria testadas com rádio real (ProMicro NRF52840) e dois nodes companion a até 1 hop.
- **Ubuntu 22.04 e 24.04:** instalação e janela testadas automaticamente, em tela virtual, ainda sem rádio real.
- **Ainda não testado com rádio real:** rotas lentas de vários hops e remoção do cabo durante o uso.

No Windows, o instalador não tem assinatura digital, então o SmartScreen pode exibir um aviso. Veja a [documentação de instalação](https://github.com/tchellow/meshcore-tracker/blob/main/docs/instalacao.md).

## [0.1.0] - 2026-10-31

Primeira versão pública.

### Recursos

- Conexão com rádio MeshCore com firmware Companion USB, com nome do dispositivo, status, tempo conectado ou desconectado e reconexão automática.
- Automação de telemetria com posição, por contato, de 15 segundos a 5 horas.
- Mapa com a última posição, um ícone colorido por contato e detalhes de bateria, altitude e temperatura.
- Espera e intervalo adaptados ao tempo de resposta de cada contato.
- Rota salva apagada depois de 2 falhas seguidas, para o pedido seguinte sair por flood.
- Instaladores para Windows e Ubuntu, sem exigir Python.

### Situação dos testes

- **Windows:** testado com rádio real (ProMicro NRF52840) e dois nodes companion a até 1 hop.
- **Ubuntu:** instalação e abertura testadas automaticamente, ainda sem rádio real.
- **Ainda não testado com rádio real:** rotas lentas de vários hops e remoção do cabo durante o uso.

### Instalação

No Windows, o instalador não tem assinatura digital, então o SmartScreen pode exibir um aviso. Veja a [documentação de instalação](https://github.com/tchellow/meshcore-tracker/blob/main/docs/instalacao.md).
