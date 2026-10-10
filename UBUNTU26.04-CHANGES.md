# Migração do ambiente de execução para Ubuntu 26.04

Data: 09/10/2026. Branch: `feat/develop/ubuntu26.04`.
Base local: `7575673` (já continha os gráficos de `compileOutput.py`).
As diferenças desse commit em relação a `WallauBioinfo/develop` são anteriores
a esta migração e não foram modificadas.

## Escopo

Instalação e execução diretamente no host com Apptainer. As imagens mantêm
seus nomes e versões; pangolin e snpEff continuam em sandbox. Não foram
alterados `vfnext/main.nf`, módulos, workflows, scripts de análise, parâmetros
científicos padrão. A adaptação posterior da GUI está registrada separadamente
em [ViralFlowGui/UBUNTU26.04-COMPATIBILITY.md](../ViralFlowGui/UBUNTU26.04-COMPATIBILITY.md).
As branches Docker foram preservadas.
O instalador foi trazido da `develop-SIF3-MAC`, sem importar seus overlays,
alterações científicas ou mecanismos específicos de macOS e outras distribuições.

## Registro por arquivo

Este arquivo também foi atualizado para referenciar a verificação de
compatibilidade da GUI, desenvolvida na branch `v0.53` (versão `0.53.0`)
do repositório ViralFlowGui e compatível com esta branch do ViralFlow.
Nessa etapa, somente este documento foi
alterado no repositório ViralFlow; não foi acrescentada opção de limpeza
ao CLI. O registro da GUI descreve individualmente seus arquivos alterados
e inseridos.

