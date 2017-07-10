import os
import scidbpy


# == =
# == = Load = ==
# == =

SCIDB_INSTANCE_NUM = 2
GBE_DATA_PATH = '/home/scidb/GlobalBiobankEngine/gbe_data'


# -- -
# -- - Load: QC - --
# -- -
QC_PATH = os.path.join(GBE_DATA_PATH, 'qc')
QC_FILES = (
    {'file': os.path.join(QC_PATH, 'UKBioBiLallfreqSNPexclude.dat'),
     'header': 1},
    {'file': os.path.join(QC_PATH, 'ukb_ukbl_low_concordance.dat')}
)

QC_ARRAY = 'qc'


# -- -
# -- - Load: ICD - --
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
   pdecimal  = 0:3:0:1;
   synthetic = 0:999:0:1000]"""

ICD_PVALUE_MAP = dict(zip((.001, .0001, .00001), range(1, 4)))

# TODO 10K limit

ICD_INFO_STORE_QUERY = """
  store(
    redimension(
      apply(
        input({input_schema}, '{{fn}}', 0, 'CSV'),
        Case, int64(null),
        Name, string(null)),
      {icd_info_schema}),
    {icd_info_array})""".format(
        input_schema=ICD_INFO_SCHEMA.replace(', Case:int64, Name:string', ''),
        icd_info_schema=ICD_INFO_SCHEMA,
        icd_info_array=ICD_INFO_ARRAY)

ICD_INFO_INSERT_QUERY = """
  insert(
    join(
      project({icd_info_array}, icd),
      redimension(
        apply(
          index_lookup(
            aio_input('{path}', 'num_attributes=6'),
            project({icd_info_array}, icd),
            a0,
            icd_idx),
          Case, dcast(a1, int64(null)),
          Name, a2),
        {input_schema})),
    {icd_info_array})""".format(
        icd_info_array=ICD_INFO_ARRAY,
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
            {qc_array},
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
        pdecimal,    iif(dcast(a11, double(null)) < .00001, 3,
                      iif(dcast(a11, double(null)) < .0001, 2,
                       iif(dcast(a11, double(null)) < .001, 1, 0))),
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
      {icd_array}),
    {icd_array})""".format(
        icd_array=ICD_ARRAY,
        qc_array=QC_ARRAY)

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
            {qc_array},
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
        pdecimal,    iif(dcast(a10, double(null)) < .00001, 3,
                      iif(dcast(a10, double(null)) < .0001, 2,
                       iif(dcast(a10, double(null)) < .001, 1, 0))),
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
      {icd_array}),
    {icd_array})""".format(
        icd_array=ICD_ARRAY,
        qc_array=QC_ARRAY)


# -- -
# -- - Load: GENE - --
# -- -
GENE_FILE = os.path.join(GBE_DATA_PATH, 'gencode.gtf.gz')
CANONICAL_FILE = os.path.join(GBE_DATA_PATH, 'canonical_transcripts.txt.gz')
DBNSFP_FILE = os.path.join(GBE_DATA_PATH, 'dbNSFP2.6_gene.gz')
OMIM_FILE = os.path.join(GBE_DATA_PATH, 'omim_info.txt.gz')

GENE_INDEX_ARRAY = 'gene_index'
GENE_INDEX_SCHEMA = '<gene_id: string>[gene_idx = 0:*:0:20]'

GENE_INDEX_STORE_QUERY = """
  store(
    redimension(
      apply(
        aio_input('{{path}}', 'num_attributes=1'),
        gene_idx, tuple_no,
        gene_id,  rsub(a0, 's/"([^.]*).*/$1/')),
      {gene_index_schema}),
    {gene_index_array})""".format(gene_index_schema=GENE_INDEX_SCHEMA,
                                  gene_index_array=GENE_INDEX_ARRAY)

DBNSFP_ARRAY = 'dbnsfp'
DBNSFP_SCHEMA = '<full_gene_name: string>[gene_idx = 0:*:0:20]'

DBNSFP_STORE_QUERY = """
  store(
    redimension(
      index_lookup(
        apply(
          filter(
            aio_input('{{path}}', 'num_attributes=14', 'header=1'),
            a1 <> '.' and a0 <> a12),
          full_gene_name, a12),
        {gene_index_array},
        a1,
        gene_idx),
      {dbnsfp_schema}, false),
    {dbnsfp_array})""".format(gene_index_array=GENE_INDEX_ARRAY,
                              dbnsfp_schema=DBNSFP_SCHEMA,
                              dbnsfp_array=DBNSFP_ARRAY)

CANONICAL_ARRAY = 'canonical'
CANONICAL_SCHEMA = '<canonical_transcript: string>[gene_idx = 0:*:0:20]'

CANONICAL_STORE_QUERY = """
  store(
    redimension(
      index_lookup(
        apply(
          aio_input('{{path}}', 'num_attributes=2'),
          canonical_transcript, a1),
        {gene_index_array},
        a0,
        gene_idx),
      {canonical_schema}, false),
    {canonical_array})""".format(gene_index_array=GENE_INDEX_ARRAY,
                                 canonical_schema=CANONICAL_SCHEMA,
                                 canonical_array=CANONICAL_ARRAY)

OMIM_ARRAY = 'omim'
OMIM_SCHEMA = '<omim_accession: string>[gene_idx = 0:*:0:20]'

OMIM_STORE_QUERY = """
  store(
    redimension(
      index_lookup(
        apply(
          aio_input('{{path}}', 'num_attributes=4'),
          omim_accession, a2),
        {gene_index_array},
        a0,
        gene_idx),
      {omim_schema}, false),
    {omim_array})""".format(gene_index_array=GENE_INDEX_ARRAY,
                            omim_schema=OMIM_SCHEMA,
                            omim_array=OMIM_ARRAY)

TRANSCRIPT_INDEX_ARRAY = 'transcript_index'
TRANSCRIPT_INDEX_SCHEMA = """
  <transcript_id:string>[transcript_idx = 0:*:0:20]"""

TRANSCRIPT_INDEX_STORE_QUERY = """
  store(
    redimension(
      apply(
        aio_input('{{path}}', 'num_attributes=1'),
        transcript_idx, tuple_no,
        transcript_id,  rsub(a0, 's/"([^.]*).*/$1/')),
      {transcript_index_schema}),
    {transcript_index_array})""".format(
        transcript_index_schema=TRANSCRIPT_INDEX_SCHEMA,
        transcript_index_array=TRANSCRIPT_INDEX_ARRAY)

GENE_ARRAY = 'gene'
GENE_SCHEMA = """
  <gene_name:            string,
   strand:               string,
   full_gene_name:       string,
   canonical_transcript: string,
   omim_accession:       string>
  [gene_idx       = 0:*:0:20;
   chrom          = 1:25:0:1;
   start          = 0:*:0:10000000;
   stop           = 0:*:0:10000000]"""

GENE_STORE_QUERY = """
  store(
    redimension(
      join(
        join(
          join(
            redimension(
              index_lookup(
                apply(
                  aio_input('{{path}}', 'num_attributes=9'),
                  g_id,       rsub(a8, 's/.*gene_id "([^.]*).*/$1/'),
                  chrom,     iif(substr(a0, 3, 4) = 'X',
                                 23,
                                 iif(substr(a0, 3, 4) = 'Y',
                                     24,
                                     iif(substr(a0, 3, 4) = 'M',
                                         25,
                                         int64(substr(a0, 3, 5))))),
                  start,     int64(a3) + 1,
                  stop,      int64(a4) + 1,
                  gene_name, rsub(a8, 's/.*gene_name "([^"]*).*/$1/'),
                  strand,    a6),
                {gene_index_array},
                g_id,
                gene_idx),

              <gene_name: string,
               strand:    string,
               chrom:     int64,
               start:     int64,
               stop:      int64>
              [gene_idx = 0:*:0:20]),

            {dbnsfp_array}),
          {canonical_array}),
        {omim_array}),
      {gene_schema}),
    {gene_array})""".format(gene_array=GENE_ARRAY,
                            gene_schema=GENE_SCHEMA,
                            gene_index_array=GENE_INDEX_ARRAY,
                            dbnsfp_array=DBNSFP_ARRAY,
                            canonical_array=CANONICAL_ARRAY,
                            omim_array=OMIM_ARRAY)

TRANSCRIPT_ARRAY = 'transcript'
TRANSCRIPT_SCHEMA = """
  <strand: string>
  [gene_idx       = 0:*:0:20;
   transcript_idx = 0:*:0:20;
   chrom          = 1:25:0:1;
   start          = 0:*:0:10000000;
   stop           = 0:*:0:10000000;
   synthetic      = 0:199:0:200]"""

TRANSCRIPT_STORE_QUERY = """
  store(
    redimension(
      index_lookup(
        index_lookup(
          apply(
            aio_input('{{path}}', 'num_attributes=9'),
            g_id,   rsub(a8, 's/.*gene_id "([^.]*).*/$1/'),
            t_id,   rsub(a8, 's/.*transcript_id "([^.]*).*/$1/'),
            chrom,  iif(substr(a0, 3, 4) = 'X',
                        23,
                        iif(substr(a0, 3, 4) = 'Y',
                            24,
                            iif(substr(a0, 3, 4) = 'M',
                                25,
                                int64(substr(a0, 3, 5))))),
            start,  int64(a3) + 1,
            stop,   int64(a4) + 1,
            strand, a6),
          {gene_index_array},
          g_id,
          gene_idx),
        {transcript_index_array},
        t_id,
        transcript_idx),
      {transcript_schema}),
    {transcript_array})""".format(
        transcript_array=TRANSCRIPT_ARRAY,
        transcript_schema=TRANSCRIPT_SCHEMA,
        gene_index_array=GENE_INDEX_ARRAY,
        transcript_index_array=TRANSCRIPT_INDEX_ARRAY)

EXON_ARRAY = 'exon'
EXON_SCHEMA = """
  <feature_type: string>
  [gene_idx       = 0:*:0:20;
   transcript_idx = 0:*:0:20;
   chrom          = 1:25:0:1;
   start          = 0:*:0:10000000;
   stop           = 0:*:0:10000000;
   synthetic      = 0:199:0:200]"""

EXON_STORE_QUERY = """
  store(
    redimension(
      index_lookup(
        index_lookup(
          apply(
            aio_input('{{path}}', 'num_attributes=9'),
            g_id,         rsub(a8, 's/.*gene_id "([^.]*).*/$1/'),
            t_id,         rsub(a8, 's/.*transcript_id "([^.]*).*/$1/'),
            chrom,        iif(substr(a0, 3, 4) = 'X',
                              23,
                              iif(substr(a0, 3, 4) = 'Y',
                                  24,
                                  iif(substr(a0, 3, 4) = 'M',
                                      25,
                                      dcast(substr(a0, 3, 5), int64(null))))),
            start,        int64(a3) + 1,
            stop,         int64(a4) + 1,
            feature_type, a2),
          {gene_index_array},
          g_id,
          gene_idx),
        {transcript_index_array},
        t_id,
        transcript_idx),
      {exon_schema}),
    {exon_array})""".format(
        exon_array=EXON_ARRAY,
        exon_schema=EXON_SCHEMA,
        gene_index_array=GENE_INDEX_ARRAY,
        transcript_index_array=TRANSCRIPT_INDEX_ARRAY)


# -- -
# -- - Load: VARIANT - --
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
   minicd:       string,
   minpval:      double,
   minor:        double,
   minl10pval:   double,
   csq:          string>
  [chrom = 1:25:0:1;
   pos   = 0:*:0:10000000]"""

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
        minicd,       rsub(a7, 's/.*minicd=([^;]*).*/$1/'),
        minpval,      dcast(rsub(a7, 's/.*minpval=([^;]*).*/$1/'),
                            double(null)),
        minor,        dcast(rsub(a7, 's/.*minor=([^;]*).*/$1/'),
                            double(null)),
        minl10pval,   dcast(rsub(a7, 's/.*minl10pval=([^;]*).*/$1/'),
                            double(null)),
        csq,          rsub(a7, 's/.*CSQ=([^;]*).*/$1/')),
      {variant_array_schema}),
    {variant_array})""".format(variant_array=VARIANT_ARRAY,
                               variant_array_schema=VARIANT_SCHEMA)

VARIANT_GENE_ARRAY = 'variant_gene'
VARIANT_GENE_SCHEMA = """
  <noval: int8 not null>
  [chrom    = 1:25:0:1;
   pos      = 0:*:0:10000000;
   gene_idx = 0:*:0:20]"""

VARIANT_GENE_STORE_QUERY = """
  store(
    redimension(
      index_lookup(
        apply(
          aio_input('{{path}}', 'num_attributes=3'),
          chrom,   int64(a0),
          pos,     int64(a1),
          noval,   int8(0)),
        {gene_index_array},
        a2,
        gene_idx),
      {variant_gene_schema}),
    {variant_gene_array})""".format(
        gene_index_array=GENE_INDEX_ARRAY,
        variant_gene_array=VARIANT_GENE_ARRAY,
        variant_gene_schema=VARIANT_GENE_SCHEMA)

VARIANT_TRANSCRIPT_ARRAY = 'variant_transcript'
VARIANT_TRANSCRIPT_SCHEMA = """
  <noval: int8 not null>
  [chrom          = 1:25:0:1;
   pos            = 0:*:0:10000000;
   transcript_idx = 0:*:0:20]"""

VARIANT_TRANSCRIPT_STORE_QUERY = """
  store(
    redimension(
      index_lookup(
        apply(
          aio_input('{{path}}', 'num_attributes=3'),
          chrom,         int64(a0),
          pos,           int64(a1),
          transcript_id, a2,
          noval,         int8(0)) as INPUT,
        {transcript_index_array},
        INPUT.transcript_id,
        transcript_idx),
      {variant_transcript_schema}),
    {variant_transcript_array})""".format(
        transcript_index_array=TRANSCRIPT_INDEX_ARRAY,
        variant_transcript_array=VARIANT_TRANSCRIPT_ARRAY,
        variant_transcript_schema=VARIANT_TRANSCRIPT_SCHEMA)


# -- -
# -- - Load: COVERAGE - --
# -- -
COVERAGE_FILE = os.path.join(
    GBE_DATA_PATH, 'coverage', 'Panel2016.all.coverage.txt.gz')

COVERAGE_ARRAY = 'coverage'
COVERAGE_SCHEMA = """
  <odds_ratio:  double,
   log10pvalue: double,
   flag:        string,
   category:    string>
  [chrom = 1:25:0:1;
   pos   = 0:*:0:10000000]"""

COVERAGE_STORE_QUERY = """
  store(
    redimension(
      apply(
        filter(
          aio_input('{{path}}', 'num_attributes=8'),
          substr(a0, 0, 1) <> '#'),
        chrom,       int64(a0),
        pos,         int64(a1),
        odds_ratio,  dcast(a2, double(null)),
        log10pvalue, dcast(a5, double(null)),
        flag,        a6,
        category,    iif(a7 = 'transcript_ablation' or
                         a7 = 'splice_acceptor_variant' or
                         a7 = 'splice_donor_variant' or
                         a7 = 'stop_gained' or
                         a7 = 'frameshift_variant',
                         'lof_variant',
                         iif(a7 = 'stop_lost' or
                             a7 = 'start_lost' or
                             a7 = 'initiator_codon_variant' or
                             a7 = 'transcript_amplification' or
                             a7 = 'inframe_insertion' or
                             a7 = 'inframe_deletion' or
                             a7 = 'missense_variant',
                           'missense_variant',
                           iif(a7 = 'protein_altering_variant' or
                               a7 = 'splice_region_variant' or
                               a7 = 'incomplete_terminal_codon_variant' or
                               a7 = 'stop_retained_variant' or
                               a7 = 'synonymous_variant',
                             'synonymous_variant',
                             a7)))),
      {coverage_array_schema}),
    {coverage_array})""".format(coverage_array=COVERAGE_ARRAY,
                                coverage_array_schema=COVERAGE_SCHEMA)


# == =
# == = LOOKUP = ==
# == =

LOOKUP_QUERY = """
  cross_join(
    {main_array},
    filter({index_array}, {id_attr} = '{id_val}'),
    {main_array}.{idx_attr},
    {index_array}.{idx_attr})"""

# -- -
# -- - Lookup: ICD - --
# -- -
ICD_LOOKUP_QUERY = """
  cross_join(
    {icd_array},
    filter({icd_info_array}, icd = '{{icd}}'),
    {icd_array}.icd_idx,
    {icd_info_array}.icd_idx)""".format(
        icd_array=ICD_ARRAY,
        icd_info_array=ICD_INFO_ARRAY)

ICD_PVALUE_LOOKUP_QUERY = """
  filter(
    cross_join(
      {icd_array},
      filter({icd_info_array}, icd = '{{icd}}'),
      {icd_array}.icd_idx,
      {icd_info_array}.icd_idx),
    pvalue < {{pvalue}})""".format(
        icd_array=ICD_ARRAY,
        icd_info_array=ICD_INFO_ARRAY)

ICD_CHROM_POS_LOOKUP_QUERY = """
  cross_join(
    between({icd_array}, null, {{chrom}}, {{pos}}, null, null,
                         null, {{chrom}}, {{pos}}, null, null),
    {icd_info_array},
    {icd_array}.icd_idx,
    {icd_info_array}.icd_idx)""".format(
        icd_array=ICD_ARRAY,
        icd_info_array=ICD_INFO_ARRAY)

ICD_X_INFO_SCHEMA = scidbpy.schema.Schema.fromstring(
    ICD_SCHEMA.replace(
        '>',
        ',{}>'.format(ICD_INFO_SCHEMA[ICD_INFO_SCHEMA.index('<') + 1:
                                      ICD_INFO_SCHEMA.index('>')])))

ICD_VARIANT_LOOKUP_QUERY = """
  cross_join(
    project({variant_array},
            rsid,
            ref,
            alt,
            filter,
            exac_nfe,
            csq),
    cross_join(
        project(
          between({icd_array}, null, null, null, {{pdecimal}}, null,
                               null, null, null, null,         null),
          or_val,
          pvalue,
          log10pvalue),
        filter({icd_info_array}, icd = '{{icd}}'),
        {icd_array}.icd_idx,
        {icd_info_array}.icd_idx) as icd_join,
    {variant_array}.chrom,
    icd_join.chrom,
    {variant_array}.pos,
    icd_join.pos)""".format(
        icd_array=ICD_ARRAY,
        icd_info_array=ICD_INFO_ARRAY,
        variant_array=VARIANT_ARRAY)

VARIANT_X_ICD_X_INFO_SCHEMA = scidbpy.schema.Schema.fromstring("""
  <rsid:        int64,
   ref:         string,
   alt:         string,
   filter:      string,
   exac_nfe:    double,
   csq:         string,
   or_val:      double,
   pvalue:      double,
   log10pvalue: double,
   icd:         string,
   Case:        int64,
   Name:        string>
  [chrom     = 1:25:0:1;
   pos       = 0:*:0:10000000;
   icd_idx   = 0:*:0:20;
   pdecimal  = 0:3:0:1;
   synthetic = 0:999:0:1000]""")


# -- -
# -- - Lookup: GENE - --
# -- -

GENE_LOOKUP_SCHEMA = scidbpy.schema.Schema.fromstring(
    GENE_SCHEMA.replace(
        '>',
        ',{}>'.format(GENE_INDEX_SCHEMA[GENE_INDEX_SCHEMA.index('<') + 1:
                                        GENE_INDEX_SCHEMA.index('>')])))

TRANSCRIPT_LOOKUP_SCHEMA = scidbpy.schema.Schema.fromstring(
    TRANSCRIPT_SCHEMA.replace(
        '>',
        ',{}>'.format(
            TRANSCRIPT_INDEX_SCHEMA[TRANSCRIPT_INDEX_SCHEMA.index('<') + 1:
                                    TRANSCRIPT_INDEX_SCHEMA.index('>')])))

TRANSCRIPT_GENE_LOOKUP_SCHEMA = scidbpy.schema.Schema.fromstring(
    TRANSCRIPT_SCHEMA.replace(
        '>',
        ',{}>'.format(GENE_INDEX_SCHEMA[GENE_INDEX_SCHEMA.index('<') + 1:
                                        GENE_INDEX_SCHEMA.index('>')])))

EXON_TRANSCRIPT_LOOKUP_SCHEMA = scidbpy.schema.Schema.fromstring(
    EXON_SCHEMA.replace(
        '>',
        ',{}>'.format(
            TRANSCRIPT_INDEX_SCHEMA[TRANSCRIPT_INDEX_SCHEMA.index('<') + 1:
                                    TRANSCRIPT_INDEX_SCHEMA.index('>')])))


# -- -
# -- - Lookup: VARIANT - --
# -- -
VARIANT_LOOKUP_QUERY = """
  between({variant_array}, {{chrom}}, {{pos}},
                     {{chrom}}, {{pos}})""".format(
    variant_array=VARIANT_ARRAY)

VARIANT_MULTI_LOOKUP_QUERY = """
  filter({variant_array}, {{chrom_pos_cond}})""".format(
    variant_array=VARIANT_ARRAY)

VARIANT_LOOKUP_SCHEMA = scidbpy.schema.Schema.fromstring(VARIANT_SCHEMA)

VARIANT_GENE_LOOKUP = """
  cross_join(
    {variant_array},
    cross_join(
      {variant_gene_array},
      filter({gene_index_array}, gene_id = '{{gene_id}}'),
      {variant_gene_array}.gene_idx,
      {gene_index_array}.gene_idx) as variant_gene_index,
    {variant_array}.chrom,
    variant_gene_index.chrom,
    {variant_array}.pos,
    variant_gene_index.pos)""".format(
        variant_array=VARIANT_ARRAY,
        variant_gene_array=VARIANT_GENE_ARRAY,
        gene_index_array=GENE_INDEX_ARRAY)

VARIANT_TRANSCRIPT_LOOKUP = """
  cross_join(
    {variant_array},
    cross_join(
      {variant_transcript_array},
      filter({transcript_index_array}, transcript_id = '{{transcript_id}}'),
      {variant_transcript_array}.transcript_idx,
      {transcript_index_array}.transcript_idx) as variant_transcript_index,
    {variant_array}.chrom,
    variant_transcript_index.chrom,
    {variant_array}.pos,
    variant_transcript_index.pos)""".format(
        variant_array=VARIANT_ARRAY,
        variant_transcript_array=VARIANT_TRANSCRIPT_ARRAY,
        transcript_index_array=TRANSCRIPT_INDEX_ARRAY)

VARIANT_X_GENE_INDEX_SCHEMA = scidbpy.schema.Schema.fromstring(
    VARIANT_GENE_SCHEMA.replace(
        '<',
        '<{},'.format(
            VARIANT_SCHEMA[VARIANT_SCHEMA.index('<') + 1:
                           VARIANT_SCHEMA.index('>')]).replace(
                               '>',
                               ',{}>'.format(
                                   GENE_INDEX_SCHEMA[
                                       GENE_INDEX_SCHEMA.index('<') + 1:
                                       GENE_INDEX_SCHEMA.index('>')]))))

VARIANT_X_TRANSCRIPT_INDEX_SCHEMA = scidbpy.schema.Schema.fromstring(
    VARIANT_TRANSCRIPT_SCHEMA.replace(
        '<',
        '<{},'.format(
            VARIANT_SCHEMA[VARIANT_SCHEMA.index('<') + 1:
                           VARIANT_SCHEMA.index('>')]).replace(
                               '>',
                               ',{}>'.format(
                                   TRANSCRIPT_INDEX_SCHEMA[
                                       TRANSCRIPT_INDEX_SCHEMA.index('<') + 1:
                                       TRANSCRIPT_INDEX_SCHEMA.index('>')]))))

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
# -- - Lookup: COVERAGE - --
# -- -
COVERAGE_LOOKUP_QUERY = """
  between({coverage_array}, {{chrom_start}}, {{pos_start}},
                            {{chrom_stop}},  {{pos_stop}})""".format(
                                coverage_array=COVERAGE_ARRAY)
