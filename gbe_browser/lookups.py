import itertools
import re
import scidbpy

import config
import utils


UNSUPPORTED_QUERIES = set((
    'CMD1G',
    'CMH9',
    'CMPD4',
    'ENSG00000155657',
    'ENST00000342175',
    'ENST00000342992',
    'ENST00000359218',
    'ENST00000460472',
    'ENST00000589042',
    'ENST00000591111',
    'FLJ32040',
    'LGMD2J',
    'MYLK5',
    'TMD',
    'TTN',
))

XOFF = int(1e9)
RSID_FORMAT = '{chrom}-{pos}-{ref}-{alt}'

# 1:1-1000
REGION_RE1 = re.compile(r'^(\d+|X|Y|M|MT)\s*:\s*(\d+)-(\d+)$')
REGION_RE2 = re.compile(r'^(\d+|X|Y|M|MT)\s*:\s*(\d+)$')
REGION_RE3 = re.compile(r'^(\d+|X|Y|M|MT)$')
REGION_RE4 = re.compile(r'^(\d+|X|Y|M|MT)\s*[-:]\s*(\d+)-([ATCG]+)-([ATCG]+)$')


def numpy2dict(ar):
    """Convert SciDB NumPy array result to Python dictionary and populate
    nullable attributes with values (discards null codes).

    """
    return [
        dict(
            (de[0],
             el[de[0]]['val'] if isinstance(de[1], list) else el[de[0]])
            for de in ar.dtype.descr if de[0] != 'notused'
        )
        for el in ar]


def format_variants(variants, add_ann=False, gene_id=None, transcript_id=None):
    for variant in variants:
        variant['rsid'] = ('rs{}'.format(variant['rsid'])
                           if variant['rsid'] else '.')
        variant['variant_id'] = RSID_FORMAT.format(
            chrom=variant['chrom'],
            pos=variant['pos'],
            ref=variant['ref'],
            alt=variant['alt'])

        anns = [dict(zip(config.VARIANT_CSQ, csq.split('|')))
                for csq in variant['csq'].split(',')]
        vep_annotations = [
            ann for ann in anns
            if ('Feature' in ann and
                ann['Feature'].startswith('ENST') and
                (gene_id is None or ann['Gene'] == gene_id) and
                (transcript_id is None or ann['Feature'] == transcript_id))]
        if add_ann:
            variant['vep_annotations'] = vep_annotations

        variant['genes'] = list(set(ann['Gene'] for ann in vep_annotations))
        variant['gene_name'] = ','.join(variant['genes'][:3])
        variant['gene_symbol'] = ','.join(
            itertools.islice(set(ann['SYMBOL'] for ann in vep_annotations), 3))
        variant['transcripts'] = list(set(
            ann['Feature'] for ann in vep_annotations))

        utils.add_consequence_to_variant(variant, vep_annotations)

    return variants


def format_genes(genes):
    for gene in genes:
        gene['xstart'] = gene['chrom'] * XOFF + gene['start']
        gene['xstop'] = gene['chrom'] * XOFF + gene['stop']
    return genes


def exists(db, array_name, attr_name, attr_val):
    """
    Search bar

    MongoDB:
      db.genes.find({'gene_id': 'ENSG00000107404'}, fields={'_id': False})

    SciDB:
      aggregate(
        filter(gene_index, gene_id = 'ENSG00000198734'),
        count(*));
    """
    return bool(
        db.iquery(
            config.EXISTS_QUERY.format(
                array_name=array_name,
                attr_name=attr_name,
                attr_val=attr_val),
            schema=config.EXISTS_SCHEMA,
            fetch=True,
            atts_only=True)[0]['count']['val'])


