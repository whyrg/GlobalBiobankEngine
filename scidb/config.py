import os
import scidbpy


SCIDB_INSTANCE_NUM = 8
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


ICD_INDEX_ARRAY = 'icd_index'
ICD_INDEX_SCHEMA = '<icd:string>[icd_id]'

ICD_ARRAY = 'icd'
ICD_SCHEMA = """
  <icdind:      int64,
   xpos:        int64,
   affyid:      string,
   or_val:      double,
   se:          double,
   pvalue:      double,
   lor:         double,
   log10pvalue: double,
   l95or:       double,
   u95or:       double>
  [icd_id    = 0:*:0:20;
   chrom     = 1:25:0:1;
   pos       = 0:*:0:10000000;
   synthetic = 0:999:0:1000]"""

ICD_INFO_ARRAY = 'icd_info'
ICD_INFO_SCHEMA = '<case:int64, icd_name:string>[icd_id=0:*:0:1000000]'

ICD_LOAD_QUERY = """
  insert(
    redimension(
      apply(
        filter(
          index_lookup(
            aio_input(
              'paths={paths}',
              'instances={instances}',
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
        icd_id,      {icd_id_cond},
        chrom,       int64(a0),
        pos,         int64(a1),
        icdind,      int64(string(int64(a0) * 1e9 + int64(a1)) +
                           {icdind_cond}),
        xpos,        int64(a0) * int64(1e9) + int64(a1),
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
    {icd})"""

QT_LOAD_QUERY = """
  insert(
    redimension(
      apply(
        filter(
          index_lookup(
            aio_input(
              'paths={paths}',
              'instances={instances}',
              'num_attributes=12') as INPUT,
            {qc},
            INPUT.a2,
            is_in_filter),
          substr(a0, 0, 1) <> '#' and
          a5 = 'ADD' and
          is_in_filter is null and
          dcast(a8, double(null)) < .5 and
          a10 <> 'NA'),
        icd_id,      {icd_id_cond},
        chrom,       int64(a0),
        pos,         int64(a1),
        icdind,      int64(string(int64(a0) * 1e9 + int64(a1)) +
                           {icdind_cond}),
        xpos,        int64(a0) * int64(1e9) + int64(a1),
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
    {icd})"""

ICD_INFO_LOAD_QUERY = """
  insert(
    redimension(
      apply(
        index_lookup(
          aio_input('{path}', 'num_attributes=6'),
          {icd_index},
          a0,
          icd_id),
        case,     dcast(a1, int64(null)),
        icd_name, a2),
      {icd_info}, false),
    {icd_info})"""


ICD_LOOKUP_QUERY="""
  filter(
    cross_join(
      icd,
      filter(icd_index, icd = '{icd_id}'),
      icd.icd_id,
      icd_index.icd_id),
    pvalue < {cutoff})"""

ICD_LOOKUP_SCHEMA=scidbpy.schema.Schema.fromstring(
    ICD_SCHEMA.replace('>', ',icd:string>'))

ICD_INFO_LOOKUP_QUERY="""
  cross_join(
    icd_info,
    filter(icd_index, icd = '{icd_id}'),
    icd_info.icd_id,
    icd_index.icd_id)"""

ICD_INFO_LOOKUP_SCHEMA=scidbpy.schema.Schema.fromstring(
    ICD_INFO_SCHEMA.replace('>', ',icd:string>'))