| Arquivo | Operação | Alteração e motivo |
| --- | --- | --- |
| `install.sh` | Inserido, executável | Instalador derivado de `develop-SIF3-MAC`, limitado à instalação Ubuntu/Linux. Seleciona esta branch e Nextflow 23.10.1; utiliza Micromamba 2.9.0 em novas instalações. Reutiliza Apptainer existente e instala pelo PPA quando necessário. Inclui `--skip-system-packages` e `--no-path-update`, preserva checkout com alterações locais, normaliza caminhos relativos, corrige expansão de `~/`, identifica o ambiente pela raiz selecionada e verifica o runtime antes de construir containers. Baixa o launcher oficial compacto da versão selecionada e mantém seu cache na raiz da instalação; resolução Maven é verificada antes de construir containers. |
| `envs/amd64.yml` | Alterado | Remove SingularityCE, spython e Nextflow 22.04.0. Apptainer é fornecido pelo host e Nextflow pelo instalador. Remove canais antigos/duplicados e canais desnecessários, mantendo bioconda e conda-forge para reduzir resolução e cache de metadados. Preserva as demais dependências e Java 17. |
| `envs/arm64.yml` | Alterado | Remove spython e Nextflow 22.04.0; preserva as demais dependências. Nextflow é instalado separadamente. ARM64 não foi executado neste host AMD64. |
| `wrapper/__init__.py` | Alterado | Remove imports sem uso de `distutils` e `logging`; `distutils` não existe no Python moderno. Troca manutenção pangolin para Apptainer, mantendo `--writable` e sandbox. Usa argumentos separados e propaga falhas nas duas atualizações pangolin e na inclusão snpEff, preservando nomes/caminhos com espaços. Restringe temporariamente o setuptools de build a `<81` para os instaladores legados, sem modificar pacotes upstream. Na atualização completa, alinha dependências aos requisitos Python das versões instaladas de pangolin/Snakemake e exige `pip check`; a atualização somente dos dados não faz essa instalação de dependências das ferramentas. Usa o interpretador Python ativo e diretório explícito para baixar/construir containers; interrompe a instalação se alguma etapa falhar. Seleciona Nextflow 23.10.1 por padrão, permite `NXF_VER` e propaga falha da pipeline ao chamador, inclusive à GUI. O parser de parâmetros é preservado. |
| `vfnext/nextflow.config` | Alterado | Declara Nextflow >=23.10.1 como versão mínima validada nesta migração para o backend Apptainer. |
| `vfnext/configs/containers.config` | Alterado | Troca o backend Singularity por Apptainer. Remove `--writable` global, incompatível com as imagens SIF. Restringe a escrita temporária a `runSnpEff` com `--writable-tmpfs`; os sandboxes permanecem em diretórios e sua manutenção persistente continua usando `--writable`. Nomes e versões de imagens são preservados. |
| `vfnext/configs/profiles.config` | Alterado | Migra os dois perfis Fiocruz para Apptainer e remove o caminho Singularity sem uso. Preserva executores, recursos, filas e binds. Configuração PBS foi inspecionada, sem execução em cluster. |
| `vfnext/containers/spython_functions.py` | Alterado | Remove import spython não utilizado. Usa `apptainer pull` com a biblioteca Sylabs explícita, diretório de destino e verificação do código de saída. Corrige a condição do laço para que downloads ausentes não causem repetição infinita. Mantém o nome do arquivo para evitar alterar seus importadores. |
| `vfnext/containers/build_containers.py` | Alterado | Troca construção/execução por Apptainer, preservando `--fakeroot --sandbox` para pangolin e snpEff. Verifica `unsquashfs` pelo `PATH`, sem exigir link em `/usr/local/bin`. Retorna falha se construção ou etapas auxiliares falharem, permitindo ao instalador detectar instalação incompleta. |
| `vfnext/containers/add_entries_SnpeffDB.sh` | Alterado | Substitui Singularity por Apptainer. Preserva fakeroot, sandbox gravável e `snpEff build -genbank`. Adiciona interrupção em falhas, argumentos/caminhos entre aspas e download temporário em formato `gbwithparts`, necessário para registros de montagem que omitem a sequência em `gb`. Exige sequência antes de alterar o banco, evita duplicar a entrada na configuração, verifica o arquivo binário produzido e publica o catálogo somente após sucesso. Usa `printf` para preservar nomes literalmente. |
| `vfnext/containers/def_files/amd64/Singularity_pangolin` | Alterado | Adota `Bootstrap: docker` e `debian:12-slim`, como na `develop-SIF3-MAC`, após falha real de pacotes na base Debian 11. Este bootstrap usa o Apptainer, sem Docker Engine. Preserva a chamada de instalação Conda e as versões pangolin 4.4, UShER 0.6.2 e Snakemake 9.19.0. Adiciona `set -e`, alinhamento posterior das dependências aos requisitos declarados pelos pacotes Python instalados e `pip check`: os metadados Bioconda atualmente divergem desses requisitos. |
| `vfnext/containers/def_files/amd64/Singularity_snpEff` | Alterado | Traz a correção dos repositórios Debian Buster para `archive.debian.org` da `develop-SIF3-MAC` e adiciona `set -e`. Ajusta somente a validade temporal do arquivo APT dentro do container arquivado; não altera configurações do host. Preserva base, dependências e snpEff 5.0. |
| `README.md` | Alterado | Acrescenta links para instalação Ubuntu 26.04 e este registro. |
| `docs/installation.md` | Alterado | Acrescenta instalação Ubuntu 26.04 com Apptainer, opções do instalador, versões do runtime, distinção entre sandbox/SIF e limites da validação. Identifica as instruções manuais anteriores como históricas. |
| `docs-pt/installation.md` | Alterado | Documenta a mesma instalação e opções em português. |
| `docs-es/installation.md` | Alterado | Documenta a mesma instalação e opções em espanhol. |
| `tests/install-script.test.sh` | Inserido, executável | Valida simulação AMD64/ARM64 sem mutações, instalação/reinstalação com comandos simulados, caminhos com espaços, ausência de sudo/downloads nas opções de reutilização e rejeição de opção inválida. Adaptado do teste do instalador da branch de referência. |
| `tests/test_runtime.py` | Inserido | Nove testes para falhas de download/pipeline/manutenção, biblioteca Sylabs explícita e término do laço de downloads. Cobrem argumentos com espaços, limpeza das restrições temporárias de build, separação da atualização somente de dados e propagação de falhas da instalação/verificação de dependências. Simulam download snpEff vazio, construção com erro e ausência do binário final; nesses casos o catálogo anterior permanece intacto. Não executam análises biológicas. |
| `tests/host-smoke.sh` | Inserido, executável | Gera uma referência aleatória não biológica e leituras sintéticas pareadas/simples. Executa a pipeline sem alterações em modo `custom`, com os limiares científicos padrão, e verifica consensos e diretório de resultados compilados. |
| `UBUNTU26.04-CHANGES.md` | Inserido | Este registro por arquivo, decisões, comandos de reprodução, evidências e limites. |

Nenhum arquivo de código versionado foi removido ou renomeado.

## Problemas observados e soluções

