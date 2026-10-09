# Validação Docker da branch docker/develop

Base inicial: `16cb3f30b1d3f6e085d96647dba196263cd5ddd8` (2026-10-08).
Comparação: branch `docker/develop-SIF3-MAC`. Objetivo: executar a CLI desta
base, preservando a estrutura da equipe de nanopore e aplicando apenas as
correções demonstradas por testes. Este registro não significa que a branch
nanopore já foi integrada ou validada.

## Preparação do protótipo

Os arquivos de empacotamento permanecem em ViralFlowGui. A CLI de compose.yaml
usa Develop.Dockerfile, a branch docker/develop e o commit acima. A imagem é
viralflow-cli:develop-ubuntu26.04. Volumes develop-containers, develop-databases
e develop-runtime isolam este teste dos SIFs/overlays da versão anterior.
A GUI continua usando a imagem CLI anterior; este teste não altera sua base.

Esta branch não possui install.sh. Por isso, o Docker instala Micromamba 1.5.7
e cria o ambiente diretamente de envs/amd64.yml, inicialmente sem alterar
Nextflow 22.04.0 nem SingularityCE 3.11.4. Ao contrário da branch SIF/MAC,
Pangolin e snpEff inicialmente permanecem sandboxes.

Para testar correções locais sem publicá-las, prepare-develop-source.py exporta
somente arquivos rastreados do working tree. O Docker clona o commit definido
e sobrepõe esses fontes nativos. .docker-source-revision identifica o commit
base; .docker-source-changes.patch registra diferenças locais. Não há patch
textual aplicado em tempo de execução. Executar o exportador novamente após
cada mudança. Arquivos novos de código precisam ser rastreados antes do export.

## Testes e correções

Resultados serão registrados abaixo conforme os testes forem executados.

### 1. Limitar tentativas de download

Arquivo: vfnext/containers/spython_functions.py.

Falha demonstrada: simulando uma imagem indisponível, o downloader tentou
uma quarta vez após o limite esperado de três. A condição `missing OR attempts`
continuava verdadeira mesmo quando o contador se tornava negativo.

Correção: usar `AND`, limitar a três passagens, baixar somente imagens ainda
faltantes e gerar erro com a lista que permanece indisponível.

Comparação: SIF3/MAC possui retries e erro em container_pull via subprocess,
mas mantém o laço externo com OR. Aqui foi corrigido diretamente o controle
do laço, mantendo o executável Singularity e o formato dos repositórios.
Testes: falha permanente encerra após três tentativas; recuperação baixa somente
faltantes; nenhuma pendência não executa downloads (simulações sem rede).

### 2. Propagar falhas do build e do pipeline

Arquivos: wrapper/__init__.py; vfnext/containers/build_containers.py.

Falha demonstrada: um Nextflow simulado retornando 17 era ignorado pelo
wrapper (retorno None, comando CLI com aparência de sucesso). O builder também
não retornava erro quando um build ou uma preparação adicional falhava.

Correção: subprocess.run(check=True) com ClickException para build-containers
e run; interromper o build após falha no pull. Builder retorna 1 se qualquer
etapa falha, inclusive ausência do unsquashfs esperado.

Comparação: SIF3/MAC já utiliza subprocess.check_call no build, mas mantém
os.system no run. Foi adotada a verificação de status em ambos os caminhos,
sem trazer alterações de overlays, gráficos ou atualização de Pangolin.

### Primeiro build: ambiente original preservado

A imagem base foi construída com sucesso a partir do ambiente original.
ViralFlow 1.4.0, SingularityCE 3.11.4 e Nextflow 22.04.0 responderam aos
comandos de versão. `python -m pip check` não encontrou requisitos quebrados.
O resolvedor selecionou Python 3.14 e Java 17.0.17; não foi necessário remover
Nextflow/SingularityCE do YAML nem importar o instalador SIF/MAC.
Log: ViralFlowGui/docker/develop-build-baseline.log (primeira execução).

