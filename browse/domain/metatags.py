"""Functions to make HTML head metadata tags for DocMetadata"""
import re
from datetime import datetime
from typing import Union, Dict, Optional, List

import pytz as pytz

from browse.domain.author_affil import parse_author_affil_utf
from browse.domain.escape_html import escape_special_characters
from browse.domain.metadata import DocMetadata
from browse.domain.routes import pdf


def meta_tag_metadata(metadata: DocMetadata):
    """Return data for HTML <meta> tags as used by Google Scholar.

    http://scholar.google.com/intl/en/scholar/inclusion.html.

    Although in earlier messages Anurag suggested a semicolon separated
    author list in one citation_author element he recommends separate
    elements for each author. Said that truncation of long author lists
    at 100 authors makes sense. """

    meta_tags = []

    if metadata.title:
        meta_tags.append(mtag('citation_title', metadata.title))

    if metadata.authors:
        hundo = parse_author_affil_utf(metadata.authors)[:100]
        meta_tags.extend(filter(lambda a: a is not None, map(format_affil_author, hundo)))

    found_y = False
    if metadata.journal_ref:
        match = re.search('(journal of artificial intelligence research)', metadata.journal_ref, re.IGNORECASE)
        if match:
            meta_tags.append(mtag('citation_journal_title', match.group(1)))
            # check for year of publication
            y_match = re.search(r"([^\d]+(\d{4})\s*$|\((\d{4})\))", metadata.journal_ref)
            if y_match:
                found_y = True
                if y_match.group(2):
                    meta_tags.append(mtag('citation_publication_date', y_match.group(2)))
                else:
                    meta_tags.append(mtag('citation_publication_date', y_match.group(3)))

    if metadata.doi:
        meta_tags.append(mtag('citation_doi', metadata.doi))

    # changed from citation_date to citation_publication_date in 2018-5: citation_date is not in spec
    if not found_y:
        meta_tags.append(mtag('citation_publication_date', metadata.get_datetime_of_version(1)))
    meta_tags.append(mtag('citation_online_date', metadata.get_datetime_of_version(metadata.version)))
    meta_tags.append(mtag('citation_pdf_url', pdf(metadata)))
    meta_tags.append(mtag('citation_arxiv_id', metadata.arxiv_id_v))
    return meta_tags


def format_affil_author(au: List[str]) -> Optional[Dict]:
    if not au or len(au) < 1 or not au[0]:
        return None
    name = au[0]
    name = name + ' ' + au[2] if (len(au) > 2 and au[2]) else name
    name = name + ', ' + au[1] if (len(au) > 1 and au[1]) else name
    # TODO: name is in TeX, do something like tex2utf()
    return mtag('citation_author', name) if name else None


def mtag(name: str, content: Union[int, str, datetime]):
    if isinstance(content, datetime):
        cstr = content.astimezone(pytz.UTC).strftime('%Y/%m/%d')
    elif isinstance(content, int):
        cstr = str(content)
    else:
        cstr = content

    cstr = re.sub(r'\s\s+', ' ', cstr)  # Remove any line breaks/multiple spaces
    return {'name': name,
            'content': escape_special_characters(cstr)}