- O launcher Nextflow compacto inicialmente falhou ao resolver dependências
  Maven. O usuário informou que havia um mirror corporativo em `settings.xml`
  e renomeou esse arquivo. Após essa mudança, o launcher oficial compacto
  23.10.1 iniciou com sucesso usando um cache Nextflow novo. O instalador
  passou a usar esse launcher, retirando a exigência da distribuição `all`.
- Uma instalação Apptainer não deve depender de um remote Sylabs previamente
  configurado. As chamadas de download usam `--library https://library.sylabs.io`,
  sem modificar o remote padrão do usuário.
- A receita pangolin Debian 11 falhou com HTTP 404 em pacotes APT. A base Debian
  12 da branch de referência resolveu a construção sem importar outras mudanças.
- A atualização real de constellations falhou na construção do pacote: seu
  instalador usa `pkg_resources`, ausente no setuptools atual. As duas rotinas
  pangolin fornecem `setuptools<81` via `PIP_BUILD_CONSTRAINT`, em arquivo
  temporário montado em `/tmp`; a restrição afeta o build, não as dependências
  científicas instaladas. O pip 26.2.1 do sandbox reconhece essa opção.
- `pip check` revelou conflitos pré-existentes no sandbox pangolin: pandas
  3.0.6, scikit-learn 1.2.2 e packaging 26.3 não atendiam aos requisitos Python
  de pangolin 4.4/Snakemake 9.19.0. O alinhamento pelos requisitos dos pacotes
  instalados resultou em pandas 2.3.3, scikit-learn 1.7.1 e packaging 25.0;
  também foi selecionado snakemake-interface-common 1.23.0 pelo resolver.
  Aplicado na construção e na atualização completa, preservando as versões
  das ferramentas. A tentativa de impor os requisitos diretamente no Conda
  falhou porque seu pangolin 4.4 exige scikit-learn `<1.3`, enquanto os
  metadados Python instalados exigem `==1.7.1`.
- O teste snpEff com cromossomo I de *Saccharomyces cerevisiae* (`NC_001133.9`)
  recebeu um registro `CONTIG` sem sequência com `-format gb`. `gbwithparts`
  resolveu o download completo. O script e o wrapper antes ocultavam a falha
  da construção; agora interrompem e retornam erro, preservando o catálogo.
  As correções de argumentos e interrupção em falhas foram comparadas com a
  `develop-SIF3-MAC`, sem importar seus overlays.
- A receita snpEff apontava para repositórios Buster removidos dos espelhos.
  A correção para o arquivo Debian resolveu a instalação de `procps`.
- Os wrappers anteriores podiam retornar sucesso após uma falha de execução.
  Agora o erro interrompe a instalação e chega ao processo que chamou ViralFlow.

## Validação no host

Host: Ubuntu 26.04.1 LTS, AMD64. Apptainer 1.5.3 já instalado.
Ambiente novo e isolado em `.venv/ubuntu26.04`, ignorado pelo Git:
Micromamba 2.9.0, Python 3.14, Java 17, Nextflow 23.10.1, ViralFlow 1.4.0.
Os ambientes internos das imagens permanecem independentes desse Java/Python.

| Verificação | Resultado |
| --- | --- |
| Launcher compacto com cache novo após renomeação do settings.xml | Sucesso; Nextflow 23.10.1 inicializado sem a distribuição `all`. |
| Instalação inicial do ambiente e reinstalação | Sucesso; wrapper e Nextflow executáveis; ambiente existente atualizado. |
| Construção dos sandboxes AMD64 | Sucesso; pangolin 4.4 e snpEff 5.0e executam comandos de versão. |
| Download das 11 imagens originais SIF | Sucesso usando Apptainer e biblioteca Sylabs explícita. |
| Instalador completo com containers existentes | Sucesso; dataset auxiliar Nextclade e catálogo snpEff gerados pela rotina existente. |
| Pipeline com entrada sintética pareada e simples | 27 tarefas concluídas, zero falhas; duração Nextflow 1m16s; consensos e resultados compilados produzidos. |
| Retomada da mesma execução | 27 tarefas recuperadas do cache, zero falhas; duração Nextflow 2,7s. |
| Reinstalação e retomada com launcher compacto | Instalador concluído; 27 tarefas recuperadas do cache, zero falhas; duração Nextflow 2,3s. |
| Sandboxes lançados pelo Nextflow com configuração real | Três tarefas de comandos de versão concluídas: pangolin, Python do snpEff e snpEff. `--writable-tmpfs` aparece somente na tarefa `runSnpEff`. |
| Escrita temporária no snpEff | Sucesso; arquivo de sondagem não persistiu no sandbox. |
| Manutenção gravável pangolin | `apptainer exec --writable ... pangolin --version` executado com sucesso, sem atualizar pacotes/dados. |
| Entrada inválida pelo comando ViralFlow | Código de saída 1 propagado ao chamador; nenhuma tarefa científica iniciada. |
| Testes do instalador e testes Python | Sucesso; nove testes Python e teste shell. |
| Configuração padrão e PBS | Carregam com `apptainer.enabled = true`; configuração PBS não submetida a cluster. |
| Revisão do diff | Nenhuma diferença em módulos, workflows, `main.nf` ou scripts científicos em relação à base local. |