Os testes simulados das correções 1 e 2 passaram. A primeira construção dos
containers científicos usa ainda os fontes originais, para capturar suas
falhas antes de reconstruir a imagem com as correções locais.

### 3. Escrita somente nos sandboxes

Arquivo: vfnext/configs/containers.config.

Falha real: SingularityCE recusou executar edirect:1.1.0.sif com a opção global
--writable: `no SIF writable overlay partition found`. A imagem baixada é
SIF imutável e não possui overlay gravável.

Correção inicial: retirar --writable global no AMD64 e restringir essa opção
a runPangolin/runSnpEff, que usam sandboxes nesta branch. ARM64 mantém a
configuração anterior, ainda não testada. checkSnpEffDB lê somente o catálogo.

Comparação: SIF3/MAC converteu os dois sandboxes em SIFs com overlays externos,
montados por processo. Para o protótipo atual, basta distinguir os sandboxes
dos SIFs; não foi importada a conversão de formatos nem sua lógica de updates.
Log de reprodução: ViralFlowGui/docker/develop-singularity-bind-baseline.log.

### 4. /etc/localtime na imagem mínima

Arquivo de empacotamento: ViralFlowGui/docker/Develop.Dockerfile.

Depois de remover --writable, o Singularity falhou ao montar /etc/localtime,
pois esse arquivo não existe no Ubuntu mínimo. Executar o mesmo SIF com
--no-mount /etc/localtime confirmou que a ferramenta funciona (edirect 24.0).
A imagem passa a fornecer /etc/localtime com o fuso UTC já instalado pelo
pacote tzdata do Conda; não são acrescentadas dependências nem desabilitadas
montagens no código científico.

Comparação: o instalador anterior instala diversos pacotes adicionais e usa
Apptainer; esta ausência não precisou de uma correção explícita naquele Docker.
Esta alteração é exclusiva do empacotamento, sem impacto no merge do nanopore.
Logs: develop-singularity-readonly.log e develop-singularity-no-localtime.log.

### 5. Não usar fakeroot quando já somos root

Arquivo: vfnext/containers/build_containers.py.

Falha real: ambos os builds falharam com `could not use fakeroot: no mapping
entry found in /etc/subuid for root`. O Docker privilegiado já executa como
root, dispensando emulação de privilégios.

Correção: incluir --fakeroot somente quando os.geteuid() != 0. Manter esse
parâmetro para execução nativa como usuário comum; não criar mapeamentos
artificiais de root nem instalar outro runtime.

Comparação: o Docker SIF3/MAC usa um adaptador de Apptainer que remove
--fakeroot quando UID=0. Aqui o ajuste fica no comando nativo do builder,
funcionando também em outras execuções como root com SingularityCE.
Log: develop-containers-baseline.log. Esse comando baseline retornou 0 apesar
das duas falhas, confirmando também a necessidade da correção 2.

### 6. Base de construção do Pangolin

Arquivo: vfnext/containers/def_files/amd64/Singularity_pangolin.

Falha real: a imagem library://debian:11 baixou índices Bullseye, mas os
pacotes openssl, ca-certificates, curl e suas bibliotecas retornaram 404
no repositório de segurança, impedindo apt-get install.

Correção inicial: usar docker://debian:12-slim, como na branch SIF3/MAC.
Acrescentar set -e explícito e -y ao install de Micromamba para build
não interativo. Permanecem Python 3.11, Usher 0.6.2, Snakemake 9.19.0 e
Pangolin 4.4; as alterações maiores de instalação via Git e de pins da branch
anterior só serão consideradas se o próximo teste demonstrar sua necessidade.

Alternativa considerada: manter a imagem antiga e trocar mirrors de Debian11.
Foi preferida a base Debian12 já validada no protótipo anterior, sem remendar
pacotes de segurança ausentes na imagem de biblioteca.
Log: develop-containers.log (primeira tentativa corrigida).

### 7. Mirrors de Debian Buster no snpEff

Arquivo: vfnext/containers/def_files/amd64/Singularity_snpEff.