# -- -
# -- - ICD - --
# -- -
def get_icd_name_map(db):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/coding/RH117

    MongoDB:
      db.icd_info.find({'icd': 'RH117'}, fields={'_id': False})

    SciDB:
      project(icd_info, icd, Name);
    """
    return dict((i['icd']['val'], '&nbsp;'.join(i['Name']['val'].split()))
                for i in db.iquery(config.ICD_INFO_MAP_QUERY,
                                   schema=config.ICD_INFO_MAP_SCHEMA,
                                   fetch=True,
                                   atts_only=True))


def exists_icd(db, icd):
    """
    Search bar

    MongoDB:
      db.icd_info.find({'icd': 'RH141'}, fields={'_id': False})

    SciDB:
      aggregate(
        filter(icd_info, icd = 'RH141'),
        count(*));
    """
    return exists(db, config.ICD_INFO_ARRAY, 'icd', "'{}'".format(icd))


def get_icd_significant(db, icd_id, cutoff=0.01):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/coding/RH117

    MongoDB:
      db.icd.find({'icd': 'RH117', 'stats.pvalue': {'$lt': 0.01}},
                  fields={'_id': false})

    SciDB:
      filter(
        cross_join(icd,
                   filter(icd_index, icd = 'RH117'),
                   icd.icd_idx,
                   icd_index.icd_idx),
        pvalue < 0.01);
    """
    return numpy2dict(
        db.iquery(
            config.ICD_PVALUE_LOOKUP_QUERY.format(
                icd=icd_id, pvalue=cutoff),
            schema=config.ICD_X_INFO_SCHEMA,
            fetch=True))


def get_variant_icd(db, chrom, pos):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/variant/1-39381448

    MongoDB:
      db.icd.find({'xpos': '1039381448'}, fields={'_id': False})

    SciDB:
      equi_join(
        between(icd, null, 1, 39381448, null,
                     null, 1, 39381448, null),
        icd_info,
        'left_names=icd_idx',
        'right_names=icd_idx',
        'keep_dimensions=1',
        'algorithm=hash_replicate_right');
    """
    return numpy2dict(
        db.iquery(
            config.ICD_CHROM_POS_LOOKUP_QUERY.format(chrom=chrom, pos=pos),
            schema=config.ICD_CHROM_POS_LOOKUP_SCHEMA,
            fetch=True,
            atts_only=True))


def get_icd_significant_variant(db, icd_id, cutoff=0.001):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/coding/RH117

    MongoDB:
      db.icd.find({'icd': 'RH117', 'stats.pvalue': {'$lt': 0.01}},
                  fields={'_id': false})
      db.icd_info.find({'icd': 'RH117'}, fields={'_id': False})
      db.variants.find({'xpos': '1039381448'}, fields={'_id': False})

    SciDB:
      equi_join(
        project(variant,
                rsid,
                ref,
                alt,
                filter,
                exac_nfe,
                csq),
        cross_join(
            project(
              between(icd, null, null, null, 1,    null,
                           null, null, null, null, null),
              or_val,
              pvalue,
              log10pvalue),
            filter(icd_info, icd = 'RH117'),
            icd.icd_idx,
            icd_info.icd_idx) as icd_join,
        'left_names=chrom,pos',
        'right_names=chrom,pos',
        'keep_dimensions=1',
        'algorithm=merge_right_first');
    """
    pdecimal = config.ICD_PVALUE_MAP.get(cutoff, 0)
    return format_variants(
        numpy2dict(
            db.iquery(
                config.ICD_VARIANT_LOOKUP_QUERY.format(
                    icd=icd_id, pdecimal=pdecimal),
                schema=config.VARIANT_X_ICD_X_INFO_SCHEMA,
                fetch=True,
                atts_only=True)))


# -- -
# -- - GENE - --
# -- -
def get_gene(db, gene_id):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/gene/ENSG00000107404

    MongoDB:
      db.genes.find({'gene_id': 'ENSG00000107404'}, fields={'_id': False})

    SciDB:
      cross_join(gene,
                 filter(gene_index, gene_id = 'ENSG00000107404'),
                 gene.gene_idx,
                 gene_index.gene_idx);
    """
    return numpy2dict(
        db.iquery(
            config.LOOKUP_QUERY.format(main_array=config.GENE_ARRAY,
                                       index_array=config.GENE_INDEX_ARRAY,
                                       id_attr='gene_id',
                                       id_val=gene_id,
                                       idx_attr='gene_idx'),
            schema=config.GENE_LOOKUP_SCHEMA,
            fetch=True))[0]


def exists_gene_id(db, gene_id):
    """
    Search bar

    MongoDB:
      db.genes.find({'gene_id': 'ENSG00000107404'}, fields={'_id': False})

    SciDB:
      aggregate(
        filter(gene_index, gene_id = 'ENSG00000198734'),
        count(*));
    """
    return exists(db,
                  config.GENE_INDEX_ARRAY,
                  'gene_id',
                  "'{}'".format(gene_id))


def get_genes_in_region(db, chrom, start, stop):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/region/16-50727514-50766988

    MongoDB:
      db.genes.find({'xstart': {'$lte': 1650766988},
                     'xstop' : {'$gte': 1650727514}}, fields={'_id': False})

    SciDB:
      cross_join(between(gene, null, 16, null,     50727514,
                               null, 16, 50766988, null),
                 gene_index,
                 gene.gene_idx,
                 gene_index.gene_idx);
    """
    return numpy2dict(
        db.iquery(
            config.GENE_BETWEEN_QUERY.format(
                chrom=chrom, start=start, stop=stop),
            schema=config.GENE_LOOKUP_SCHEMA,
            fetch=True))