Os testes não comprovam desempenho científico, classificação de linhagens ou
anotação de amostras reais. A pipeline sintética utiliza `runSnpEff false` e modo
`custom`; os sandboxes foram testados separadamente quanto ao ambiente e ao
lançamento pelo Nextflow. ARM64, instalação do PPA em uma máquina sem Apptainer,
cluster PBS e interface gráfica não foram executados nesta validação.

### Manutenção pangolin e banco personalizado snpEff

As operações foram exercitadas pelo CLI real, redirecionando somente sua raiz
de instalação para cópias dos sandboxes. Versões antigas dos dados e do scorpio
foram instaladas nessas cópias para testar downloads e gravações reais.

| Operação | Resultado |
| --- | --- |
| Atualização somente dos dados | pangolin-data 1.40 → 1.41 e constellations 0.1.10 → 0.1.12; código de saída 0. Pangolin 4.4 e scorpio 0.3.19 preservados. |
| Inventário antes/depois da atualização de dados | Somente os dois pacotes de dados mudaram de versão; demais pacotes preservados. `pip check` sem conflitos antes e depois. |
| Atualização de ferramentas e dados | pangolin-data 1.40 → 1.41, constellations 0.1.10 → 0.1.12 e scorpio 0.3.17 → 0.3.19; código de saída 0. Pangolin já estava na versão estável mais recente, 4.4. |
| Alinhamento e verificação de dependências | Atualização completa executada na cópia e no sandbox instalado; `pip check` sem conflitos em ambos. |
| Reconstrução pangolin com a receita corrigida | Sucesso; sandbox novo com pangolin 4.4, dados 1.41, constellations 0.1.12 e scorpio 0.3.19; `pip check` sem conflitos. |
| Inclusão snpEff em caminho/nome com espaços | Banco `NC_001133.9` construído; binário não vazio; catálogo indica `OK` e nome `Saccharomyces cerevisiae`. |
| Repetição da inclusão snpEff | Sucesso; uma única entrada `.genome` na configuração. |
| Carregamento do banco personalizado | snpEff com `-noDownload` anotou um VCF de teste de levedura e produziu `ANN`; banco carregado do sandbox com `--writable-tmpfs`. |
| Pipeline completa após os ajustes de manutenção | Launcher compacto; diretório novo e entradas aleatórias não biológicas; 27 tarefas executadas com sucesso, zero falhas, duração 1m14s. |

Uma tentativa exploratória de usar pangolin 4.3.1 como versão antiga de teste
encontrou incompatibilidade com setuptools e Snakemake 9.19.0. Essa preparação
foi descartada: o teste final usa pangolin 4.4 da receita desta branch e scorpio
anterior. Não se afirma compatibilidade com ambientes de versões principais
antigas; a documentação upstream exige ajuste do ambiente nessas migrações.
Nenhuma classificação de linhagem ou análise de amostra patogênica foi feita.

## Reprodução

```bash
bash install.sh --repo-dir "$PWD" --no-update --skip-system-packages \
  --no-path-update --install-root "$PWD/.venv/ubuntu26.04" \
  --bin-dir "$PWD/.venv/ubuntu26.04/bin"

bash tests/install-script.test.sh
python3 -m unittest discover -s tests -p 'test_runtime.py' -v

VIRALFLOW_COMMAND="$PWD/.venv/ubuntu26.04/bin/viralflow" \
  bash tests/host-smoke.sh /tmp/viralflow-host-validation-nova
```

O teste de host exige um diretório novo para preservar as evidências de
execuções anteriores. O instalador exige mapeamentos fakeroot já configurados
quando `--skip-system-packages` é utilizado para construir sandboxes.

Comandos de manutenção, usando a instalação selecionada acima:

