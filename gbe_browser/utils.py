from operator import itemgetter
import re
import itertools
vep_field_names = ['Allele', 'Consequence', 'IMPACT', 'SYMBOL', 'Gene', 'Feature_type', 'Feature', 'BIOTYPE', 'EXON', 'INTRON', 'HGVSc', 'HGVSp', 'cDNA_position', 'CDS_position', 'Protein_position', 'Amino_acids', 'Codons', 'Existing_variation',  'DISTANCE', 'ALLELE_NUM','STRAND', 'VARIANT_CLASS', 'MINIMISED', 'SYMBOL_SOURCE', 'HGNC_ID', 'CANONICAL', 'TSL', 'APPRIS', 'CCDS', 'ENSP', 'SWISSPROT', 'TREMBL', 'UNIPARC',  'SIFT2','SIFT', 'PolyPhen', 'DOMAINS', 'HGVS_OFFSET', 'GMAF', 'AFR_MAF', 'AMR_MAF', 'EAS_MAF', 'EUR_MAF', 'SAS_MAF', 'AA_MAF', 'EA_MAF', 'ExAC_MAF', 'ExAC_Adj_MAF', 'ExAC_AFR_MAF', 'ExAC_AMR_MAF', 'ExAC_EAS_MAF', 'ExAC_FIN_MAF', 'ExAC_NFE_MAF', 'ExAC_OTH_MAF', 'ExAC_SAS_MAF', 'CLIN_SIG', 'SOMATIC', 'PHENO', 'PUBMED', 'MOTIF_NAME', 'MOTIF_POS', 'HIGH_INF_POS', 'MOTIF_SCORE_CHANGE', 'LoF', 'LoF_filter', 'LoF_flags', 'LoF_info']
AF_BUCKETS = [0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1]
METRICS = [
    'BaseQRankSum',
    'ClippingRankSum',
    'DP',
    'FS',
    'InbreedingCoeff',
    'MQ',
    'MQRankSum',
    'QD',
    'ReadPosRankSum',
    'VQSLOD'
]

def return_gene_vep(vep_annotation):
    info_field = dict([(x.split('=', 1)) if '=' in x else (x, x) for x in re.split(';(?=\w)', vep_annotation)])
    consequence_array = info_field['CSQ'].split(',') if 'CSQ' in info_field else []
    annotations = [dict(zip(vep_field_names, x.split('|'))) for x in consequence_array]
    coding_annotations = [ann for ann in annotations if 'Feature' in ann and ann['Feature'].startswith('ENST')]
    vep_annotations = [ann for ann in coding_annotations]
    genes = list(set(ann['Gene'] for ann in vep_annotations))
    gene = ','.join(genes[:3])
    symbol = ','.join(
            itertools.islice(set(ann['SYMBOL'] for ann in vep_annotations), 3))
    HGVSp = ','.join(list({annotation['HGVSp'] for annotation in vep_annotations})).lstrip(',').split(',')[0]
    HGVSc = ','.join(list({annotation['HGVSc'] for annotation in vep_annotations})).lstrip(',').split(',')[0]
    return (gene, symbol, HGVSp, HGVSc)


def add_transcript_coordinate_to_variants(variant_list, transcript):
    """
    Each variant has a 'xpos' and 'pos' positional attributes.
    This method takes a list of variants and adds a third position: the "transcript coordinates".
    This is defined as the distance from the start of the transcript, in coding bases.
    So a variant in the 7th base of the 6th exon of a transcript will have a transcript coordinate of
    the sum of the size of the first 5 exons) + 7
    This is 0-based, so a variant in the first base of the first exon has a transcript coordinate of 0.

    You may want to add transcript coordinates for multiple transcripts, so this is stored in a variant as
    variant['transcript_coordinates'][transcript_id]

    If a variant in variant_list does not have a `transcript_coordinates` dictionary, we create one

    If a variant start position for some reason does not fall in any exons in this transcript, its coordinate is 0.
    This is perhaps logically inconsistent,
    but it allows you to spot errors quickly if there's a pileup at the first base.
    `None` would just break things.

    Consider the behavior if a 20 base deletion deletes parts of two exons.
    I think the behavior in this method is consistent, but beware that it might break things downstream.

    Edits variant_list in place; no return val
    """

    transcript_id = transcript['transcript_id']
    # make sure exons is sorted by (start, end)
    exons = sorted(transcript['exons'], key=itemgetter('start', 'stop'))

    # offset from start of base for exon in ith position (so first item in this list is always 0)
    exon_offsets = [0 for i in range(len(exons))]
    for i, exon in enumerate(exons):
        for j in range(i+1, len(exons)):
            exon_offsets[j] += exon['stop'] - exon['start']

    for variant in variant_list:
        if 'transcript_coordinates' not in variant:
            variant['transcript_coordinates'] = {}
        variant['transcript_coordinates'][transcript_id] = 0
        for i, exon in enumerate(exons):
            if exon['start'] <= variant['pos'] <= exon['stop']:
                variant['transcript_coordinates'][transcript_id] = exon_offsets[i] + variant['pos'] - exon['start']


