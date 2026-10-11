# Diferenças de develop-SIF3-MAC em relação a WallauBioinfo/develop

## Resumo

A branch `develop-SIF3-MAC` reúne adaptações de instalação e execução para
Linux/WSL AMD64 e ARM64 e para macOS por meio de uma VM Linux ARM64 do Lima.
Inclui um instalador próprio, separa Nextflow do ambiente Conda e exige
Apptainer nos comandos de construção, download e manutenção dos containers.

Pangolin e snpEff passam a ser construídos como imagens SIF, com overlays
persistentes separados para atualizações e bancos locais. A construção usa
uma área de trabalho no sistema de arquivos Linux, permitindo manter o
repositório em uma pasta macOS compartilhada com a VM. Os overlays são montados
como somente leitura durante a execução normal da pipeline.

As diferenças também incluem preparação e validação do banco snpEff, novas
opções no CLI, atualização dinâmica do Pangolin, quatro gráficos SVG nos
resultados e correções dos nomes de comandos na documentação. Dois módulos
Nextflow foram alterados: a verificação do banco snpEff e o tratamento dos
cabeçalhos dos arquivos de saída do iVar.

Nextflow permanece com **22.04.0 como versão padrão** no instalador e no wrapper;
a configuração da pipeline continua usando o backend **`singularity`**.
Micromamba **1.5.7** é a versão baixada pelo instalador quando o binário local
não existe. Java **17** permanece nos ambientes ativos. Essas versões são as
desta branch, independentemente das versões selecionadas pela GUI em outro
repositório.

A referência da comparação é `WallauBioinfo/develop`, commit
`16cb3f30b1d3`. O conteúdo de `develop-SIF3-MAC` foi conferido a partir do
commit `c108466598cd`, incluindo a reescrita deste documento no diretório de
trabalho. São **36 arquivos diferentes: 26 modificados e 10 adicionados**.
Nenhum arquivo da referência foi removido. A comparação inclui documentação,
instalador, testes e arquivos auxiliares, sem organização por datas ou commits.

## Diferenças por arquivo

### `.gitignore` — modificado

Acrescenta a exclusão de `vfnext/containers/*.overlay`, evitando versionar os
arquivos persistentes locais dos containers. Também acrescenta uma quebra de
linha ao final do arquivo. As exclusões de imagens SIF e demais artefatos
preexistentes permanecem.

### `.readthedocs.yaml` — modificado

Remove uma linha final que continha somente espaços e normaliza o final do
arquivo. Não altera a configuração funcional do Read the Docs.

### `.viralflow-gui` — adicionado

Inclui metadados JSON que associam as ações da GUI aos comandos do CLI:
execução, atualização completa ou somente de dados do Pangolin, personalização
do banco snpEff e construção de containers. Não contém implementação da GUI.

### `README.md` — modificado

Acrescenta instruções de instalação automatizada e manual para Linux/WSL,
AMD64, ARM64, distribuições Debian/Ubuntu e RPM e macOS/Lima. Documenta
Apptainer como requisito dos scripts auxiliares, o instalador, a possibilidade
de adiar a construção dos containers e os caminhos de instalação.

Na instalação Linux padrão, o checkout fica em `~/ViralFlow`, os comandos em
`~/.local/bin` e o ambiente Micromamba em
`~/.local/share/viralflow/micromamba`. Para Lima, descreve dependências no
sistema de arquivos Linux em `/var/lib/viralflow`, com o repositório na pasta
macOS compartilhada e um launcher no host que encaminha as chamadas à VM.

### `dev.md` — modificado

Substitui o procedimento manual de instalação e compilação de Singularity
por orientações de uso do instalador da branch. Resume plataformas, caminhos
padrão e construção posterior dos containers por arquitetura. Preserva a
orientação inicial sobre seleção de arquitetura e organização dos containers.

### `docs/installation.md` — modificado

Corrige o exemplo de construção para o comando real `build-containers`, em
vez de `build_containers`. Remove também espaços ao final de uma linha da
lista de etapas de instalação. O procedimento de instalação preexistente
continua no documento.

### `docs/quickstart.md` — modificado

Corrige os nomes dos comandos e opções para a forma com hífens usada pelo CLI:
personalização snpEff, atualização Pangolin e atualização somente de dados.
O conteúdo restante do guia em inglês é preservado.

### `docs-pt/installation.md` — modificado

Corrige o comando de construção para `build-containers`. As demais instruções
de instalação em português permanecem iguais à referência.

