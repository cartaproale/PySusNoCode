"""Memória de aprendizado do PySusNoCode.

Cada vez que o aplicativo encontra um erro ao executar uma célula e consegue
corrigi-lo, extrai uma "lição" (uma linha) e guarda aqui. As lições são
injetadas no prompt de sistema das próximas conversas, de modo que o app
aprende com os próprios erros entre sessões.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import date

from .config import APP_DIR, LESSONS_FILE

# Teto de lições que vão para o prompt. Precisa folgar sobre a quantidade de
# lições pré-carregadas, porque essas nunca são cortadas — a folga é o espaço
# das lições que o aplicativo aprendeu sozinho.
MAX_LESSONS_IN_PROMPT = 100
MAX_LESSONS_STORED = 250

# Lições pré-carregadas com armadilhas conhecidas do PySUS em notebooks.
SEED_LESSONS = [
    "As funcoes do pysus chamam asyncio.run() por dentro e falham em qualquer notebook ('asyncio.run() cannot be called from a running event loop'). Antes de usar a biblioteca rode: import nest_asyncio; nest_asyncio.apply().",
    "A primeira celula de codigo deve ser '%pip install pysus nest_asyncio -q' e a segunda 'import nest_asyncio; nest_asyncio.apply()' — funciona neste aplicativo e no Google Colab.",
    "O parametro group so funciona no CNES. Em SIH, SIM, SINASC e SIA, passar group faz a funcao devolver ZERO linhas: nessas bases nao passe group.",
    "No CNES o group e essencial: sem ele o download traz 33 mil linhas e 362 colunas (mais de 300 MB) com todos os grupos misturados. Use group='LT' para leitos, 'ST' para estabelecimentos, 'PF' para profissionais.",
    "Pedir um periodo inexistente no catalogo devolve tabela VAZIA, sem erro. Consulte antes com list_files(dataset=..., state=..., year=...) e verifique len(df) depois de baixar.",
    "SINAN e nacional (nao aceita state) e gigantesco: dengue de 2024 tem 6,5 milhoes de linhas e ~29 GB em memoria se carregada inteira. Use as_dataframe=False e leia so as colunas necessarias com pd.read_parquet(caminho, columns=[...]).",
    "SG_UF_NOT do SINAN vem como codigo IBGE em texto ('35'=SP, '31'=MG, '41'=PR), nao como sigla.",
    "Na base CIHA o parametro group tem 'CIHA' como valor padrao, e esse valor faz a consulta devolver ZERO linhas: e preciso passar group=None explicitamente.",
    "SIA e enorme: um unico mes de um estado grande passa de 3 milhoes de linhas e 253 colunas. Use as_dataframe=False e leia so as colunas necessarias (PA_PROC_ID, PA_QTDAPR, PA_VALAPR, PA_MUNPCN).",
    "O grupo PA (producao ambulatorial) do SIA nao existe em todos os estados e meses; confira antes no catalogo com list_files(dataset='sia', state=..., year=...).",
    "Para resumos de bases grandes, duckdb consulta o parquet sem carregar nada na memoria: duckdb.sql(\"SELECT col, COUNT(*) FROM read_parquet('caminho') GROUP BY col\"). No GROUP BY use o nome original da coluna, nao o apelido do SELECT.",
    "A populacao para calcular taxas por 100 mil habitantes vem de ibge(year=...), com colunas UFCOD, IDADE, SEXO e POPULACAO.",
    "Se o Python for encerrado durante uma celula, quase sempre foi falta de memoria por carregar uma base inteira: refaca com recorte menor ou lendo apenas as colunas necessarias.",
    "Prefira as funcoes de alto nivel do pysus 2.x com as_dataframe=True para receber um pandas.DataFrame pronto (ex.: sinan(disease='DENG', year=2024, as_dataframe=True)).",
    "Downloads do DATASUS podem demorar varios minutos; em testes iniciais baixe apenas 1 ano e, quando o dataset for estadual, apenas 1 UF.",
    "Codigo encontrado na internet com 'from pysus.online_data import ...' ou 'from pysus.ftp.databases ...' e da versao 1.x (antiga). Na 2.x use 'from pysus import sinan, sim, ...' ou o orquestrador pysus.api.client.PySUS.",
    "Colunas de DataFrames do DATASUS geralmente vem como texto (dtype object). Converta com pd.to_numeric(..., errors='coerce') ou pd.to_datetime(..., errors='coerce') antes de agregar ou plotar.",
    "Datas do SINAN como DT_NOTIFIC podem vir no formato YYYYMMDD; use pd.to_datetime(df['DT_NOTIFIC'], format='%Y%m%d', errors='coerce').",
    "O pysus devolve o caminho de um ARQUIVO .parquet, nao de uma pasta. No duckdb use read_parquet('caminho.parquet'); acrescentar '/**/*.parquet' da erro 'No files found that match the pattern'.",
    "A populacao municipal do IBGE (POPTBR) de 2022 e de 2023 esta TRUNCADA na origem: 2022 so tem o Parana (399 municipios) e 2023 so o Rio Grande do Norte (167). Antes de calcular taxa municipal, confira que o arquivo tem 5570 municipios e 27 UFs; se nao tiver, use outro ano ou trabalhe por UF com as projecoes (PROJUF), que estao completas.",
    "A idade no SIM e um codigo de 3 digitos, nao um numero de anos: o primeiro digito e a unidade (0-3 = minutos, horas, dias e meses, ou seja, menos de 1 ano; 4 = anos; 5 = anos acima de 100). Tratar IDADE como inteiro produz idades de 400 anos. Decodifique antes de usar.",
    "Ao comparar taxas entre estados, municipios ou anos, ofereca padronizacao por idade: a taxa bruta compara estruturas etarias, nao risco. Exemplo real: RS tem mortalidade bruta de 833 por 100 mil contra 491 do AP, mas depois de padronizar o AP fica pior (630 contra 546).",
    "No SIA, os procedimentos de atencao basica aparecem com valor aprovado ZERO (PA_VALAPR): eles sao pagos por bloco de financiamento, nao por procedimento. Somar valor do SIA e concluir que a atencao primaria e barata e erro de leitura — avise o usuario disso ao mostrar gasto por nivel de complexidade (campo PA_NIVCPL: 1 basica, 2 media, 3 alta).",
    "O codigo de procedimento do SIGTAP (PA_PROC_ID no SIA, PROC_REA no SIH e no CIHA) e estruturado: os 2 primeiros digitos sao o grupo (01 promocao, 02 diagnostico, 03 clinico, 04 cirurgico, 05 transplantes, 06 medicamentos, 07 orteses e proteses, 08 acoes complementares) e os 4 primeiros o subgrupo (0301 consultas, 0304 oncologia, 0305 nefrologia/dialise, 0202 laboratorio, 0206 tomografia, 0207 ressonancia). Da para classificar milhoes de linhas com substr(), sem tabela auxiliar.",
    "A pysus 2.10 tem pysus.info() e pysus.info_table(), que listam 34 conjuntos de dados de tres origens. So as 9 bases de origem FTP (SINAN, SIM, SINASC, SIH, SIA, CNES, PNI, CIHA, IBGE) tem ARQUIVOS para baixar; as 6 de origem 'DadosGov' exigem autenticacao. As 19 de origem 'Saude' devolvem zero arquivos porque NAO SAO ARQUIVOS: elas vem do portal dadosabertos.saude.gov.br e da API REST apidadosabertos.saude.gov.br. Os dados existem e estao atualizados — 'zero arquivos' nunca significa 'sem dados', significa que a fonte e servida por outro caminho.",
    "As funcoes da origem 'Saude' da pysus estao QUEBRADAS (testado na 2.10.3 e na 2.10.4): atencao_primaria() e as outras 10 de nome composto (assistencia_saude, saude_indigena, vigilancia_meio_ambiente...) devolvem lista vazia por um erro de chave interno, e o parametro group= e ignorado, entao nao ha contorno. Pior: sisvan() aponta para o grupo 'saude-indigena' e devolve dado errado com cara de certo. Para atencao primaria use SaudeClient (list_groups/list_datasets/fetch_dataset) ou baixe direto a URL publicada.",
    "Nao use pysus.quality_score() como prova de qualidade do dado do DATASUS: ele mede nulos, e o DATASUS grava campo vazio como STRING VAZIA, nao como nulo. Um arquivo do SIH cheio de campos em branco recebe nota 100 de 100 em completude. O mesmo vale para missing_values(): conte tambem as strings vazias, com (df[col].astype(str).str.strip() == '').",
    "Nao confie em pysus.validate_data() para idade: a regra embutida testa se o valor esta entre 0 e 120 e aprova a coluna IDADE do SIH, que sozinha nao quer dizer nada (precisa de COD_IDADE para saber se sao dias, meses ou anos). Ela valida a forma, nao o significado.",
    "Evite pysus.to_english(): ele traduz apenas parte dos nomes das colunas e devolve uma tabela com metade em portugues e metade em ingles (IDADE vira 'age' mas COD_IDADE fica como esta, o que e justamente a armadilha). Pior que qualquer um dos dois idiomas sozinho.",
    "pysus.load_column_metadata(base) devolve nome e descricao das colunas de sinan, sim, sinasc, sih, sia e arboviroses — util para saber o que uma coluna e. Mas quase nao traz as TABELAS DE CODIGO (so 7 colunas em todas as bases somadas explicam os codigos), entao ele nao dispensa conferir a distribuicao real com value_counts antes de rotular.",
    "pysus.disable_progress_bars() existe desde a 2.10 e promete desligar as barras de download, mas NAO TEM EFEITO — testado na 2.10.3, as barras continuam saindo em stderr. Nao ofereca essa funcao ao usuario como solucao para a saida poluida.",
    "nest_asyncio.apply() so faz sentido DENTRO de um notebook (Jupyter/Colab/este aplicativo), onde ja existe um laco de eventos rodando. Num script .py comum ele e desnecessario — a pysus funciona sem ele — e tem um efeito colateral ruim: o laco remendado nunca fecha e o Python NAO ENCERRA sozinho depois da ultima linha; o processo fica parado consumindo memoria ate ser morto a forca. Se o usuario pedir para transformar a analise num script para rodar sozinho (agendado, por linha de comando), retire o nest_asyncio.",
    "Bases diferentes fecham em anos diferentes: no Parana o SIM ja tem 2024 e o SINASC para em 2022. Ao cruzar duas bases (mortalidade infantil, por exemplo), use a INTERSECAO dos anos disponiveis, nunca o ano mais recente de uma delas — senao o numerador e de um ano e o denominador de outro.",
    "Nao use pd.set_option('display.float_format', ...) global: ele arredonda todos os numeros mostrados e esconde valores pequenos (0,0886 vira 0,09). Formate coluna a coluna com .round() quando precisar.",
    "Para separar milhar no padrao brasileiro NAO use f\"{n:,}\".replace(',', '.') dentro de uma frase: o replace troca tambem as virgulas do texto ('doencas, entre' vira 'doencas. entre'). Defina def mil(n): return f'{n:,.0f}'.replace(',', '.') e chame mil(n) dentro do f-string.",
    "Nunca adivinhe o significado dos codigos do DATASUS (ESC2010, RACACOR, GESTACAO, CONSULTAS, LOCOCOR...). Um rotulo deslocado produz uma tabela inteiramente errada sem nenhum erro de execucao. Mostre a distribuicao real (value_counts) e confira se ela faz sentido antes de rotular.",
    "sih(uf, ano, mes) devolve uma LISTA de arquivos e o primeiro costuma ser o SP (servicos profissionais, um registro por ato medico), nao o RD (uma linha por internacao, com DIAG_PRINC, DIAS_PERM, VAL_TOT e MORTE). Escolha pelo nome do arquivo: [c for c in caminhos if os.path.basename(c).upper().startswith('RD')].",
    "A cobertura do grupo RD do SIH no espelho do PySUS e esburacada: em alguns estados ha so 1 ou 2 meses por ano recente, enquanto o SP tem os 12. Consulte list_files(dataset='sih', state=UF, year=ANO) e conte os arquivos que comecam com RD antes de prometer uma analise anual.",
    "O PNI no PySUS termina em 2019 (arquivos CPNI e DPNI). Pedir 2020 ou depois devolve lista vazia sem erro.",
    "Os arquivos do SINAN nao tem as mesmas colunas entre agravos: a dengue de 2024 tem 121 colunas e o zika 38; HOSPITALIZ existe na dengue e na chikungunya, nao no zika. Consulte DESCRIBE antes de montar a consulta em vez de supor.",
    "As datas do SINAN (DT_NOTIFIC, DT_SIN_PRI) vem como TEXTO no parquet: strftime e date_diff falham com 'No function matches'. Converta com TRY_CAST(DT_SIN_PRI AS DATE). Campos numericos como NU_IDADE_N tem strings vazias: use TRY_CAST, nao CAST, senao a consulta inteira quebra.",
    "No SINAN, 'caso provavel' (o numero dos boletins do Ministerio da Saude) e notificacoes menos descartados pelo campo CLASSI_FIN — mas o CODIGO DO DESCARTE MUDA POR AGRAVO: 8 na dengue, 5 na chikungunya, 2 no zika. Usar um codigo so nas tres infla a chikungunya em mais de 60%. Para descobrir o codigo sem a tabela oficial, agrupe por CLASSI_FIN e veja onde estao os obitos: o descarte e o codigo em que praticamente ninguem morre.",
    "A idade no SINAN e NU_IDADE_N, com 4 digitos: o primeiro e a unidade (1 hora, 2 dia, 3 mes, 4 ano) e os tres seguintes o valor. 24 anos vem como '4024'.",
    "A idade no SIH vem em DOIS campos: IDADE (o numero) e COD_IDADE (a unidade: 2 dias, 3 meses, 4 anos, 5 anos acima de cem). Um recem-nascido de 3 dias aparece como idade 3. Combine os dois antes de calcular media ou faixa etaria.",
    "O grupo PF do CNES tem uma linha por VINCULO de trabalho, nao por pessoa: no PR sao 351 mil vinculos para 226 mil profissionais. Calcular 'medicos por mil habitantes' contando linhas infla o resultado em 3,6 vezes. Use count(DISTINCT CPF_PROF). Medicos sao os CBO que comecam com 225; enfermeiros, 2235.",
    "O campo REGSAUDE do CNES vem escrito de formas diferentes para a mesma regiao ('2a', '02', '002'). Normalize extraindo os digitos antes de agrupar, senao 22 regioes de saude viram 40.",
    "No CNES, TP_LEITO=3 e 'leito complementar', que inclui UTI E unidades intermediarias — nao chame de UTI. Para isolar a UTI e preciso o campo CODLEITO.",
    "Ao estratificar por escolaridade em bases de mortalidade, fixe a faixa etaria antes de comparar: a escolaridade carrega a geracao junto, e quem morreu com 80 anos ou mais quase nunca estudou. Sem esse cuidado o resultado sai invertido ('quem nao estudou vive mais'). Sem populacao por escolaridade nao ha taxa: compare composicao de causas (mortalidade proporcional) e diga isso ao usuario.",
    # --- a regressao do state= (agosto de 2026) -------------------------
    "O parametro state= diz onde PROCURAR, mas NAO FILTRA o resultado. Desde 2026 o catalogo publica um arquivo NACIONAL ao lado do arquivo de cada estado, e a pysus devolve os dois: sinasc(state='PR', year=2022) traz SINASC_2022.parquet junto com DNPR2022.parquet, o que da 2,7 milhoes de linhas do Brasil inteiro em vez das 140.637 do Parana — e ainda conta o PR duas vezes. Vale para sinasc e sim. SEMPRE confira de que UF sao as linhas depois de baixar.",
    "Para ficar so com o estado pedido use o CATALOGO, nao o nome do arquivo: em list_files(dataset=..., state=UF, year=ANO) o arquivo nacional vem com a coluna state VAZIA e o do estado vem com a sigla. Procurar a sigla dentro do nome do arquivo e armadilha — 'DO23OPEN' (o arquivo nacional do SIM) contem 'PE'.",
    "drop_duplicates() NAO conserta a mistura do arquivo nacional com o estadual: as linhas dos dois arquivos nao sao byte a byte identicas, e as duplicatas continuam la. O jeito e escolher o arquivo certo antes de ler.",
    "Nem todo ano tem arquivo por estado: o SINASC de 2023 so tem o arquivo nacional. Quando so houver o nacional, filtre as linhas pelo codigo do IBGE do estado (os 2 primeiros digitos de CODMUNRES) e AVISE o usuario que filtrou.",
    # --- funcoes novas da 2.10 que enganam ------------------------------
    "pysus.aggregate_by_age_group(df, coluna, valor) aceita QUALQUER coluna numerica como se fosse idade e nao confere nada: passando o codigo da UF ela devolve alegremente faixas '0-5', '5-15', '15-30'. Nao use sem ter certeza de que a coluna e idade em anos.",
    "pysus.detect_units() classifica TODAS as colunas numericas como 'kg' com confianca 0,5, inclusive codigo de UF e contagem de equipes. Nao serve para nada em dados do DATASUS.",
    "pysus.aggregate_by_period(df, coluna_data, valor) devolve ZERO LINHAS sem erro quando a coluna de data e texto — e no DATASUS ela quase sempre e. Converta com pd.to_datetime(..., errors='coerce') antes.",
    "pysus.to_geojson() num DataFrame sem as colunas de coordenada grava um FeatureCollection VAZIO e devolve sucesso. Confira sempre len(mapa['features']) depois de exportar.",
    "pysus.to_sql(df, nome_tabela) NAO grava banco nenhum: devolve o TEXTO de um CREATE TABLE. Para gravar de verdade use duckdb ou sqlite direto.",
    "pysus.search_columns(base, termo) so tem conteudo para 'sinan' (120 colunas para 'idade'); para 'sih', 'sim' e 'sinasc' devolve zero. pysus.get_aliases() devolve lista vazia ate para SIH/IDADE e SINASC/IDADEMAE. Nao apresente essas funcoes como dicionario geral das bases.",
    "O que vale a pena da pysus 2.10: query_parquet(caminho, sql) + to_df()/to_arrow() consultam parquet grande via duckdb sem carregar (175 mil linhas em 0,1 s), stream_parquet(caminho, chunk_size, columns) le em pedacos com selecao de colunas, mask_data()/unmask_data() criptografam e revertem colunas sensiveis com uma chave (util para compartilhar dado), column_stats() e profile_report() dao um retrato rapido de cada coluna.",
    # --- atencao primaria: onde os dados realmente estao ----------------
    "Os indicadores do Previne Brasil / SISAB estao na API REST apidadosabertos.saude.gov.br, no endpoint /atencao-primaria/indicador-desempenho-programa-previne-brasil, com filtros de uf, competencia, quadrimestre e codigo_municipio. O helper pysus.api.saude.rest.iter_rows pagina para voce.",
    "A paginacao por offset da API do Ministerio da Saude e INSTAVEL: ela desloca linhas sobre um resultado sem ordenacao garantida. Tres coletas seguidas do mesmo recorte devolveram 21.546 linhas cada, mas 14.071, 16.137 e 12.829 registros DISTINTOS. O total sempre bate e o conteudo nunca. Nao pagine: particione o pedido (um municipio por vez, com codigo_municipio) ate caber numa resposta so.",
    "No Previne Brasil a coluna 'percentual' NAO e o resultado do indicador — e cobertura de cadastro (identificados / estimados do IBGE), por isso passa de 100 em metade das linhas. O resultado do indicador e 'percentual_quadrimestre' (numerador / denominador_utilizador). Conferido em 100% das linhas.",
    "Os codigos de indicador do Previne Brasil (10, 20, 30, 40, 50, 70) nao estao documentados no swagger nem na pysus, e um dos sete oficiais nao aparece na API. Da para separa-los pela evidencia: os tres de gestante compartilham denominador identico em 100% dos municipios. Nunca invente o rotulo que falta.",
    "Os 89 indicadores de atencao primaria do MGDI (equipes, saude bucal, Academia da Saude, Farmacia Popular, telessaude) sao .csv.zip publicados em demas-dados-abertos.s3.amazonaws.com/csv/<nome>.csv.zip, todos com o MESMO esquema de 25 colunas: uma receita serve para qualquer um. Quando a mesma base tem API paginada e arquivo publicado, PREFIRA O ARQUIVO.",
    "Nos indicadores MGDI, vl_indicador_calculado_al e a AMAZONIA LEGAL — 773 municipios de 9 UFs, zero nas demais linhas. O nome nao diz isso. As demais colunas agregadas (_rs regiao de saude, _ms macrorregiao, _uf, _reg, _br) fecham exatamente com a soma dos municipios.",
    "Nos indicadores MGDI, ZERO nao quer dizer ausencia do servico: cada arquivo mede uma MODALIDADE. Dos 502 municipios com zero equipes de Saude Bucal 40h, 147 (29%) tem equipe na modalidade de carga horaria diferenciada, contada em outro arquivo.",
    "Nem todo indicador do MGDI e somavel: equipes, polos e centros pertencem a um municipio so e a soma bate com o total nacional, mas 'pessoas atendidas' nao fecha (a mesma pessoa e atendida em mais de um municipio). Antes de somar por municipio, veja a unidade de medida — quando conta pessoas, use a coluna agregada que o arquivo ja traz.",
    "A periodicidade dos indicadores MGDI VARIA: uns sao mensais, outros trazem so dezembro de cada ano, outros junho. co_anomes no formato AAAAMM nao garante serie mensal, e comparar 'o mais recente de cada indicador' compara meses diferentes. Confira os meses presentes antes de plotar.",
    "No cadastro de UBS (47.910 unidades), LATITUDE e LONGITUDE vem como texto com virgula E ponto misturados no mesmo arquivo — sem str.replace(',', '.') viram NaN e o mapa sai vazio sem erro; 4% nao tem coordenada. A coluna UF guarda o CODIGO do IBGE (41 = PR), nao a sigla. E o retangulo 'do Brasil' (-34 a 6, -74 a -34) reprova as UBS de Fernando de Noronha, que ficam a leste de -34.",
    "Ausencia no arquivo nao e ausencia de rede: 83 municipios nao tem nenhuma UBS cadastrada, e 67 deles (81%) tem equipe de saude bucal custeada. O maior e Araruama (RJ), com 137 mil habitantes. Antes de concluir que falta servico, cruze com outro registro.",
    # --- a propria biblioteca -------------------------------------------
    "A pysus NAO declara o PyYAML entre as dependencias dela, embora importe 'yaml' na inicializacao: 'pip install pysus' num ambiente limpo falha no 'import pysus' com ModuleNotFoundError. Continua assim na 2.10.4. Se o usuario montar um ambiente novo, instale pyyaml junto.",
    "A pysus 2.10 teve cinco versoes em tres dias (2.10.0 a 2.10.4, agosto de 2026) e a documentacao do Read the Docs ficou para tras (ela ainda se identifica como 2.9.0). Para trabalho que precisa ser reproduzivel, fixe a versao (pysus==2.10.4) em vez de usar piso aberto, e confie no codigo da tag antes da documentacao.",
]


class LessonStore:
    def __init__(self) -> None:
        self.lessons: list[dict] = []
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        """Carrega as lições, juntando as guardadas com as desta versão.

        Cuidado histórico: até a versão 1.8.3 este método só criava o arquivo
        quando ele ainda não existia. Quem já tinha o aplicativo instalado
        ficava congelado nas lições da primeira instalação e nunca recebia as
        novas — o aplicativo atualizava, e a parte que ele sabe sobre o
        DATASUS, não.
        """
        guardadas: list[dict] = []
        try:
            if LESSONS_FILE.exists():
                carregado = json.loads(LESSONS_FILE.read_text(encoding="utf-8"))
                if isinstance(carregado, list):
                    guardadas = [x for x in carregado if isinstance(x, dict) and x.get("licao")]
        except Exception:  # noqa: BLE001
            guardadas = []          # arquivo corrompido: recomeça das sementes

        self.lessons = self._sincronizar(guardadas)
        try:
            self.save()
        except Exception:  # noqa: BLE001
            pass

    def _sincronizar(self, guardadas: list[dict]) -> list[dict]:
        """Junta o que o aplicativo aprendeu sozinho com as lições da versão.

        As lições aprendidas com erros reais são do usuário e ficam sempre.
        As pré-carregadas são nossas e passam a ser as desta versão: se uma
        saiu do código, saiu porque foi corrigida ou superada, e mantê-la faria
        o assistente seguir uma regra que já sabemos errada.
        """
        aprendidas = [x for x in guardadas if x.get("origem") != "pre-carregada"]
        ja_conhecidas = {self._norm(x["licao"]) for x in aprendidas}
        hoje = str(date.today())
        sementes = [
            {"licao": texto, "origem": "pre-carregada", "data": hoje}
            for texto in SEED_LESSONS
            if self._norm(texto) not in ja_conhecidas
        ]
        return sementes + aprendidas

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        LESSONS_FILE.write_text(
            json.dumps(self.lessons[-MAX_LESSONS_STORED:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _norm(text: str) -> str:
        text = unicodedata.normalize("NFKD", text.lower().strip())
        return "".join(c for c in text if not unicodedata.combining(c))

    def add(self, licao: str, origem: str = "erro corrigido") -> bool:
        """Guarda uma nova lição; devolve False se já existia uma equivalente."""
        licao = " ".join(licao.split())
        if not licao or len(licao) < 15:
            return False
        norm = self._norm(licao)
        for existing in self.lessons:
            if self._norm(existing["licao"]) == norm:
                return False
        self.lessons.append(
            {"licao": licao, "origem": origem, "data": str(date.today())}
        )
        self.save()
        return True

    def for_prompt(self) -> str:
        """Bloco de texto com as lições, para injetar no prompt de sistema.

        As pré-carregadas nunca são cortadas: são elas que evitam os erros que
        travam o notebook (o nest_asyncio, o group de cada base, as bases que
        estouram a memória). Um corte simples pelas últimas do arquivo
        derrubaria justamente as primeiras da lista, que são as mais básicas.
        Quando não cabe tudo, quem sai são as aprendidas mais antigas.
        """
        sementes = [x for x in self.lessons if x.get("origem") == "pre-carregada"]
        aprendidas = [x for x in self.lessons if x.get("origem") != "pre-carregada"]

        espaco = MAX_LESSONS_IN_PROMPT - len(sementes)
        if espaco > 0:
            selecionadas = sementes + aprendidas[-espaco:]
        else:
            selecionadas = sementes

        if not selecionadas:
            return ""
        return "\n".join(f"- {item['licao']}" for item in selecionadas)

    def count(self) -> int:
        return len(self.lessons)
