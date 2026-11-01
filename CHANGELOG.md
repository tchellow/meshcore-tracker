# Histórico de versões

## [0.2.1] - 2026-10-31

A versão 0.2.0 não foi publicada. A tag `v0.2.0` aponta para um commit incorreto e não tem instaladores.

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