Falha real: os repositórios Debian Buster da base miniconda3:4.7.12 retornaram
404/ausência de Release. O script continuou a instalar Conda apesar dessa
falha, pois o apt estava numa lista com && sem set -e geral.

Correção: usar archive.debian.org para os mirrors de Debian e de segurança,
desabilitar Check-Valid-Until dos índices arquivados e tornar o script
fail-fast com set -e. A falha do apt-get agora encerra a construção antes
que o container possa parecer válido.

Comparação: mesmo ajuste pontual da definição SIF3/MAC. Mantida a base antiga
para reduzir o impacto sobre a instalação existente de snpEff 5.0, em vez de
reescrever toda a instalação Conda. Log: develop-containers.log.

Verificação da correção 2 na CLI Docker: um executável Nextflow de teste que
retorna 17 fez `viralflow run` terminar com status 1 e mensagem explícita
`Command failed with exit code 17`, em vez de sucesso silencioso.
Log: develop-cli-failure-test.log (falha proposital, não execução científica).

Verificação da correção 4: o SIF edirect executou normalmente, sem
--no-mount, depois de fornecer /etc/localtime na imagem. pip check do ambiente
principal continua sem conflitos. Log: develop-runtime.log.

### 8. Compatibilidade Python/Conda de Pangolin 4.4

Arquivo: vfnext/containers/def_files/amd64/Singularity_pangolin.

Falha real: o sandbox respondeu `pangolin 4.4`, mas pip check detectou:
Snakemake 9.19.0 exige packaging<26 (Conda instalou 26.3); Pangolin exige
pandas~=2.3.1 (instalado 3.0.6) e scikit-learn==1.7.1 (instalado 1.2.2).
A leitura do conda-meta confirmou que o recipe de Pangolin exige sklearn<1.3,
em contradição com a metadata Python. Simplesmente acrescentar pins mantendo
pangolin=4.4 no Conda não resolve essa contradição.

Correção: remover somente a aplicação pangolin do install Conda e instalá-la
via pip da tag oficial v4.4. Auxiliares, pangolin-data, scorpio e constellations
permanecem no Conda. Fixar pandas 2.3.x e scikit-learn 1.7.1; fixar packaging
>=24,<26 e interface-common >=1.20.1,<1.23 para Snakemake 9.19.0. Incluir
setuptools<81/wheel para a instalação dessa tag antiga sem build isolation e
validar pip check durante o build.

Comparação: SIF3/MAC instala a aplicação e também dados/Scorpio/constellations
via Git, com compiladores adicionais e self-update de Micromamba. Aqui são
mantidos Conda para os auxiliares e Micromamba 1.5.7, sem acrescentar compiladores;
a tag da aplicação é a mesma. Os pins de packaging/common seguem a solução
anterior; os pins de pandas/sklearn explicitam os requisitos observados.
Logs: develop-pangolin-check.log e develop-pangolin-metadata.log.

Validação da correção 7: o sandbox snpEff foi construído; respondeu SnpEff 5.0e,
baixou NC_045512.2 e gerou seu catálogo. Os 11 SIFs foram preservados e a
preparação de dados Nextclade também passou. Log completo dessa construção:
ViralFlowGui/docker/develop-containers-conda-baseline.log.

O primeiro sandbox Pangolin Conda foi preservado no volume de testes com o nome
pangolin:4.4-conda-baseline para comparação. O builder irá construir um novo
pangolin:4.4.sif usando a definição da correção 8; os dois continuam sendo
diretórios de sandbox, sem conversão para SIF.

Validação da correção 8: Pangolin 4.4 foi instalado da tag v4.4 e pip check
passou dentro do build. Não foi necessário instalar compiladores nem mudar
o Micromamba. build-containers retornou 0 após construir Pangolin, reutilizar
snpEff, preparar o dataset Nextclade e gerar o catálogo snpEff.
Log: ViralFlowGui/docker/develop-containers.log.