### `docs-pt/quickstart.md` — modificado

Corrige comandos e opções de personalização snpEff e atualização Pangolin para
a forma com hífens. Preserva o restante das orientações em português.

### `docs-es/installation.md` — modificado

Corrige o comando de construção para `build-containers`. As demais instruções
de instalação em espanhol permanecem iguais à referência.

### `docs-es/quickstart.md` — modificado

Corrige comandos e opções de personalização snpEff e atualização Pangolin para
a forma com hífens. Corrige também a opção `--params-file` nos dois exemplos
de execução, que utilizavam `--params_file`.

### `envs/amd64-legado.yml` — adicionado

É uma cópia idêntica de `envs/amd64.yml` do upstream. Preserva os canais,
Nextflow 22.04.0, Java 17, spython 0.3.1 e SingularityCE 3.11.4, além das
demais dependências. Serve como definição legada; o instalador usa o arquivo
ativo `envs/amd64.yml`.

### `envs/amd64.yml` — modificado

Comenta as dependências `nextflow=22.04.0` e `singularityce=3.11.4`, retirando-as
da instalação do ambiente Conda ativo. Nextflow é instalado separadamente e
o runtime de containers é fornecido pelo host. Preserva os canais, Java 17,
spython 0.3.1 e as demais dependências do upstream.

### `envs/arm64-legado.yml` — adicionado

É uma cópia idêntica de `envs/arm64.yml` do upstream. Preserva os canais,
Nextflow 22.04.0, Java 17, click 8.3, spython e demais dependências. O instalador
usa a definição ativa `envs/arm64.yml`.

### `envs/arm64.yml` — modificado

Comenta somente a dependência `nextflow=22.04.0`, retirando Nextflow do ambiente
Conda ativo. Preserva canais, Java 17, click 8.3, spython e demais dependências.

### `envs/legado.yml` — adicionado

Inclui uma definição alternativa de ambiente com Python limitado a versões
entre 3.9 e anteriores a 3.13, Java 17, bibliotecas Python, snpEff e utilitários
de sistema. Declara Nextflow e SingularityCE como dependências externas ao
ambiente. Essa definição não é selecionada automaticamente pelo instalador.

### `fork-camilo.md` — adicionado

Documenta o estado atual da branch e as diferenças de cada arquivo em relação
a `WallauBioinfo/develop`, incluindo arquivos documentais e auxiliares. As
informações descrevem o conteúdo do código, sem histórico cronológico.

### `install.sh` — adicionado

Inclui instalador para Linux/WSL AMD64 e ARM64 e macOS/Lima. Detecta plataforma
e arquitetura; instala pacotes de sistema; instala ou reutiliza Apptainer;
configura o remote SylabsCloud, o mapeamento fakeroot e o link de `unsquashfs`.
Suporta gerenciadores APT, DNF e YUM e estratégias específicas para Debian.

Instala Micromamba 1.5.7 quando `${BIN_DIR}/micromamba` não existe e baixa o
launcher Nextflow quando `${BIN_DIR}/nextflow` não existe. Reutiliza binários
executáveis já presentes nesses caminhos sem exigir que tenham uma versão
específica. O launcher ViralFlow exporta `NXF_VER`, com padrão 22.04.0.

Clona a branch configurada ou atualiza um checkout existente por fast-forward.
Exige que o checkout existente esteja na branch esperada e evita atualizá-lo
quando há alterações locais. Cria o ambiente pelo YAML da arquitetura,
instala o wrapper em modo editável e liga `vfnext` ao ambiente instalado.
Para atualizar um ambiente existente, o código usa `micromamba env update`.

Cria launchers Linux e macOS, configura o PATH nas inicializações de shell,
verifica versões e pode construir os containers. Oferece configuração de
repositório, branch, diretórios, versão Nextflow, modo de simulação, instalação
sem containers e preservação do checkout sem atualização.

No macOS, cria ou inicia uma VM Lima ARM64, verifica a montagem gravável da
pasta pessoal do host, instala dependências em `/var/lib/viralflow` dentro da
VM e cria um launcher no host. O script verifica Apptainer, mas não cria
explicitamente o link de compatibilidade `singularity`.

### `setup.py` — modificado

Remove espaços ao final de duas linhas da descrição do pacote. Não altera
versão, dependências, entry point ou comportamento do empacotamento.
A versão declarada continua sendo 1.4.0.

### `tests/install-script.test.sh` — adicionado

