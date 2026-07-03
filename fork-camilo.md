# Alterações do fork Camilo em relação ao ViralFlow upstream

## Escopo da comparação

Este documento resume as diferenças de código entre:

- base: `WallauBioinfo/develop` (`16cb3f3`);
- fork analisado: `origin/develop-SIF3-MAC` (`cc2a62d`).

A comparação foi feita a partir do ancestral comum dos branches. No momento da
análise, o fork continha 65 commits adicionais e não havia commits do upstream
pendentes de incorporação.

Arquivos exclusivamente documentais não foram analisados. O `README.md` e o
novo `install.sh` são citados apenas para registrar sua existência, sem
detalhamento de conteúdo.

## Resumo geral

As alterações do fork estão concentradas nos seguintes pontos:

1. **Compatibilidade com Linux, macOS/Lima e arquiteturas amd64/arm64**
   - Separação entre dependências Python/Conda e ferramentas instaladas
     externamente, especialmente Nextflow.
   - Apptainer passou a ser requisito obrigatório para construção, download,
     atualização e execução dos contêineres. Singularity não é mais considerado
     runtime suficiente para este fork.
   - Construção dos contêineres em uma área temporária localizada no sistema de
     arquivos Linux, evitando limitações de diretórios compartilhados pelo
     macOS.
   - Uso configurável de diretórios de staging, cache e trabalho, com
     `/var/tmp/viralflow-apptainer` como padrão.

2. **Reestruturação da construção e manutenção dos contêineres**
   - Migração da lógica de construção para comandos estruturados de Apptainer.
   - Remoção do fallback operacional para Singularity nos fluxos de wrapper,
     pull, build e personalização de bancos.
   - Download de contêineres com retentativas configuráveis e remoção de SIFs
     parciais após falhas.
   - Geração de imagens SIF em vez de sandboxes graváveis.
   - Criação de overlays persistentes separados para Pangolin e snpEff.
   - Opções para limpeza dos artefatos e controle da quantidade de processos do
     `mksquashfs`.

3. **Atualização do Pangolin**
   - O contêiner passou a instalar componentes do Pangolin a partir dos
     respectivos repositórios Git.
   - O comando de atualização identifica dinamicamente a versão estável mais
     recente do Pangolin e atualiza suas dependências dentro de um overlay.
   - Foi adicionada uma verificação de consistência das dependências Python após
     a atualização.

4. **Persistência e validação do banco do snpEff**
   - Bancos personalizados são gravados em um overlay próprio, sem modificar a
     imagem SIF.
   - A pipeline verifica se o código solicitado existe no catálogo e se o banco
     correspondente está efetivamente instalado.
   - Mensagens de erro foram ampliadas para orientar o usuário quando o banco
     não está pronto.

5. **Novos gráficos de controle de qualidade**
   - A compilação dos resultados passou a gerar gráficos SVG de quantidade de
     reads, relação entre amplitude e profundidade de cobertura e distribuição
     das amostras por faixas de cobertura.
   - Controles negativos identificados pelo prefixo `Cneg` recebem destaque
     visual.

6. **Ajustes de robustez e integração**
   - Comandos críticos passaram a usar listas de argumentos e
     `subprocess.check_call` em alguns pontos, reduzindo problemas de quoting.
   - Foi incluído um arquivo de metadados para integração com a interface
     gráfica do ViralFlow.
   - O processo do iVar deixou de depender de `sed -i` para alterar cabeçalhos
     FASTA.

## Alterações detalhadas por arquivo

### Ambientes e empacotamento

#### `envs/amd64.yml`

- Nextflow e SingularityCE foram removidos do ambiente Conda ativo.
- As demais dependências usadas pelo wrapper e pela pipeline foram mantidas.
- A intenção é instalar Nextflow separadamente e exigir Apptainer como runtime
  de contêineres, evitando conflitos de bibliotecas no ambiente Conda.

#### `envs/arm64.yml`

- Nextflow também foi removido do ambiente Conda ativo.
- O ambiente continua contendo as bibliotecas Python e ferramentas auxiliares
  necessárias para arm64.

#### `envs/amd64-legado.yml`

- Preserva a definição anterior do ambiente amd64, incluindo Nextflow 22.04.0 e
  SingularityCE 3.11.4.