A configuração Nextflow foi resolvida com sucesso: opção global sem
--writable e opções --writable somente em runPangolin/runSnpEff no AMD64.
Log: develop-nextflow-config.log. Iniciada a execução completa do fixture
SARS-CoV-2 do repositório (ART1/ART2 paired-end, ART3 single-end e Cneg),
com snpEff e exportação de reads habilitados. Dados e resultados estão em
ViralFlowGui/docker-data/develop/test_files/sars-cov-2/.

### 9. Montar projeto/dados e permitir binds nos sandboxes

Arquivo: vfnext/configs/containers.config (refinamento da correção 3).

Falha real na primeira análise: checkSnpEffDB não enxergava o catálogo em
/opt/viralflow/vfnext/containers/snpEff_DB.catalog. Os scripts de vários outros
processos também usam projectDir e outDir por caminhos absolutos, que não são
inputs staged pelo Nextflow.

Correção: acrescentar binds explícitos de projectDir e launchDir. O teste
com esses binds e --writable falhou porque o sandbox não contém os diretórios
de destino. O mesmo teste com --writable-tmpfs passou. Por isso, runPangolin e
runSnpEff passam a usar --writable-tmpfs em AMD64. SIFs restantes continuam
sem opção de escrita. ARM64 mantém sua escrita tmpfs anterior, com os binds
acrescentados, sem validação desta arquitetura.

Comparação: SIF3/MAC também acrescentou esses dois binds, mas usa SIFs com
overlays persistentes externos. Foi escolhida escrita temporária por processo,
compatível com os sandboxes desta branch e independente do caminho do checkout.
Não é necessário criar /data ou /opt/viralflow em cada definição científica.
Saídas nos diretórios montados persistem; alterações internas de ferramentas
durante a análise não persistem. Os comandos explícitos de atualização do
Pangolin e preparação snpEff continuam utilizando seus sandboxes graváveis.
A atualização dessas ferramentas ainda não foi testada neste protótipo.
Logs: develop-run-bind-baseline.log, develop-sandbox-bind-writable.log e
 develop-sandbox-bind-tmpfs.log.

## Resultado desta rodada

A CLI em Docker AMD64/Ubuntu26.04 executou o fixture SARS-CoV-2 completo com
sucesso: 2m51s, 65 tarefas executadas e 1 tarefa em cache (referência preparada
na primeira tentativa). Todos os processos finalizaram, incluindo Pangolin,
Nextclade, snpEff, gráficos, Picard, relatório e compileOutputs_SC2.

Verificação dos artefatos:
- ART1/ART2 paired-end, ART3 single-end e Cneg presentes nas métricas compiladas;
- quatro sequências major no seqbatch.fa, quatro registros major e três minor;
- sete registros de classificação tanto no pango.csv quanto no nextclade.csv;
- CSVs com número consistente de colunas;
- Cneg com qc_status=fail no Pangolin;
- gráficos e relatório snpEff das quatro amostras, index HTML e oito relatórios
  individuais fastp/snpEff presentes e não vazios;
- errors_detected.csv sem entradas.

Logs finais (ViralFlowGui): docker/develop-build.log,
docker/develop-containers.log, docker/develop-run.log e
docker/develop-validation.log. Relatório:
docker-data/develop/test_files/sars-cov-2/outputs/COMPILED_OUTPUT/VF_REPORT/index.html.

Imagem final: viralflow-cli:develop-ubuntu26.04, baseada no commit 16cb3f3
mais as alterações locais documentadas acima. Nenhum commit/publicação foi
realizado nesta rodada. A branch SIF3/MAC, imagens GUI anteriores e seus volumes
não foram substituídos. No ViralFlow foram alterados seis arquivos existentes
(config, builder, duas definições AMD64, downloader e wrapper), além deste
registro. envs/amd64.yml permanece original.

## Pendências e limites de validação

- A funcionalidade nanopore ainda não foi integrada nem testada; esta rodada
  valida apenas os fixtures Illumina paired/single-end desta base.
- Sem validação de GUI, ARM64, macOS/Windows, vírus customizados ou comandos
  de atualização do Pangolin. Bases de classificação e dependências não fixadas
  integralmente podem mudar em um novo build; não há lockfile nesta branch.