def xpos_to_pos(xpos):
    return int(xpos % 1e9)


def add_consequence_to_variants(variant_list):
    for variant in variant_list:
        add_consequence_to_variant(variant, variant['vep_annotations'])


def add_consequence_to_variant(variant, vep_annotations):
    worst_csq = worst_csq_with_vep(vep_annotations)
    if worst_csq is None: return
    variant['major_consequence'] = worst_csq['major_consequence']
    variant['HGVSp'] = get_proper_hgvs(worst_csq)
    variant['HGVSc'] = worst_csq['HGVSc'].split(':')[-1]
    variant['CANONICAL'] = worst_csq['CANONICAL']
    if csq_order_dict[variant['major_consequence']] <= csq_order_dict["frameshift_variant"]:
        variant['category'] = 'lof_variant'
    elif csq_order_dict[variant['major_consequence']] <= csq_order_dict["missense_variant"]:
        # Should be noted that this grabs inframe deletion, etc.
        variant['category'] = 'missense_variant'
    elif csq_order_dict[variant['major_consequence']] <= csq_order_dict["synonymous_variant"]:
        variant['category'] = 'synonymous_variant'
    else:
        variant['category'] = 'other_variant'


def add_category_to_variant(worst_csq):
    if worst_csq is None: return 'other_variant'
    if csq_order_dict[worst_csq] <= csq_order_dict["frameshift_variant"]:
        category = 'lof_variant'
    elif csq_order_dict[worst_csq] <= csq_order_dict["missense_variant"]:
        # Should be noted that this grabs inframe deletion, etc.
        category = 'missense_variant'
    elif csq_order_dict[worst_csq] <= csq_order_dict["synonymous_variant"]:
        category = 'synonymous_variant'
    else:
        category = 'other_variant'
    return category


protein_letters_1to3 = {
    'A': 'Ala', 'C': 'Cys', 'D': 'Asp', 'E': 'Glu',
    'F': 'Phe', 'G': 'Gly', 'H': 'His', 'I': 'Ile',
    'K': 'Lys', 'L': 'Leu', 'M': 'Met', 'N': 'Asn',
    'P': 'Pro', 'Q': 'Gln', 'R': 'Arg', 'S': 'Ser',
    'T': 'Thr', 'V': 'Val', 'W': 'Trp', 'Y': 'Tyr',
    'X': 'Ter', '*': 'Ter'
}


def get_proper_hgvs(csq):
    """
    Takes consequence dictionary, returns proper variant formatting for synonymous variants
    """
    if '%3D' in csq['HGVSp']:
        try:
            amino_acids = ''.join([protein_letters_1to3[x] for x in csq['Amino_acids']])
            return "p." + amino_acids + csq['Protein_position'] + amino_acids
        except Exception, e:
            return "p.X0X"
            print 'Could not create HGVS for: %s' % csq
    return csq['HGVSp'].split(':')[-1]

# Note that this is the current as of v77 with 2 included for backwards compatibility (VEP <= 75)
csq_order = ["transcript_ablation",
"splice_acceptor_variant",
"splice_donor_variant",
"stop_gained",
"frameshift_variant",
"stop_lost",
"start_lost",  # new in v81
"initiator_codon_variant",  # deprecated
"transcript_amplification",
"inframe_insertion",
"inframe_deletion",
"missense_variant",
"protein_altering_variant",  # new in v79
"splice_region_variant",
"incomplete_terminal_codon_variant",
"stop_retained_variant",
"synonymous_variant",
"coding_sequence_variant",
"mature_miRNA_variant",
"5_prime_UTR_variant",
"3_prime_UTR_variant",
"non_coding_transcript_exon_variant",
"non_coding_exon_variant",  # deprecated
"intron_variant",
"intronic_variant",
"NMD_transcript_variant",
"non_coding_transcript_variant",
"nc_transcript_variant",  # deprecated
"upstream_gene_variant",
"downstream_gene_variant",
"TFBS_ablation",
"TFBS_amplification",
"TF_binding_site_variant",
"regulatory_region_ablation",
"regulatory_region_amplification",
"feature_elongation",
"regulatory_region_variant",
"feature_truncation",
"intergenic_variant",
"intergenic",
'mature_miR""_variant',
'""'
""]

csq_order_dict = dict(zip(csq_order, range(len(csq_order))))
rev_csq_order_dict = dict(zip(range(len(csq_order)), csq_order))