- Funciona como referência ou alternativa para a instalação legada.

#### `envs/arm64-legado.yml`

- Preserva a definição anterior do ambiente arm64, incluindo Nextflow 22.04.0.
- Funciona como referência ou alternativa para a instalação legada.

#### `envs/legado.yml`

- Adiciona uma definição legada genérica com Python, Java, bibliotecas Python,
  snpEff e utilitários de linha de comando.
- Registra explicitamente que Nextflow e SingularityCE devem ser instalados fora
  do ambiente.

#### `setup.py`

- Contém apenas um ajuste de formatação na descrição do pacote.
- Não há mudança funcional no empacotamento.

### Configuração e módulos da pipeline

#### `vfnext/configs/containers.config`

- Remove as opções globais `--writable` e `--writable-tmpfs`.
- Configura overlays somente nos processos que precisam de escrita persistente:
  `runPangolin`, `runSnpEff` e `checkSnpEffDB`.
- Os overlays são montados como somente leitura durante a execução normal da
  pipeline:
  - `pangolin_4.4.overlay`;
  - `snpeff_5.0.overlay`.
- Isso evita o conflito entre `--writable-tmpfs` e overlays e reduz o escopo de
  permissões de escrita nos demais contêineres.

#### `vfnext/modules/checkSnpEffDB.nf`

- Substitui o código Python embutido no módulo pelo script independente
  `vfnext/bin/checkSnpEffDB.py`.
- Passa ao script o código da referência, o vírus configurado, o catálogo e os
  caminhos dos arquivos de saída.
- Mantém como produto do processo o arquivo `snpEffDB_entry_found.log`.

#### `vfnext/modules/runIvar.nf`

- Substitui a sequência `mv` e `sed -i` por `awk`, gerando diretamente os FASTA
  finais com o cabeçalho esperado.
- Remove explicitamente os arquivos intermediários após a conversão.
- O comportamento funcional da geração de consensos permanece o mesmo, mas a
  implementação fica menos dependente das diferenças entre versões de `sed`.

### Scripts de processamento e resultados

#### `vfnext/bin/checkSnpEffDB.py`

Novo script responsável por validar o banco do snpEff antes da anotação:

- procura o código de referência no catálogo;
- rejeita ausência ou múltiplas correspondências;
- procura a instalação do banco nos caminhos conhecidos das imagens amd64 e
  arm64;
- impede que a execução dependa de download automático do banco;
- grava o log de correspondências também nos casos de erro;
- apresenta mensagens com contexto e indicação de preparação prévia do banco.

#### `vfnext/bin/compileOutput.py`

Adiciona geração direta de gráficos SVG, sem introduzir uma biblioteca gráfica
externa:

- `reads_count_plot.svg`: barras com a quantidade total de reads por amostra;
- `coverage_plot.svg`: relação entre amplitude e profundidade média da
  cobertura, incluindo uma regressão linear simples;
- `coverage_breadth_summary_plot.svg`: quantidade de amostras nas faixas
  0–30%, acima de 30% e abaixo de 70%, e 70–100%;
- `coverage_breadth_decile_plot.svg`: distribuição em intervalos de 10%.

Também foram adicionados:

- conversão de valores de cobertura para porcentagem quando necessário;
- cálculo de limites de eixo arredondados;
- ordenação estável das amostras no gráfico de reads;
- rótulos inclinados para suportar maior quantidade de amostras;
- destaque azul e legenda para controles negativos `Cneg`;
- validação das colunas necessárias e avisos quando não há dados utilizáveis.

Os gráficos são gerados automaticamente junto com `reads_count.csv` e
`short_summary.csv`.

### Construção e manutenção dos contêineres

#### `vfnext/containers/build_containers.py`

O script foi amplamente reestruturado:

- usa `argparse` e valida a arquitetura (`amd64` ou `arm64`);
- aceita `--clean`, `--staging-dir` e `--mksquashfs-processors`;
- usa um diretório de staging configurável, por padrão em
  `/var/tmp/viralflow-apptainer`;
- separa diretórios temporários, cache e workdir;
- limpa `tmpdir` e `workdir` antes de cada construção, preservando o cache;
- direciona as variáveis de ambiente de Apptainer para o staging;
- mantém variáveis `SINGULARITY_*` apenas como compatibilidade ambiental
  herdada, mas o executável exigido pelo script é `apptainer`;