Verifica sintaxe do instalador, presença de uma opção de ajuda e a chamada de
verificação do Nextflow pelo caminho do binário instalado. Executa o
instalador em modo `--dry-run` para Linux AMD64, Linux ARM64 e macOS ARM64,
com pastas pessoais temporárias. Confere caminhos, configuração do PATH e
argumentos encaminhados para Lima. Não instala dependências nem executa a
pipeline; não valida uma reinstalação real do ambiente Micromamba.

### `vfnext/bin/checkSnpEffDB.py` — adicionado

Extrai e amplia a verificação que ficava embutida no módulo Nextflow.
Consulta o catálogo, exige uma única correspondência e verifica a existência
do diretório do banco dentro do container. Procura nos locais conhecidos das
imagens AMD64 e ARM64 e grava o log de entradas também diante de erros.

Acrescenta mensagens com o contexto da execução e orientações sobre preparação
prévia do banco. A correspondência do código no catálogo continua sendo uma
busca por substring. A verificação de instalação testa a presença do diretório,
sem validar a integridade de todos os arquivos do banco.

### `vfnext/bin/compileOutput.py` — modificado

Acrescenta quatro gráficos SVG à compilação dos resultados:

- `reads_count_plot.svg`: quantidade total de leituras por amostra.
- `coverage_plot.svg`: abrangência versus profundidade média de cobertura,
  com uma linha de regressão da visualização.
- `coverage_breadth_summary_plot.svg`: distribuição por faixas de cobertura.
- `coverage_breadth_decile_plot.svg`: distribuição por intervalos de 10%.

Inclui funções auxiliares de escala, conversão para porcentagens, ordenação,
escape SVG e destaque dos controles negativos identificados pelo prefixo
`Cneg`. Os gráficos são produzidos a partir das tabelas existentes, sem nova
biblioteca gráfica. Essa é uma diferença na apresentação dos resultados,
além das adaptações de instalação e execução.

### `vfnext/configs/containers.config` — modificado

Mantém `singularity.enabled` e a montagem automática do upstream. Remove
as opções globais de escrita selecionadas por arquitetura e acrescenta
montagens de overlay somente em `runPangolin`, `runSnpEff` e `checkSnpEffDB`.

Os processos usam `pangolin_4.4.overlay` ou `snpeff_5.0.overlay` em modo
somente leitura. As imagens e os nomes de containers atribuídos aos processos
permanecem iguais ao upstream. Não habilita o backend nativo Apptainer.

### `vfnext/containers/add_entries_SnpeffDB.sh` — modificado

Passa a exigir Apptainer e trabalhar com o overlay persistente do snpEff,
em vez de alterar um sandbox diretamente. Usa execução estrita do shell,
validação de argumentos e verificações de existência das imagens e do overlay.

Detecta a instalação do snpEff dentro do container, evita duplicar a entrada
de configuração e utiliza uma pasta temporária com limpeza automática.
A preparação do banco grava seus arquivos no overlay; o catálogo local é
atualizado usando a imagem e esse mesmo overlay. Os caminhos internos são
resolvidos em tempo de execução para atender às duas arquiteturas.

### `vfnext/containers/build_containers.py` — modificado

Reestrutura o construtor com argumentos validados, comandos em listas e
exigência explícita de Apptainer. Constrói Pangolin e snpEff como SIF, em vez
dos sandboxes do upstream. Imagens ou diretórios já existentes são aceitos e
preservados; um build sem limpeza não converte automaticamente artefatos antigos.

Usa staging configurável, com padrão `/var/tmp/viralflow-apptainer`, e separa
trabalho, arquivos temporários e cache. Constrói no sistema de arquivos Linux
e copia o resultado para o repositório, atendendo a pastas compartilhadas com
macOS. Limpa temporários e área de trabalho, preservando o cache de downloads,
e remove resultados parciais quando a construção falha.

Acrescenta opções para limpeza prévia, diretório de staging e quantidade de
processos do `mksquashfs`, com padrão de um processo. Exporta variáveis de
staging Apptainer e mantém variáveis ambientais `SINGULARITY_*` compatíveis.
Cria overlays separados de 2 GiB para Pangolin e 1 GiB para snpEff.

Mantém as etapas de preparação de dataset e catálogo quando as imagens
correspondentes existem. Gera o catálogo com o overlay snpEff e preserva a
exigência de `unsquashfs` em `/usr/local/bin`. Retorna códigos de falha ao
chamador quando uma etapa não conclui.

### `vfnext/containers/build_containers_alterado.py` — adicionado

