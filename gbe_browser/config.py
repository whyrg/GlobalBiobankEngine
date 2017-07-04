import os
import scidbpy


SCIDB_INSTANCE_NUM = 2
GBE_DATA_PATH = '/home/scidb/GlobalBiobankEngine/gbe_data'


# -- -
# -- - QC - --
# -- -
QC_PATH = os.path.join(GBE_DATA_PATH, 'qc')
QC_FILES = (
    {'file': os.path.join(QC_PATH, 'UKBioBiLallfreqSNPexclude.dat'),
     'header': 1},
    {'file': os.path.join(QC_PATH, 'ukb_ukbl_low_concordance.dat')}
)

QC_ARRAY = 'qc'


# -- -
# -- - ICD - --
# -- -
ICD_GLOB = os.path.join(
    GBE_DATA_PATH, 'icdassoc', 'hybrid', 'c*.hybrid.rewrite.gz')
QT_GLOB = os.path.join(
    GBE_DATA_PATH, 'icdassoc', 'hybrid', 'c*.linear.rewrite.gz')

ICD_INFO_FILE = os.path.join(GBE_DATA_PATH, 'icdstats', 'icdinfo.txt')


ICD_INFO_ARRAY = 'icd_info'
ICD_INFO_SCHEMA = '<icd:string, Case:int64, Name:string>[icd_idx = 0:*:0:20]'

ICD_ARRAY = 'icd'
ICD_SCHEMA = """
  <icdind:      int64,
   affyid:      string,
   or_val:      double,
   se:          double,
   pvalue:      double,
   lor:         double,
   log10pvalue: double,
   l95or:       double,
   u95or:       double>
  [icd_idx   = 0:*:0:20;
   chrom     = 1:25:0:1;
   pos       = 0:*:0:10000000;
   synthetic = 0:999:0:1000]"""

ICD_PVALUE_MAP = dict(
    (pvalue, '{icd}_pvalue_lt{pvalue:05d}_ltd'.format(
        icd=ICD_ARRAY, pvalue=int(pvalue * 10e4)))
    for pvalue in [.001, .0001, .00001])
ICD_PVALUE_LIMIT = 100000

ICD_INFO_STORE_QUERY = """
  store(
    redimension(
      apply(
        input({input_schema}, '{{fn}}', 0, 'CSV'),
        Case, int64(null),
        Name, string(null)),
      {icd_info_schema}),
    {icd_info})""".format(
        input_schema=ICD_INFO_SCHEMA.replace(', Case:int64, Name:string', ''),
        icd_info_schema=ICD_INFO_SCHEMA,
        icd_info=ICD_INFO_ARRAY)

ICD_INFO_INSERT_QUERY = """
  insert(
    join(
      project({icd_info}, icd),
      redimension(
        apply(
          index_lookup(
            aio_input('{path}', 'num_attributes=6'),
            project({icd_info}, icd),
            a0,
            icd_idx),
          Case, dcast(a1, int64(null)),
          Name, a2),
        {input_schema})),
    {icd_info})""".format(
        icd_info=ICD_INFO_ARRAY,
        input_schema=ICD_INFO_SCHEMA.replace('icd:string, ', ''),
        path=ICD_INFO_FILE)

ICD_INSERT_QUERY = """
  insert(
    redimension(
      apply(
        filter(
          index_lookup(
            aio_input(
              'paths={{paths}}',
              'instances={{instances}}',
              'num_attributes=12') as INPUT,
            {qc},
            INPUT.a2,
            is_in_filter),
          substr(a0, 0, 1) <> '#' and
          a6 = 'ADD' and
          is_in_filter is null and
          dcast(a9, double(null)) < .5 and
          a11 <> 'NA' and
          dcast(a11, double(null)) <> 0),
        icd_idx,     {{icd_idx_cond}},
        chrom,       int64(a0),
        pos,         int64(a1),
        icdind,      int64(string(int64(a0) * 1e9 + int64(a1)) +
                           {{icdind_cond}}),
        affyid,      a2,
        or_val,      dcast(a8,  double(null)),
        se,          dcast(a9,  double(null)),
        pvalue,      dcast(a11, double(null)),
        lor,         log(dcast(a8, double(null))),
        log10pvalue, -log10(dcast(a11, double(null))),
        l95or,       exp(log(dcast(a8, double(null))) -
                         1.96 * dcast(a9, double(null))),
        u95or,       exp(log(dcast(a8, double(null))) +
                         1.96 * dcast(a9, double(null)))),
      {icd}),
    {icd})""".format(
        icd=ICD_ARRAY,
        qc=QC_ARRAY)