def worst_csq_index(csq_list):
    """
    Input list of consequences (e.g. ['frameshift_variant', 'missense_variant'])
    Return index of the worst annotation (In this case, index of 'frameshift_variant', so 4)
    Works well with csqs = 'non_coding_exon_variant&nc_transcript_variant' by worst_csq_index(csqs.split('&'))

    :param annnotation:
    :return most_severe_consequence_index:
    """
    return min([csq_order_dict[ann] for ann in csq_list])


def worst_csq_from_list(csq_list):
    """
    Input list of consequences (e.g. ['frameshift_variant', 'missense_variant'])
    Return the worst annotation (In this case, 'frameshift_variant')
    Works well with csqs = 'non_coding_exon_variant&nc_transcript_variant' by worst_csq_from_list(csqs.split('&'))

    :param annnotation:
    :return most_severe_consequence:
    """
    return rev_csq_order_dict[worst_csq_index(csq_list)]


def worst_csq_from_csq(csq):
    """
    Input possibly &-filled csq string (e.g. 'non_coding_exon_variant&nc_transcript_variant')
    Return the worst annotation (In this case, 'non_coding_exon_variant')

    :param consequence:
    :return most_severe_consequence:
    """
    return rev_csq_order_dict[worst_csq_index(csq.split('&'))]


def order_vep_by_csq(annotation_list):
    output = sorted(annotation_list, cmp=lambda x, y: compare_two_consequences(x, y), key=itemgetter('Consequence'))
    for ann in output:
        ann['major_consequence'] = worst_csq_from_csq(ann['Consequence'])
    return output


def worst_csq_with_vep(annotation_list):
    """
    Takes list of VEP annotations [{'Consequence': 'frameshift', Feature: 'ENST'}, ...]
    Returns most severe annotation (as full VEP annotation [{'Consequence': 'frameshift', Feature: 'ENST'}])
    Also tacks on worst consequence for that annotation (i.e. worst_csq_from_csq)
    :param annotation_list:
    :return worst_annotation:
    """
    if len(annotation_list) == 0: return None
    worst = annotation_list[0]
    for annotation in annotation_list:
        if compare_two_consequences(annotation['Consequence'], worst['Consequence']) < 0:
            worst = annotation
        elif compare_two_consequences(annotation['Consequence'], worst['Consequence']) == 0 and annotation['CANONICAL'] == 'YES':
            worst = annotation
    worst['major_consequence'] = worst_csq_from_csq(worst['Consequence'])
    return worst



def compare_two_consequences(csq1, csq2):
    if csq_order_dict[worst_csq_from_csq(csq1)] < csq_order_dict[worst_csq_from_csq(csq2)]:
        return -1
    elif csq_order_dict[worst_csq_from_csq(csq1)] == csq_order_dict[worst_csq_from_csq(csq2)]:
        return 0
    return 1

CHROMOSOMES = ['chr%s' % x for x in range(1, 23)]
CHROMOSOMES.extend(['chrX', 'chrY', 'chrM'])
CHROMOSOME_TO_CODE = { item: i+1 for i, item in enumerate(CHROMOSOMES) }


def get_single_location(chrom, pos):
    """
    Gets a single location from chromosome and position
    chr must be actual chromosme code (chrY) and pos must be integer

    Borrowed from xbrowse
    """
    return CHROMOSOME_TO_CODE[chrom] * int(1e9) + pos


def get_xpos(chrom, pos):
    """
    Borrowed from xbrowse
    """
    if not chrom.startswith('chr'):
        chrom = 'chr{}'.format(chrom)
    return get_single_location(chrom, pos)


def get_minimal_representation(pos, ref, alt):
    """
    Get the minimal representation of a variant, based on the ref + alt alleles in a VCF
    This is used to make sure that multiallelic variants in different datasets,
    with different combinations of alternate alleles, can always be matched directly.

    Note that chromosome is ignored here - in xbrowse, we'll probably be dealing with 1D coordinates
    Args:
        pos (int): genomic position in a chromosome (1-based)
        ref (str): ref allele string
        alt (str): alt allele string
    Returns:
        tuple: (pos, ref, alt) of remapped coordinate
    """
    pos = int(pos)
    # If it's a simple SNV, don't remap anything
    if len(ref) == 1 and len(alt) == 1:
        return pos, ref, alt
    else:
        # strip off identical suffixes
        while(alt[-1] == ref[-1] and min(len(alt),len(ref)) > 1):
            alt = alt[:-1]
            ref = ref[:-1]
        # strip off identical prefixes and increment position
        while(alt[0] == ref[0] and min(len(alt),len(ref)) > 1):
            alt = alt[1:]
            ref = ref[1:]
            pos += 1
        return pos, ref, alt


def union(a, b):
    """ return the union of two lists """
    return list(set(a) | set(b))