Guarda uma implementação intermediária de construção para macOS/Lima.
Usa staging em `~/.viralflow/apptainer` dentro da VM, o nome antigo da imagem
Pangolin 4.3, construção SIF e uma tentativa de overlay associado à imagem.
Inclui cópia dos artefatos para o repositório e etapas auxiliares de preparação.
Não é chamado pelo wrapper ou pela pipeline atuais.

### `vfnext/containers/build_containers_original.py` — adicionado

Guarda uma implementação auxiliar antiga, com chamadas `singularity`,
construção de sandboxes e nome Pangolin 4.3. Inclui as etapas antigas de
preparação dos containers e a verificação fixa de `unsquashfs`. Não é chamado
pelo wrapper ou pela pipeline atuais; é um arquivo histórico adicional,
não uma substituição do construtor ativo.

### `vfnext/containers/def_files/amd64/Singularity_pangolin` — modificado

Troca a base Debian 11 obtida pela biblioteca pela base Docker Debian 12 slim.
Acrescenta compiladores, cabeçalhos Python e Git, atualização do Micromamba
e `minimap2` às ferramentas do ambiente. O transporte Docker da imagem base
não implica uso do Docker Engine na execução da pipeline.

Substitui a instalação Conda do Pangolin por instalação de sua tag 4.4 via
pip/Git, acompanhada dos projetos de dados e dependências relacionados.
Restringe `setuptools` a versões anteriores a 81, instala `wheel` e desabilita
isolamento de build nessas instalações. Preserva as versões explícitas de
Python 3.11, Usher e Snakemake presentes na definição do upstream.

### `vfnext/containers/def_files/amd64/Singularity_snpEff` — modificado

Preserva imagem base e versões das ferramentas. Direciona os repositórios
APT da distribuição antiga para `archive.debian.org`, desativa a expiração
dos índices arquivados e acrescenta interrupção diante de falhas. Permite
preparar a imagem usando os repositórios arquivados.

### `vfnext/containers/def_files/arm64/Singularity_pangolin` — modificado

Preserva a base e as versões principais da definição ARM64. Acrescenta Git e
pip ao ambiente, instala `wheel`, troca a restrição `setuptools==81.0.0` por
`setuptools<81` e usa `python -m pip` com build sem isolamento nas instalações
via Git. Pangolin já era instalado pela tag 4.4 via Git no upstream ARM64;
a mudança adapta suas dependências e o processo de instalação.

### `vfnext/containers/def_files/arm64/Singularity_snpEff` — modificado

Acrescenta a preparação antecipada do banco de referência padrão na imagem
ARM64. O restante da definição permanece igual ao upstream. Essa preparação
adicional não aparece como mudança correspondente na definição AMD64.

### `vfnext/containers/spython_functions.py` — modificado

Remove o import de spython e troca o download por chamadas diretas a
`apptainer pull`, com exigência explícita desse executável. Usa subprocessos
com lista de argumentos e diretório de containers definido, propagando erros
ao chamador. O download continua usando referências `library://` e depende
do remote configurado; o instalador seleciona SylabsCloud.

Acrescenta retentativas por imagem, configuráveis por
`VIRALFLOW_CONTAINER_PULL_RETRIES` e
`VIRALFLOW_CONTAINER_PULL_RETRY_DELAY`, com padrões de três tentativas e
dez segundos. Remove arquivos SIF parciais após falhas e identifica as
tentativas no log. Acrescenta erro explícito quando faltam containers ao fim
da rotina, preservando a condição e a lista usada pelo laço externo original.

### `vfnext/modules/checkSnpEffDB.nf` — modificado

Substitui o Python embutido pela chamada ao novo `checkSnpEffDB.py`.
Encaminha código da referência, vírus, catálogo e caminhos do log. Mantém
como saída `snpEffDB_entry_found.log`. A validação passa a incluir a instalação
do banco, além de sua presença no catálogo.

### `vfnext/modules/runIvar.nf` — modificado

Substitui renomeação seguida de `sed -i` por geração dos arquivos finais com
`awk`, alterando o primeiro cabeçalho e preservando as linhas seguintes.
Remove os arquivos intermediários após a conversão. Preserva as chamadas
iVar/samtools e seus argumentos científicos; a diferença fica no tratamento
dos arquivos de saída e seus cabeçalhos.

### `wrapper/__init__.py` — modificado

Acrescenta exigência de Apptainer, helpers de subprocessos, criação de
overlays e limpeza de artefatos. Construção e manutenção passam a usar listas
de argumentos e propagação de falhas. O build usa o interpretador Python do
wrapper, encaminha opções de limpeza e staging e continua baixando as imagens
antes de construir os containers locais.