QT_INSERT_QUERY = """
  insert(
    redimension(
      apply(
        filter(
          index_lookup(
            aio_input(
              'paths={{paths}}',
              'instances={{instances}}',
              'num_attributes=12') as INPUT,
            {qc},
            INPUT.a2,
            is_in_filter),
          substr(a0, 0, 1) <> '#' and
          a5 = 'ADD' and
          is_in_filter is null and
          dcast(a8, double(null)) < .5 and
          a10 <> 'NA'),
        icd_idx,     {{icd_idx_cond}},
        chrom,       int64(a0),
        pos,         int64(a1),
        icdind,      int64(string(int64(a0) * 1e9 + int64(a1)) +
                           {{icdind_cond}}),
        affyid,      a1,
        or_val,      dcast(a7,  double(null)),
        se,          dcast(a8,  double(null)),
        pvalue,      dcast(a10, double(null)),
        lor,         dcast(a7, double(null)),
        log10pvalue, -log10(dcast(a10, double(null))),
        l95or,       exp(log(dcast(a7, double(null)))
                         - 1.96 * dcast(a8, double(null))),
        u95or,       exp(log(dcast(a7, double(null)))
                         + 1.96 * dcast(a8, double(null)))),
      {icd}),
    {icd})""".format(
        icd=ICD_ARRAY,
        qc=QC_ARRAY)

ICD_PVALUE_STORE_QUERIES = ["""
  store(
    redimension(
      cross_join(
        filter(icd, pvalue < {pvalue}) as icd_pvalue,
        filter(
          aggregate(
            filter(icd, pvalue < {pvalue}),
            count(*) as idx_cnt, icd_idx),
          idx_cnt < {limit}) as icd_pvalue_ltd,
        icd_pvalue.icd_idx,
        icd_pvalue_ltd.icd_idx),
      {icd} ),
    {icd_pvalue})""".format(
        pvalue=pvalue,
        limit=ICD_PVALUE_LIMIT,
        icd=ICD_ARRAY,
        icd_pvalue=icd_pvalue)
  for (pvalue, icd_pvalue) in ICD_PVALUE_MAP.items()]

ICD_PVALUE_LOOKUP_QUERY = """
    cross_join(
      {{icd_pvalue}},
      filter({icd_info}, icd = '{{icd}}'),
      {{icd_pvalue}}.icd_idx,
      {icd_info}.icd_idx)""".format(
        icd_info=ICD_INFO_ARRAY)

# ICD_XPOS_LOOKUP_QUERY = """
#   cross_join(
#     filter({icd}, xpos = {{xpos}}),
#     {icd_index},
#     {icd}.icd_idx,
#     {icd_index}.icd_idx)""".format(
#         icd=ICD_ARRAY,
#         icd_index=ICD_INDEX_ARRAY)

ICD_LOOKUP_SCHEMA_INST = scidbpy.schema.Schema.fromstring(
    ICD_SCHEMA.replace('>', ',icd:string,Case:int64,Name:string>'))

# -- -
# -- - VARIANT - --
# -- -
VARIANT_FILE = os.path.join(GBE_DATA_PATH,
                            'icd10ukbb.ukbiobank.merge.sort.vcf.gz')

VARIANT_ARRAY = 'variant'
VARIANT_SCHEMA = """
  <rsid:         int64,
   ref:          string,
   alt:          string,
   site_quality: string,
   filter:       string,
   exac_nfe:     double,
   minpval:      double,
   minl10pval:   double,
   csq:          string>
  [chrom     = 1:25:0:1;
   pos       = 0:*:0:10000000;
   synthetic = 0:999:0:1000]"""

VARIANT_STORE_QUERY = """
  store(
    redimension(
      apply(
        filter(
          aio_input('{{path}}', 'num_attributes=8'),
          substr(a0, 0, 1) <> '#'),
        chrom,        int64(a0),
        pos,          int64(a1),
        rsid,         iif(strlen(a2) > 1,
                          int64(substr(a2, 2, 100)),
                          int64(null)),
        ref,          a3,
        alt,          a4,
        site_quality, a5,
        filter,       a6,
        exac_nfe,     dcast(rsub(a7, 's/.*EXAC_NFE=([^;]*).*/$1/'),
                            double(null)),
        minpval,      dcast(rsub(a7, 's/.*minpval=([^;]*).*/$1/'),
                            double(null)),
        minl10pval,   dcast(rsub(a7, 's/.*minl10pval=([^;]*).*/$1/'),
                            double(null)),
        csq,          rsub(a7, 's/.*CSQ=([^;]*).*/$1/')),
      {variant}),
    {variant})""".format(variant=VARIANT_ARRAY)