- O Nextflow emitiu warnings de cardinalidade nos inputs runPangolin/runNextClade:
  o join envia oito elementos, enquanto cada módulo declara seis. Os dois
  elementos extras são VCF/índice, que esses módulos não usam. A mesma declaração
  de seis elementos existe na branch SIF3/MAC. A execução e os artefatos passaram;
  o aviso foi registrado para revisar os canais junto ao merge nanopore, sem
  alterar agora o contrato do workflow.
- O teste confirma execução e consistência estrutural dos resultados; não é
  uma validação científica abrangente de sensibilidade/especificidade.

## Reproduzir o build local

Na raiz de ViralFlowGui, com ViralFlow em docker/develop no commit configurado:

```bash
python3 docker/prepare-develop-source.py ../ViralFlow
docker compose --progress plain build viralflow
docker compose run --rm viralflow build-containers --arch amd64
docker compose run --rm viralflow run --params-file /data/test_files/sars-cov-2.params
```

O último comando utiliza os fixtures já copiados para docker-data/develop nesta
rodada. Para novos dados, crie outro params com caminhos dentro de /data e ajuste
VIRALFLOW_DATA_DIR se necessário. Ao publicar as correções em um novo commit,
atualizar VIRALFLOW_COMMIT no Compose/Dockerfile ou passá-lo pelo ambiente, e
exportar novamente o working tree. O commit exportado deve coincidir com o
commit pedido no build. /opt/viralflow-image-revision e
/opt/viralflow-image-local-changes.patch identificam a base e as diferenças.


## 2026-10-09 — gráficos dos resultados compilados

Origem: branch `docker/develop-SIF3-MAC`, commit
`984f4b6746c8ab98910e2641b60f53dae5607e1a`.
Destino: working tree de `docker/develop`, base `1bc34d3`.

Arquivo alterado: `vfnext/bin/compileOutput.py`.
A comparação entre as branches mostrou que as diferenças nesse arquivo eram
apenas a geração de quatro gráficos SVG, seus helpers e as chamadas após
escrever as tabelas compiladas. Foi trazida essa implementação integralmente,
sem alterações nos módulos Nextflow, nas definições de containers ou no
cálculo das métricas existentes. Não há dependências gráficas novas: a geração
usa pandas já instalado, `math` da biblioteca padrão e escrita de SVG.

Arquivos gerados automaticamente em `COMPILED_OUTPUT/`:

- `reads_count_plot.svg`: quantidade total de reads por amostra;
- `coverage_plot.svg`: amplitude de cobertura versus profundidade média;
- `coverage_breadth_summary_plot.svg`: distribuição nas faixas 0–30%,
  acima de 30% e abaixo de 70%, e 70–100%;
- `coverage_breadth_decile_plot.svg`: distribuição em intervalos de 10%.

A implementação mantém os rótulos, a ordenação, o destaque dos controles
Cneg, a regressão do gráfico de cobertura e o tratamento de dados ausentes da
branch de origem. Os gráficos de cobertura são chamados nos fluxos
`sars-cov2` e `custom`; esta rodada verificou resultados SARS-CoV-2.

Validação: recompilação dos resultados existentes das quatro amostras do teste
GUI, em diretórios separados, usando o script anterior e o script com gráficos.
Os dez CSVs e `seqbatch.fa` ficaram idênticos byte a byte. Os quatro SVGs foram
gerados, são XML válido e não contêm coordenadas NaN. Importação do script e
`git diff --check` passaram. Não foi reexecutada a análise científica completa.

Artefatos locais em ViralFlowGui:
`docker-data/plots-port-validation/ported/`, logs `baseline.log` e `ported.log`,
e `validation.json` na pasta `docker-data/plots-port-validation/`.
Nenhuma imagem Docker foi reconstruída. Para incluir os gráficos nas imagens,
publique este código, atualize `VIRALFLOW_COMMIT` em `docker/Dockerfile` do
ViralFlowGui e reconstrua a GUI pelo Compose (que constrói a base CLI).
