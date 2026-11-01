# Instalação

Baixe os arquivos na página de [versões](https://github.com/tchellow/meshcore-tracker/releases/latest). O instalador já inclui o Python e as bibliotecas.

## Windows 10 ou 11 (64 bits)

1. Baixe `MeshcoreTracker-<versão>-windows-x64-setup.exe`.
2. Dê dois cliques no arquivo e siga os passos. Não é preciso ser administrador.
3. Abra o programa pelo Menu Iniciar.

### Aviso do SmartScreen

O instalador não tem assinatura digital paga, então o Windows pode avisar que o editor é desconhecido. Para continuar, clique em **Mais informações** e depois em **Executar assim mesmo**.

Se quiser, confira a integridade do arquivo com o `SHA256SUMS.txt` da mesma página:

```powershell
Get-FileHash .\MeshcoreTracker-<versão>-windows-x64-setup.exe -Algorithm SHA256
```

### Atualizar ou desinstalar

Para atualizar, execute o instalador da versão nova. Ele encerra o programa aberto antes de instalar.

Para desinstalar, use **Configurações > Aplicativos**. Seus contatos e posições ficam em `%LOCALAPPDATA%\MeshcoreTracker`. Apague essa pasta se quiser remover também os dados.

## Ubuntu 22.04 ou mais novo (amd64)

```bash
sudo apt install ./MeshcoreTracker-<versão>-ubuntu-amd64.deb
```

O caminho precisa começar com `./`, ou o `apt` procura o nome nos repositórios. Depois, abra pelo menu de aplicativos ou com `meshcore-tracker`.

Confira a integridade do arquivo, se quiser, na pasta do download:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing
```

### Acesso à USB

O pacote instala uma regra `udev` que dá ao usuário com sessão ativa acesso às portas seriais USB, sem precisar do grupo `dialout`. Ela vale para todas as portas seriais USB do computador. Se o rádio já estava ligado, desconecte e conecte de novo depois de instalar.

Em outras distribuições derivadas do Debian, o pacote pode funcionar, mas não é testado.

### Atualizar ou desinstalar

Para atualizar, instale o `.deb` da versão nova da mesma forma. Para desinstalar:

```bash
sudo apt remove meshcore-tracker
```

Seus dados ficam em `~/.local/share/meshcore-tracker`. Apague essa pasta se quiser removê-los.

## Rodar a partir do código

Com Python 3.10 ou mais novo, use `iniciar.bat` no Windows ou `bash iniciar.sh` no Ubuntu. Os scripts criam o ambiente e instalam as dependências. No Ubuntu, o `iniciar.sh` não instala a regra `udev`, então é preciso entrar no grupo `dialout`:

```bash
sudo apt install python3-venv
sudo usermod -aG dialout $USER   # uma vez; depois saia e entre na sessão
```