VARIANT_CSQ = ('Allele',
               'Consequence',
               'IMPACT',
               'SYMBOL',
               'Gene',
               'Feature_type',
               'Feature',
               'BIOTYPE',
               'EXON',
               'INTRON',
               'HGVSc',
               'HGVSp',
               'cDNA_position',
               'CDS_position',
               'Protein_position',
               'Amino_acids',
               'Codons',
               'Existing_variation',
               'DISTANCE',
               'ALLELE_NUM',
               'STRAND',
               'VARIANT_CLASS',
               'MINIMISED',
               'SYMBOL_SOURCE',
               'HGNC_ID',
               'CANONICAL',
               'TSL',
               'APPRIS',
               'CCDS',
               'ENSP',
               'SWISSPROT',
               'TREMBL',
               'UNIPARC',
               'SIFT2',
               'SIFT',
               'PolyPhen',
               'DOMAINS',
               'HGVS_OFFSET',
               'GMAF',
               'AFR_MAF',
               'AMR_MAF',
               'EAS_MAF',
               'EUR_MAF',
               'SAS_MAF',
               'AA_MAF',
               'EA_MAF',
               'ExAC_MAF',
               'ExAC_Adj_MAF',
               'ExAC_AFR_MAF',
               'ExAC_AMR_MAF',
               'ExAC_EAS_MAF',
               'ExAC_FIN_MAF',
               'ExAC_NFE_MAF',
               'ExAC_OTH_MAF',
               'ExAC_SAS_MAF',
               'CLIN_SIG',
               'SOMATIC',
               'PHENO',
               'PUBMED',
               'MOTIF_NAME',
               'MOTIF_POS',
               'HIGH_INF_POS',
               'MOTIF_SCORE_CHANGE',
               'LoF',
               'LoF_filter',
               'LoF_flags',
               'LoF_info')


# -- -
# -- - GENE - --
# -- -
GENE_FILE = os.path.join(GBE_DATA_PATH, 'gencode.gtf.gz')

GENE_INDEX_ARRAY = 'gene_index'
GENE_INDEX_SCHEMA = '<gene_id:string>[gene_idx = 0:*:0:20]'

GENE_INDEX_STORE_QUERY = """
  store(
    redimension(
      apply(
        uniq(
          sort(
            project(
              apply(
                filter(
                  aio_input('{{path}}', 'num_attributes=9'),
                  substr(a0, 0, 1) <> '#'),
                gene_id, rsub(a8, 's/.*gene_id "([^.]*).*/$1/')),
              gene_id))),
        gene_idx, i),
      {gene_index}),
    {gene_index})""".format(gene_index=GENE_INDEX_ARRAY)


GENE_ARRAY = 'gene'
GENE_SCHEMA = """
  <gene_name: string,
   strand:    string>
  [gene_idx  = 0:*:0:20;
   chrom     = 1:25:0:1;
   start     = 0:*:0:10000000;
   stop      = 0:*:0:10000000;
   synthetic = 0:199:0:200]"""

GENE_STORE_QUERY = """
  store(
    redimension(
      index_lookup(
        apply(
          filter(
            aio_input('{{path}}', 'num_attributes=9'),
            substr(a0, 0, 1) <> '#'),
          gene_id,      rsub(a8, 's/.*gene_id "([^.]*).*/$1/'),
          chrom,        iif(substr(a0, 3, 4) = 'X',
                            23,
                            iif(substr(a0, 3, 4) = 'Y',
                                24,
                                iif(substr(a0, 3, 4) = 'M',
                                    25,
                                    dcast(substr(a0, 3, 5), int64(null))))),
          start,        int64(a3) + 1,
          stop,         int64(a4) + 1,
          gene_name,    rsub(a8, 's/.*gene_name "([^"]*).*/$1/'),
          strand,       a6) as INPUT,
        {gene_index},
        INPUT.gene_id,
        gene_idx),
      {gene}),
    {gene})""".format(gene=GENE_ARRAY, gene_index=GENE_INDEX_ARRAY)

GENE_LOOKUP_QUERY = """
  cross_join(
    {gene},
    filter({gene_index}, gene_id = '{{gene_id}}'),
    {gene}.gene_idx,
    {gene_index}.gene_idx)""".format(
        gene=GENE_ARRAY,
        gene_index=GENE_INDEX_ARRAY)

GENE_LOOKUP_SCHEMA_INST = scidbpy.schema.Schema.fromstring(
    GENE_SCHEMA.replace('>', ',gene_id:string>'))