def get_gene_id_by_name(db, gene_name):
    """
    Search bar

    MondoDB:
      db.genes.find_one({'gene_name': 'F5'},   fields={'_id': False})
      db.genes.find_one({'other_names': 'F5'}, fields={'_id': False})

    SciDB:
      project(
        cross_join(
          gene_index,
          filter(gene, gene_name = 'F5'),
          gene_index.gene_idx,
          gene.gene_idx),
        gene_id);
    """
    # TODO other_names
    res = db.iquery(
        config.GENE_ID_BY_NAME_QUERY.format(gene_name=gene_name),
        schema=config.GENE_ID_BY_NAME_SCHEMA,
        fetch=True,
        atts_only=True)
    if not res:
        return None
    return res[0]['gene_id']['val']


def get_transcript(db, transcript_id, gene_id=None):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/gene/ENSG00000107404

    MongoDB:
      db.transcripts.find({'transcript_id': 'ENST00000378891'},
                          fields={'_id': False})

    SciDB:
      cross_join(transcript,
                 filter(transcript_index, transcript_id = 'ENST00000378891'),
                 transcript.transcript_idx,
                 transcript_index.transcript_idx);
    """
    res = format_genes(numpy2dict(
            db.iquery(
                config.LOOKUP_QUERY.format(
                    main_array=config.TRANSCRIPT_ARRAY,
                    index_array=config.TRANSCRIPT_INDEX_ARRAY,
                    id_attr='transcript_id',
                    id_val=transcript_id,
                    idx_attr='transcript_idx'),
                schema=config.TRANSCRIPT_LOOKUP_SCHEMA,
                fetch=True)[:1]))[0]
    res['exons'] = get_exons_in_transcript(db, transcript_id)
    if gene_id is None:
        res['gene_id'] = db.iquery(
            config.GENE_INDEX_LOOKUP_QUERY.format(gene_idx=res['gene_idx']),
            fetch=True,
            atts_only=True,
            schema=config.GENE_INDEX_SCHEMA)[0]['gene_id']['val']
    else:
        res['gene_id'] = gene_id
    return res


def exists_transcript_id(db, transcript_id):
    """
    Search bar

    MongoDB:
      db.transcripts.find({'transcript_id': 'ENST00000450546'},
                          fields={'_id': False})

    SciDB:
      aggregate(
        filter(transcript_index, transcript_id = 'ENST00000450546'),
        count(*));
    """
    return exists(db,
                  config.TRANSCRIPT_INDEX_ARRAY,
                  'transcript_id',
                  "'{}'".format(transcript_id))


def get_transcripts_in_gene(db, gene_id):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/gene/ENSG00000107404

    MongoDB:
      db.transcripts.find({'gene_id': 'ENSG00000107404'},
                          fields={'_id': False})

    SciDB:
      cross_join(transcript,
                 filter(gene_index, gene_id = 'ENSG00000107404'),
                 transcript.gene_idx,
                 gene_index.gene_idx);
    """
    return numpy2dict(
        db.iquery(
            config.LOOKUP_QUERY.format(main_array=config.TRANSCRIPT_ARRAY,
                                       index_array=config.GENE_INDEX_ARRAY,
                                       id_attr='gene_id',
                                       id_val=gene_id,
                                       idx_attr='gene_idx'),
            schema=config.TRANSCRIPT_GENE_LOOKUP_SCHEMA,
            fetch=True))