Reorganiza a leitura de parâmetros em `load_params`, preservando as chaves
aceitas. Antes de chamar Nextflow, verifica catálogo e diretório do banco
snpEff e prepara o banco no overlay quando necessário. Essa etapa só é
acionada quando o arquivo de parâmetros habilita `runSnpEff`; sem esse
parâmetro, o wrapper considera a preparação desabilitada.

As atualizações Pangolin usam um overlay gravável. A atualização completa
consulta a API GitHub para selecionar uma tag estável, com fallback para as
tags paginadas, atualiza ferramenta e dependências e verifica consistência
com `pip check`. A atualização somente de dados conserva sua operação própria.
A criação da imagem fixa a tag 4.4, enquanto a atualização completa pode
selecionar uma versão estável mais recente.

Permite definir a versão Nextflow por `NXF_VER`, mantendo 22.04.0 como padrão.
Conserva a seleção do executável pelo PATH, a montagem final do comando em
string, `os.system` e a opção `-resume`. Não implementa seleção absoluta por
`VIRALFLOW_NEXTFLOW`. O import preexistente de `distutils` permanece.

### `wrapper/cli.py` — modificado

Acrescenta `--clean` e `--staging-dir` ao comando de construção, encaminhando
as escolhas para o wrapper. Acrescenta `--arch` ao comando de execução para
orientar a preparação do banco snpEff, com padrão AMD64. Preserva os nomes dos
comandos e as demais opções do CLI do upstream.

## Arquivos e comportamentos preservados

`vfnext/main.nf`, `vfnext/nextflow.config`, `vfnext/configs/profiles.config`
e o workflow de tratamento de entradas são idênticos a `WallauBioinfo/develop`.
Os demais módulos Nextflow permanecem iguais à referência, com exceção dos
dois módulos descritos acima. Parâmetros científicos padrão, dados de teste
versionados e listas de repositórios de containers também são preservados.

Esta branch tem mudanças no ambiente, na preparação e validação de recursos
locais e na apresentação dos resultados. Portanto, seu conjunto de diferenças
é maior que uma adaptação exclusiva do comando de containers ou do sistema
operacional. A descrição dos módulos alterados e dos gráficos faz parte da
comparação completa, mesmo que não sejam mudanças de algoritmos de análise.

## Particularidades do estado atual

Os scripts auxiliares exigem `apptainer`, enquanto Nextflow continua usando
`singularity`. Para executar Nextflow com Apptainer, o comando de compatibilidade
`singularity` precisa estar disponível no host. O instalador desta branch não
cria esse link explicitamente; sua presença pode vir do pacote do runtime.

O instalador baixa Micromamba 1.5.7, mas usa `env update` para ambientes
existentes. Esse subcomando não está disponível no Micromamba 1.5.7, conforme
os testes isolados anteriores das versões antigas. O teste `--dry-run` desta
branch não cobre essa operação real. A documentação registra essa diferença
sem alterar o instalador.

Os ambientes ativos ainda declaram spython, embora o helper de download tenha
removido seu import. O helper também preserva a condição original com `or`
no laço externo de verificação; as retentativas acrescentadas são internas a
cada download. O comando Nextflow ainda depende do PATH e seu retorno não é
propagado pelo wrapper como nas operações que usam `check_call`.

Os arquivos `*-legado.yml`, `build_containers_original.py` e
`build_containers_alterado.py` são referências adicionais. Não são escolhidos
pelo fluxo normal do instalador ou pelo wrapper. Sua presença está incluída
na contagem dos arquivos diferentes.

## Conferência do documento

Esta revisão compara o conteúdo atual dos arquivos diretamente com a referência
Git, incluindo alterações locais do diretório de trabalho. Foram conferidos
os 36 arquivos diferentes, as duas cópias legadas idênticas aos YAMLs do
upstream e a preservação do fluxo/configurações principais. Somente este
documento foi reescrito; não foram modificados fontes, ambientes ou containers.

A revisão documental não executa instalação, construção ou pipeline, nem
constitui nova validação de Linux, WSL, ARM64 ou macOS. O teste existente do
instalador cobre sintaxe e simulação, conforme descrito em sua seção.

Para reproduzir a comparação:

```bash
git diff --name-status WallauBioinfo/develop --
git diff --stat WallauBioinfo/develop --
git diff WallauBioinfo/develop --
```
