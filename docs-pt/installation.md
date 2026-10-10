# Instalação

## Ubuntu 26.04 com Apptainer

Nesta branch a execução usa Apptainer diretamente no host Ubuntu. O instalador
foi adaptado da `develop-SIF3-MAC`, mantendo o caminho de instalação Linux:

```bash
git clone -b feat/develop/ubuntu26.04 https://github.com/camilodotto/ViralFlow.git
cd ViralFlow
bash install.sh --repo-dir "$PWD"
export PATH="$HOME/.local/bin:$PATH"
viralflow --version
```

O instalador cria o ambiente Micromamba, instala Java 17 e Nextflow 23.10.1
com o launcher compacto, que resolve dependências no primeiro uso.
Reutiliza o Apptainer instalado ou o instala
pelo PPA oficial para Ubuntu. Pacotes do sistema e mapeamentos fakeroot
ausentes usam `sudo`. Pangolin e snpEff continuam como **diretórios sandbox**,
apesar da extensão `.sif`; as demais imagens continuam em formato SIF.
Não é necessário instalar Docker Engine.

Para usar o checkout e as dependências de sistema existentes:

```bash
bash install.sh --repo-dir "$PWD" --no-update --skip-system-packages
```

Use `--dry-run` para simular, `--skip-containers` para instalar somente o
ambiente de execução e `--no-path-update` para preservar os arquivos de
inicialização do shell. `--install-root` e `--bin-dir` permitem instalações
separadas. Alterações locais no checkout são preservadas. Basta ter
`unsquashfs` no `PATH`; não é necessário criar links em `/usr/local/bin`.

O comando `viralflow` gerado seleciona o Java do ambiente Micromamba e mantém
o cache Nextflow na raiz da instalação. Execução direta pelo Nextflow exige
versão >=23.10.1 e Java 17. As definições ARM64 foram mantidas, mas a validação
neste host é AMD64.

Consulte o [registro da migração](../UBUNTU26.04-CHANGES.md) para as alterações
por arquivo e os resultados da validação. As instruções manuais abaixo
descrevem as instalações Ubuntu anteriores; nesta branch prefira o instalador.

## Instalação no MacOS

Devido a limitações do uso do singularity no MacOS, para rodar o ViralFlow neste tipo de sistema, sugerimos a utilização de um software de virtualização Linux chamado [Lima](https://github.com/lima-vm/lima).

### Instalando o Lima

Instale o Lima utilizando o gerenciador de pacotes Homebrew:

```bash
brew install lima
```

### Instalando a instância Ubuntu

Siga o passo a passo da instalação de uma instância Ubuntu:

```bash
limactl start
```

### Inicie o Ubuntu

Quando a máquina virtual for instalada, utilize o comando abaixo para iniciar o Ubuntu e siga os passos de instalação do ViralFlow normalmente:

```bash
lima
```

## Instalação no Ubuntu

Para realizar a instalação do ViralFlow, são necessários quatro passos:
1. Instalar as dependências de sistema
2. Instalar o Conda
3. Instalar o ViralFlow
4. Montar os containers para as análises

Este processo é realizado uma única vez.

A instalação e uso do ViralFlow já foi testada nos sistemas:
- Ubuntu 20.04 LTS
- Ubuntu 22.04 LTS

### Instalando as Dependências do Sistema

Caso você não tenha o instalador de dependências pip, o sistema de controle de versões git, e o pacote uidmap, você deve realizar a instalação com as seguintes linhas:

```bash
sudo apt update -y && \
  sudo apt upgrade -y && \
  sudo apt install curl git python3-pip uidmap -y
```

### Instalando e Configurando o Ambiente Micromamba

Recomendamos o gerenciador de ambientes micromamba devido a sua paralelização ao fazer o download e instalação das dependências. Caso você utilize outro gerenciador de ambientes (conda, miniconda, mamba), você pode pular esta etapa, porém, conflitos durante a instalação podem ocorrer.

Caso você não tenha o gerenciador de ambientes micromamba instalado:

```bash
cd $HOME
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/1.5.7 | tar -xvj bin/micromamba
./bin/micromamba shell init -s bash -p ~/micromamba
source ~/.bashrc
micromamba activate
```

### Instalando o ViralFlow

Caso você já tenha as dependências citadas e o conda instalado, você pode instalar o ViralFlow com 5 linhas de código:

```bash
git clone https://github.com/WallauBioinfo/ViralFlow
cd ViralFlow/
micromamba env create -f envs/env.yml
micromamba activate viralflow
pip install -e .
```

### Construindo os Containers

Todas as etapas do ViralFlow são executadas em ambientes controlados. O ViralFlow possui um método próprio para realizar toda essa construção de ambientes, rodando apenas uma linha de código.

Para que a construção dos containers ocorra, o ViralFlow necessita que a ferramenta "unsquashfs" esteja disponível no diretório `/usr/local/bin/`. Para garantir isto, crie um link simbólico:

```bash
sudo ln -s /usr/bin/unsquashfs /usr/local/bin/unsquashfs
```

Após garantir que o unsquashfs esteja no local apropriado, rode o comando para a construção dos containers:

```bash
viralflow build_containers
```

```{note}
Este processo irá baixar aproximadamente 4,4GB de imagens de containers. Certifique-se de ter espaço suficiente em disco e uma conexão de internet estável.
```