def get_exons_in_transcript(db, transcript_id):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/gene/ENSG00000107404

    MongoDB:
      db.exons.find({'transcript_id': transcript_id,
                     'feature_type': { "$in": ['CDS', 'UTR', 'exon'] }},
                    fields={'_id': False})

    SciDB:
      cross_join(exon,
                 filter(transcript_index, transcript_id = 'ENST00000378891'),
                 exon.transcript_idx,
                 transcript_index.transcript_idx);
    """
    return numpy2dict(
        db.iquery(
            config.LOOKUP_QUERY.format(
                main_array=config.EXON_ARRAY,
                index_array=config.TRANSCRIPT_INDEX_ARRAY,
                id_attr='transcript_id',
                id_val=transcript_id,
                idx_attr='transcript_idx'),
            schema=config.EXON_TRANSCRIPT_LOOKUP_SCHEMA,
            fetch=True))


# -- -
# -- - VARIANT - --
# -- -
def get_variants_by_id(db, variant_ids):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/coding/RH117

    MongoDB:
      db.variants.find({'xpos': '1039381448'}, fields={'_id': False})

    SciDB:
      filter(variant, chrom = 1 and pos = 39381448); -- or chrom = ...
    """
    chrom_pos_cond = ' or '.join(
        'chrom = {chrom} and pos = {pos}'.format(
            chrom=int(xpos / XOFF), pos=int(xpos % XOFF))
        for xpos in variant_ids)
    variants = numpy2dict(
        db.iquery(
            config.VARIANT_MULTI_LOOKUP_QUERY.format(
                chrom_pos_cond=chrom_pos_cond),
            schema=config.VARIANT_LOOKUP_SCHEMA,
            fetch=True))
    variants = format_variants(variants)
    return variants


def get_variants_chrom_pos_by_rsid_limit2(db, rsid):
    """
    Search bar

    MongoDB:
      db.variants.find({'rsid': 'rs6025'}, fields={'_id': False}))

    SciDB:
      limit(
        project(
          filter(variant, rsid = 6025),
          rsid),
        2);
    """
    if not rsid.startswith('rs'):
        return None
    rsid_int = None
    try:
        rsid_int = int(rsid.lstrip('rs'))
    except Exception:
        return None

    res = db.iquery(
        config.VARIANT_CHROM_POS_BY_RSID_QUERY.format(rsid=rsid_int),
        schema=config.VARIANT_CHROM_POS_BY_RSID_SCHEMA,
        fetch=True)
    if not res:
        return None

    return res


def get_variants_chrom_pos(db, chrom, start, stop=None):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/variant/1-39381448

    MongoDB:
      db.variants.find({'xpos': '1039381448'}, fields={'_id': False})

    SciDB:
      between(vairant, 1, 39381448,
                       1, 39381448);
    """
    if stop is None:
        stop = start
    return format_variants(
        numpy2dict(
            db.iquery(
                config.VARIANT_LOOKUP_QUERY.format(
                    chrom=chrom, start=start, stop=stop),
                schema=config.VARIANT_LOOKUP_SCHEMA,
                fetch=True)),
        add_ann=True)


def get_variant_ann_by_chrom_pos(db, chrom, start):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/variant/1-39381448

    MongoDB:
      db.variants.find({'xpos': '1039381448'}, fields={'_id': False})

    SciDB:
      between(vairant, 1, 39381448,
                       1, 39381448);
    """
    variants = format_variants(
        numpy2dict(
            db.iquery(
                config.VARIANT_LIMIT_QUERY.format(chrom=chrom, start=start),
                schema=config.VARIANT_LIMIT_SCHEMA,
                fetch=True)),
        add_ann=True)
    variant = variants[0] if len(variants) else None
    if variant is None or 'rsid' not in variant:
        return variant
    if variant['rsid'] == '.' or variant['rsid'] is None:
        raise NotImplementedError()  # TODO
        # rsid = db.dbsnp.find_one({'xpos': xpos})
        # if rsid:
        #     variant['rsid'] = 'rs%s' % rsid['rsid']
    return variant