```bash
.venv/ubuntu26.04/bin/viralflow update-pangolin-data
.venv/ubuntu26.04/bin/viralflow update-pangolin
.venv/ubuntu26.04/bin/viralflow add-entry-to-snpeff \
  --org-name 'Saccharomyces cerevisiae' --genome-code NC_001133.9 --arch amd64
```

Esses comandos operam no sandbox instalado. Nesta validação, a inclusão de
levedura foi feita somente na cópia de teste; a atualização completa também
foi aplicada ao sandbox pangolin instalado para corrigir suas dependências.

## Artefatos locais de instalação e execução

Estes artefatos são ignorados pelo Git e não integram o código da migração:

- `.venv/ubuntu26.04/bin/`: comandos `micromamba`, `nextflow` e `viralflow`.
- `.venv/ubuntu26.04/micromamba/`, `nextflow/` e `apptainer-cache/`: dependências
  e caches da instalação isolada.
- `vfnext/containers/*.sif`: 11 arquivos SIF e os dois diretórios sandbox.
- `vfnext/containers/snpEff_DB.catalog` e
  `vfnext/containers/nextclade_dataset/sars-cov-2/`: artefatos auxiliares da
  rotina de instalação original.
- `.venv/ubuntu26.04/validation/installation-logs/`: logs de instalação,
  download e construção copiados do diretório temporário de trabalho.
- `.venv/ubuntu26.04/validation/synthetic/`: referência, GFF, FASTQ e parâmetros
  sintéticos; `pipeline.log`, `resume.log`, `resume-compact.log`, logs Nextflow,
  cache, work e output.
- `.venv/ubuntu26.04/validation/sandbox-runtime/`: workflow de comandos de versão,
  link para containers, log, trace e work de três tarefas.
- `.venv/ubuntu26.04/validation/maven-default/`: launcher compacto, cache novo
  e log da inicialização após a renomeação do `settings.xml`.
- `.venv/ubuntu26.04/validation/maintenance/`: cópias dos sandboxes, scripts
  locais que redirecionam a raiz do CLI e logs das tentativas e dos testes
  finais. `data-consistent-final.log`, `data-package-changes.json` e
  `data-packages-before.json`/`data-packages-final.json` comprovam a atualização
  somente dos dados. `tool-final.log` e `tool-dependencies-corrected.log`
  registram atualização das ferramentas/dados e alinhamento de dependências;
  `original-dependencies-corrected.log` registra a correção no sandbox instalado.
  `*-pip-check-final.log` e `*-verified.txt` registram as verificações finais.
  `pangolin-rebuild-corrected.log` e `pangolin-rebuilt-corrected.sif/` são a
  reconstrução validada. `snpeff-spaces.log`, `snpeff-repeat.log` e
  `snpeff with spaces/annotated.vcf` comprovam inclusão, repetição e carregamento
  do banco de levedura. `unit-tests.log` registra os nove testes Python.
- `.venv/ubuntu26.04/validation/synthetic-after-maintenance/`: execução completa
  com launcher compacto após os ajustes; `pipeline.log`, `.nextflow.log` e
  outputs registram 27 tarefas executadas, nenhuma recuperada do cache.
- `.venv/ubuntu26.04/validation/nextflow-*.config`: configuração resolvida para
  conferência dos backends padrão/PBS.
- `.venv/ubuntu26.04/validation/failure/`: parâmetros deliberadamente inválidos
  e log da verificação de código de saída. Consultas de configuração e esta
  verificação também registraram logs/cache Nextflow no diretório do checkout.

Não foram modificados pacotes do sistema, arquivos de inicialização do shell,
configuração global do Apptainer ou restrições AppArmor do host. Alterações
de código permanecem no checkout para revisão, sem publicação remota.

## Referências de compatibilidade

- [Backend Apptainer no Nextflow](https://docs.seqera.io/nextflow/reference/config/apptainer).
- [Distribuição oficial Nextflow 23.10.1](https://github.com/nextflow-io/nextflow/releases/tag/v23.10.1).
- [Remotes e bibliotecas Apptainer](https://apptainer.org/docs/user/latest/endpoint.html).
- [Instalação Micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html).
- [Atualização pangolin](https://cov-lineages.org/resources/pangolin/updating.html).
- [Restrições de build no pip](https://pip.pypa.io/en/stable/user_guide/#build-constraints).
- [NCBI EFetch e GenBank com sequência completa](https://www.ncbi.nlm.nih.gov/sites/books/NBK1058/).