- constrói os SIFs no sistema de arquivos Linux e depois os copia para o
  repositório, o que atende ao uso do repositório em um volume macOS montado no
  Lima;
- limita por padrão o `mksquashfs` a um processo;
- remove artefatos parciais após falhas;
- cria overlays separados:
  - 2 GiB para Pangolin;
  - 1 GiB para snpEff;
- permite remover imagens, overlays e catálogo antes da reconstrução;
- carrega o dataset do Nextclade quando a imagem correspondente está presente;
- gera o catálogo do snpEff usando seu overlay;
- verifica a disponibilidade de `unsquashfs`;
- retorna códigos de erro em falhas, em vez de apenas imprimir o resultado.

O script verifica explicitamente a presença do executável `apptainer` antes da
construção. Singularity não satisfaz mais esse fluxo.

#### `vfnext/containers/build_containers_original.py`

- Cópia auxiliar da implementação antiga do construtor de contêineres.
- Não é chamada pelo wrapper nem pela pipeline.
- Deve ser avaliada para remoção antes de uma integração, pois representa código
  histórico duplicado.

#### `vfnext/containers/build_containers_alterado.py`

- Registra uma versão intermediária das adaptações para macOS/Lima.
- Usa staging dentro da `HOME` da VM e ainda contém decisões anteriores sobre
  imagens e overlays.
- Não é chamada pelo wrapper nem pela pipeline.
- Deve ser tratada como arquivo de desenvolvimento e avaliada para remoção.

#### `vfnext/containers/add_entries_SnpeffDB.sh`

- Ativa execução estrita do shell com `set -euo pipefail`.
- Exige o executável `apptainer`; Singularity não é mais aceito como fallback.
- valida argumentos, imagens e overlay antes de iniciar;
- detecta o diretório interno do snpEff executando comandos no contêiner, em vez
  de acessar a imagem como diretório;
- grava configuração, dados e banco no overlay persistente;
- evita duplicar a entrada no `snpEff.config`;
- usa diretório temporário com limpeza automática;
- baixa o registro de referência pelo contêiner do EDirect;
- reconstrói o banco e atualiza o catálogo após a inclusão.

#### `vfnext/containers/spython_functions.py`

- Remove a dependência direta da biblioteca `spython` para o pull de imagens.
- Passa a exigir o executável `apptainer`.
- Substitui `singularity pull` por `apptainer pull -F`.
- Adiciona retentativas configuráveis para download de contêineres:
  - `VIRALFLOW_CONTAINER_PULL_RETRIES`, com padrão `3`;
  - `VIRALFLOW_CONTAINER_PULL_RETRY_DELAY`, com padrão de 10 segundos.
- Remove arquivos SIF parciais antes de tentar novamente após uma falha de
  download.
- Mostra no log a tentativa atual e o total de tentativas configurado.
- Usa `subprocess.check_call` com lista de argumentos, evitando montagem de
  comandos por string.
- Passa a reportar falha quando algum contêiner obrigatório não é baixado após
  as tentativas previstas.

#### `vfnext/containers/def_files/amd64/Singularity_pangolin`

- Adiciona compiladores, cabeçalhos Python e Git.
- Atualiza o Micromamba antes da instalação.
- Instala as ferramentas base pelo ambiente Micromamba.
- Instala Pangolin 4.4 e seus projetos relacionados a partir dos repositórios
  Git.
- Fixa `setuptools` abaixo da versão 81 e usa `--no-build-isolation` para
  compatibilidade com o processo atual de build.

#### `vfnext/containers/def_files/arm64/Singularity_pangolin`

- Alinha a instalação arm64 à estratégia usada em amd64.
- Garante a presença de Git e pip no ambiente.
- Instala Pangolin e projetos relacionados via pip/Git com
  `--no-build-isolation`.
- Substitui a instalação de `setuptools==81.0.0` por `setuptools<81`.

#### `vfnext/containers/def_files/amd64/Singularity_snpEff`

- Atualiza as fontes APT do Debian Buster para `archive.debian.org`.
- Desativa a validação de expiração dos metadados antigos.
- Permite que a imagem continue sendo construída após a retirada dos
  repositórios Buster dos servidores Debian regulares.