def get_variants_in_gene(db, gene_id):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/gene/ENSG00000107404

    MongoDB:
      db.variants.find({'genes': 'ENSG00000107404'}, fields={'_id': False})

    SciDB:
      cross_join(variant,
                 cross_join(variant_gene,
                            filter(gene_index, gene_id = 'ENSG00000107404'),
                            variant_gene.gene_idx,
                            gene_index.gene_idx) as variant_gene_index,
                 variant.chrom,
                 variant_gene_index.chrom,
                 variant.pos,
                 variant_gene_index.pos);
    """
    return format_variants(
        numpy2dict(
            db.iquery(
                config.VARIANT_GENE_LOOKUP.format(gene_id=gene_id),
                schema=config.VARIANT_X_GENE_INDEX_SCHEMA,
                fetch=True)),
        gene_id=gene_id)


def get_variants_in_transcript(db, transcript_id):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/gene/ENSG00000107404

    MongoDB:
      db.variants.find({'transcripts': 'ENST00000378891'},
                       fields={'_id': False})

    SciDB:
      cross_join(
        variant,
        cross_join(
          variant_transcript,
          filter(transcript_index, transcript_id = 'ENST00000378891'),
          variant_transcript.transcript_idx,
          transcript_index.transcript_idx) as variant_transcript_index,
        variant.chrom,
        variant_transcript_index.chrom,
        variant.pos,
        variant_transcript_index.pos);
    """
    return format_variants(
        numpy2dict(
            db.iquery(
                config.VARIANT_TRANSCRIPT_LOOKUP.format(
                    transcript_id=transcript_id),
                schema=config.VARIANT_X_TRANSCRIPT_X_INDEX_SCHEMA,
                fetch=True)),
        transcript_id=transcript_id)


def get_variants_by_transcript_idx(db, transcript_id, transcript_idx):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/gene/ENSG00000107404

    MongoDB:
      db.variants.find({'transcripts': 'ENST00000378891'},
                       fields={'_id': False})

    SciDB:
      cross_join(
        variant,
        between(variant_transcript, null, null, 3694,
                                    null, null, 3694),
        variant.chrom,
        variant_transcript.chrom,
        variant.pos,
        variant_transcript.pos);
    """
    return format_variants(
        numpy2dict(
            db.iquery(
                config.VARIANT_TRANSCRIPT_IDX_LOOKUP.format(
                    transcript_idx=transcript_idx),
                schema=config.VARIANT_X_TRANSCRIPT_SCHEMA,
                fetch=True)),
        transcript_id=transcript_id)


def get_variants_in_region(db, chrom, start, stop):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/region/16-50727514-50766988

    MongoDB:
      db.variants.find({'xpos': {'$lte': 1650766988},
                                 '$gte': 1650727514}}, fields={'_id': False})

    SciDB:
      between(variant, 16, 50727514,
                       16, 50766988);
    """
    # TODO add SEARCH_LIMIT
    return get_variants_chrom_pos(db, chrom, start, stop)


# -- -
# -- - COVERAGE - --
# -- -
def get_coverage_for_transcript(db, xstart, xstop=None):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/gene/ENSG00000107404

    MongoDB:
      db.base_coverage.find({'xpos': {'$gte': xstart, '$lte': xstop}},
                            fields={'_id': False})

    SciDB:
      between(coverage, 1, 1270607,
                        1, 1284543);

    """
    # TODO has_coverage filter
    return get_coverage_for_bases(db, xstart, xstop)


def get_coverage_for_bases(db, xstart, xstop=None):
    """
    e.g.,
    UI:
      https://biobankengine.stanford.edu/region/16-50727514-50766988

    MongoDB:
      db.base_coverage.find({'xpos': {'$gte': xstart, '$lte': xstop}},
                            fields={'_id': False})

    SciDB:
      between(coverage, 16, 50727514,
                        16,  50766988);
    """
    if xstop is None:
        xstop = xstart
    return numpy2dict(
        db.iquery(config.COVERAGE_LOOKUP_QUERY.format(
            chrom_start=int(xstart / XOFF), pos_start=int(xstart % XOFF),
            chrom_stop=int(xstop / XOFF), pos_stop=int(xstop % XOFF)),
                fetch=True))


# -- -
# -- - SEARCH BAR - --
# -- -
def get_awesomebar_suggestions(g, query):
    """This generates autocomplete suggestions when user query is the
    string that user types If it is the prefix for a gene, return list
    of gene names

    """
    regex = re.compile('^' + re.escape(query), re.IGNORECASE)
    results = [r for r in g.autocomplete_strings if regex.match(r)][:20]
    return results


def get_awesomebar_result(db, query):
    """Similar to the above, but this is after a user types enter We need to
    figure out what they meant - could be gene, variant, region, icd10

    Return tuple of (datatype, identifier)
    Where datatype is one of 'gene', 'variant', or 'region'
    And identifier is one of:
    - ensembl ID for gene
    - variant ID string for variant (eg. 1-1000-A-T)
    - region ID string for region (eg. 1-1000-2000)

    Follow these steps:
    - if query is an ensembl ID, return it
    - if a gene symbol, return that gene's ensembl ID
    - if an RSID, return that variant's string


    Finally, note that we don't return the whole object here - only
    it's identifier.  This could be important for performance later

    """
    query = query.strip()
    (query_lower, query_upper) = (query.lower(), query.upper())
    print 'Query: %s' % query

    if query_upper in UNSUPPORTED_QUERIES:
        return 'error', query

    # Variant
    variants = get_variants_chrom_pos_by_rsid_limit2(db, query_lower)
    if variants:
        if len(variants) == 1:
            variant = variants[0]
            variant_id = '{}-{}'.format(variant['chrom'], variant['pos'])
            return 'variant', variant_id
        else:
            return 'dbsnp_variant_set', query_lower

    # TODO
    # variant = get_variants_from_dbsnp(db, query.lower())
    # if variant:
    #     return 'variant', variant[0]['variant_id']

    gene_id = get_gene_id_by_name(db, query_upper)
    if gene_id:
        return 'gene', gene_id

    # Ensembl formatted queries
    if query_upper.startswith('ENS'):
        # Gene
        if exists_gene_id(db, query_upper):
            return 'gene', query_upper

        # Transcript
        if exists_transcript_id(db, query_upper):
            return 'transcript', query_upper

    # ICD10 formatted queries
    if query_upper.startswith('ICD'):
        # ICD10
        if exists_icd(db, query_upper):
            return 'icd10', query_upper

    # From here on out, only region queries
    if query_upper.startswith('CHR'):
        query_upper = query_upper.lstrip('CHR')

    # Region
    m = REGION_RE1.match(query_upper)
    if m:
        if int(m.group(3)) < int(m.group(2)):
            return 'region', 'invalid'
        return 'region', '{}-{}-{}'.format(m.group(1), m.group(2), m.group(3))
    m = REGION_RE2.match(query_upper)
    if m:
        return 'region', '{}-{}-{}'.format(m.group(1), m.group(2), m.group(2))
    m = REGION_RE3.match(query_upper)
    if m:
        return 'region', '{}'.format(m.group(1))
    m = REGION_RE4.match(query_upper)
    if m:
        return 'variant', '{}-{}-{}-{}'.format(
            m.group(1), m.group(2), m.group(3), m.group(4))

    return 'not_found', query


if __name__ == '__main__':
    db = scidbpy.connect()

    import pprint
    pp = pprint.PrettyPrinter(indent=2)
    pp.pprint(exists_gene_id(db, 'ENSG00000107404'))
    pp.pprint(exists_icd(db, 'RH117'))
    pp.pprint(exists_transcript_id(db, 'ENST00000378891'))
    pp.pprint(get_coverage_for_bases(db, 1039381448))
    pp.pprint(get_coverage_for_transcript(db, 1039381448))
    pp.pprint(get_exons_in_transcript(db, 'ENST00000378891'))
    pp.pprint(get_gene(db, 'ENSG00000107404'))
    pp.pprint(get_gene_id_by_name(db, 'F5'))
    pp.pprint(get_genes_in_region(db, 1, 39381448, 39382448))
    pp.pprint(get_icd_name_map(db))
    pp.pprint(get_icd_significant(db, 'RH117'))
    pp.pprint(get_icd_significant_variant(db, 'RH117'))
    pp.pprint(get_transcript(db, 'ENST00000378891'))
    pp.pprint(get_transcripts_in_gene(db, 'ENSG00000107404'))
    pp.pprint(get_variant_ann_by_chrom_pos(db, 1, 39381448))
    # pp.pprint(get_variant_chrom_pos(db, 19, 11210912)) # TODO
    pp.pprint(get_variant_icd(db, 1, 39381448))
    pp.pprint(get_variants_by_id(db, (1039381448,)))
    pp.pprint(get_variants_by_transcript_idx(db, 'ENST00000378891', 3694))
    pp.pprint(get_variants_chrom_pos_by_rsid_limit2(db, 'rs6025'))
    pp.pprint(get_variants_chrom_pos(db, 1, 39381448))
    pp.pprint(get_variants_in_gene(db, 'ENSG00000107404'))
    pp.pprint(get_variants_in_region(db, 1, 39381448, 39382448))
    pp.pprint(get_variants_in_transcript(db, 'ENST00000378891'))