#### `vfnext/containers/def_files/arm64/Singularity_snpEff`

- Inclui no build da imagem o download do banco `NC_045512.2`.
- Garante que esse banco esteja disponível sem download durante a execução da
  pipeline.

### Wrapper e comandos

#### `wrapper/__init__.py`

As principais alterações são:

- exigência explícita de `apptainer`; Singularity não é mais runtime aceito pelo
  wrapper;
- funções auxiliares para executar comandos, criar overlays e remover artefatos;
- execução do script de personalização do snpEff com argumentos estruturados;
- limpeza de imagens, overlays e catálogo por arquitetura;
- suporte às opções de limpeza e staging na construção dos contêineres;
- atualização do Pangolin dentro de overlay persistente;
- identificação da versão estável mais recente do Pangolin por meio da API do
  GitHub;
- fallback da release mais recente para paginação das tags;
- aceitação apenas de tags estáveis no formato `vX.Y` ou `vX.Y.Z`;
- atualização ordenada das dependências do Pangolin;
- execução de `pip check` após a atualização;
- atualização separada dos dados do Pangolin no mesmo overlay;
- possibilidade de sobrescrever a versão do Nextflow pela variável `NXF_VER`,
  mantendo `22.04.0` como padrão.

#### `wrapper/cli.py`

- O comando `viralflow build-containers` recebe duas novas opções:
  - `--clean`, para remover artefatos antes da reconstrução;
  - `--staging-dir`, para escolher o local usado pelo Apptainer.
- As opções são encaminhadas para a implementação no wrapper.

### Integração e arquivos auxiliares

#### `.viralflow-gui`

- Novo arquivo JSON que mapeia ações da interface gráfica para comandos do CLI:
  execução da pipeline, atualização do Pangolin, atualização de dados,
  personalização do snpEff e construção dos contêineres.

#### `.gitignore`

- Passa a ignorar arquivos `vfnext/containers/*.overlay`.
- Evita que overlays locais, potencialmente grandes e específicos de cada
  instalação, sejam versionados.

## Arquivos apenas citados

### `install.sh`

Foi adicionado um instalador automatizado para Linux/WSL amd64 e arm64 e para
macOS por meio de uma VM Lima. Ele instala e configura as dependências,
ambiente, comandos e contêineres necessários. Sua implementação não foi
detalhada neste documento por solicitação de escopo.

### `tests/install-script.test.sh`

Foi adicionado um teste de sintaxe e de execução simulada do `install.sh`,
cobrindo Linux amd64, Linux arm64 e macOS arm64. Ele é citado por estar
diretamente associado ao instalador, mas não faz parte da lógica da pipeline.

### `README.md`

Foi ampliado para documentar instalação e uso. As alterações não foram
analisadas por se tratar de documentação.

## Arquivos documentais excluídos

Não foram considerados na análise funcional:

- `.readthedocs.yaml`;
- `dev.md`;
- `docs/installation.md`;
- `docs/quickstart.md`;
- `docs-es/installation.md`;
- `docs-es/quickstart.md`;
- `docs-pt/installation.md`;
- `docs-pt/quickstart.md`.

## Pontos sugeridos para revisão antes da integração

1. Comunicar explicitamente aos usuários e mantenedores que Apptainer é
   obrigatório e que Singularity não satisfaz mais as dependências deste fork.
2. Remover ou mover para histórico os arquivos
   `build_containers_original.py` e `build_containers_alterado.py`.
3. Confirmar se os arquivos `*-legado.yml` devem permanecer no repositório
   principal.
4. Revisar a estratégia de atualização dinâmica do Pangolin, pois ela reduz o
   pinning e pode afetar a reprodutibilidade entre instalações.
5. Avaliar se os geradores SVG devem permanecer implementados manualmente em
   `compileOutput.py` ou ser isolados em módulo próprio.
6. Confirmar se o banco incluído diretamente na imagem arm64 também deve ser
   incorporado à imagem amd64, ou se ambos devem depender exclusivamente do
   overlay.
7. Adicionar testes automatizados específicos para:
   - construção e limpeza de contêineres;
   - criação e uso dos overlays;
   - validação do banco do snpEff;
   - geração dos quatro gráficos SVG;
   - seleção da versão estável do Pangolin.
