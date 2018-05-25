"""Parse Authors lines to extract author and affiliation data"""
import re
from itertools import dropwhile
from typing import List, Tuple, Dict

PREFIX_MATCH = 'van|der|de|la|von|del|della|da|mac|ter|dem|di'

"""
Takes data from an Author: line in the current arXiv abstract
file and returns a structured set of data:
 
 author_list_ptr = [
  [ author1_keyname, author1_firstnames, author1_suffix, affil1, affil2 ] ,
  [ author2_keyname, author2_firstnames, author1_suffix, affil1 ] ,
  [ author3_keyname, author3_firstnames, author1_suffix ] 
         ]

Abstracted from Dienst software for OAI1 and other uses. This
routine might at some stage be incorporated into Metadata.pm
but should just go away when a better metadata structure is
adopted that deals with names and affiliations properly.

Must remember that there is at least one person one the archive 
who has only one name, this should clearly be considered the key name.

Code originally written by Christina Scovel, Simeon Warner Dec99/Jan00 
 2000-10-16 - separated. 
 2000-12-07 - added support for suffix
 2003-02-14 - get surname prefixes from arXiv::Filters::Index [Simeon]
 2007-10-01 - created test script, some tidying [Simeon]
 2018-05-25 - Translated from Perl to Python [Brian C.]
"""


def parse_author_affil(authors: str) -> List[List[str]]:
    """
    Takes an unparsed author line as input string and returns an
    list of author and affiliation data.

    The list for each author will have at least three elements for
    keyname, firstname(s) and suffix. The keyname will always have content
    but the other stings might be empty stings if there is no firstname
    or suffix. Any additional elements after the first three are affiliations,
    there may be zero or more.

    Handling of prefix "XX collaboration" etc. is duplicated here and in
    arXiv::HTML::AuthorLink -- it shouldn't be. Likely should just be here.

    This routine is just a wrapper around the two parts that first split
    the authors line into parts, and then back propagate the affiliations.
    The first part is to be used along for display where we do not want
    to back propagate affiliation information.

    :param authors: string of authors from abs file or similar
    :return:
    Returns a structured set of data:
    author_list_ptr = [
        [ author1_keyname, author1_firstnames, author1_suffix, affil1, affil2 ] ,
        [ author2_keyname, author2_firstnames, author1_suffix, affil1 ] ,
        [ author3_keyname, author3_firstnames, author1_suffix ]
    ]
    """

    return parse_author_affil_back_propagate(**parse_author_affil_split(authors))

def parse_author_affil_split(author_line: str):
    """
    Take author line, tidy spacing and punctuation, and then split up into
    individual author an affiliation data. Has special cases to avoid splitting
    an initial collaboration name and records in $back_propagate_affiliation_to
    the fact that affiliations should not be back propagated to collaboration
    names.

    Does not handle multiple collaboration names.
    """
    names = split_authors(author_line)
    if not names or len(names) == 0:
        return {'author_list': [], 'back_prop': 0}

    #names = map(lambda n: n.lstrip().rstrip(), names)

    names = remove_double_commas(names)
    names = reversed(list(dropwhile(lambda x: x == ',', reversed(names))))  # get rid of commas at back
    names = list(dropwhile(lambda x: x == ',', names))  # get rid of commas at front

    # Extract all names (all parts not starting with comma or paren)
    names = list(map(tidy_name, filter(lambda x: re.match('^[^](,]', x), names)))
    names = list(filter(lambda n: not re.match(r'^\s*et\.\s+al\.?\s*', n, flags=re.IGNORECASE), names))

    (names, author_list, back_propagate_affiliations_to) = collaboration_at_start(names)

    (enumaffils) = enum_collaboration_at_end(author_line)

    # Now go through names in turn and try to get affiliations
    # to go with them
    for name in names:
        # Split name into keyname and firstnames/initials.
        # Deal with different patterns in turn: prefixes, suffixes, plain
        # and single name.
        patterns = [('double-prefix', r'^(.*)\s+(' + PREFIX_MATCH + r')\s(' + PREFIX_MATCH + r')\s(\S+)$'),
                    ('name-prefix-name', r'^(.*)\s+(' + PREFIX_MATCH + ')\s(\S+)$'),
                    ('name-name-prefix', r'^(.*)\s+(\S+)\s(I|II|III|IV|V|Sr|Jr|Sr\.|Jr\.)$'),
                    ('name-name', r'^(.*)\s+(\S+)$'), ]

        pattern_matches = ((mtype, re.match(m, name, flags=re.IGNORECASE))
                           for (mtype, m) in patterns)

        (mtype, match) = next(((mtype, m)
                               for (mtype, m) in pattern_matches if m is not None), ('default', None))

        if mtype == 'double-prefix':
            s = '{} {} {}'.format(match.group(2), match.group(3), match.group(4))
            author_entry = [s, match.group(1), '']
        elif mtype == 'name-prefix-name':
            s = '{} {}'.format(match.group(2), match.group(3))
            author_entry = [s, match.group(1), '']
        elif mtype == 'name-name-prefix':
            author_entry = [match.group(2), match.group(1), match.group(3)]
        elif mtype == 'name-name':
            author_entry = [match.group(2), match.group(1), '']
        else:
            author_entry = [name, '', '']

        # search back in author_line for affiliation
        author_entry = add_affiliation( author_line, enumaffils, author_entry, name)
        author_list.append(author_entry)

    return {'author_list': author_list, 'back_prop': back_propagate_affiliations_to}


def remove_double_commas(items: List[str]) -> List[str]:
    parts = []
    last = ''
    for p in items:
        if p == ',' and last == ',':
            next
        else:
            parts.append(p)
            last = p
    return parts


def tidy_name(name: str) -> str:
    name = re.sub('\s\s+', ' ', name)  # also gets rid of CR
    # add space after dot (except in TeX)
    name = re.sub(r'(?<!\\)\.(\S)', '. \g<1>', name)
    return name


def collaboration_at_start(names: List[str])->Tuple[List[str], List[List[str]], int]:
    """Special handling of collaboration at start"""
    author_list = []

    back_propagate_affiliations_to = 0
    while len(names) > 0:
        m = re.match(r'^([a-z0-9]+\s+(collaboration|group|team))',
                     names[0], flags=re.IGNORECASE)
        if not m:
            break

        # Add to author list
        author_list.append([m.group(1), '', ''])
        back_propagate_affiliations_to += 1
        # Remove from names
        names.pop(0)
        # Also swallow and following comma or colon
        if len(names) > 0 and (names[0] == ',' or names[0] == ':'):
            names.pop(0)

    return names, author_list, back_propagate_affiliations_to


def enum_collaboration_at_end(author_line:str)->Dict:
    """ Gets separate set of enumerated affiliations from end of author_line"""

    # Now see if we have a separate set of enumerated affiliations
    # This is indicated by finding '(\s*('
    line_m = re.search(r'\(\s*\((.*)$', author_line)
    if not line_m:
        return {}

    enumaffils = {}
    affils = re.sub(r'\s*\)\s*$', '', line_m.group(1))

    # Now expect to have '1) affil1 (2) affil2 (3) affil3'
    for affil in affils.split('('):
        # Now expect `1) affil1 ', discard if no match
        m = re.match(r'^(\d+)\)\s*(\S.*\S)\s*$', affil)
        if m:
            enumaffils[m.group(1)] = re.sub(r'[\.,\s]*$', '', m.group(2))

    return enumaffils


def add_affiliation(author_line: str, enumaffils: Dict, author_entry: List[str], name: str):
    """Add author affiliation to author_entry if one is found in author_line
    This should deal with these cases
    Smith B(labX) Smith B(1) Smith B(1, 2) Smith B(1 & 2) Smith B(1 and 2)  """

    en = re.escape(name)
    namerex = r'{}\s*\(([^\(\)]+)'.format( en.replace(' ', 's*'))
    m = re.search(namerex, author_line, flags=re.IGNORECASE)
    if not m:
        return author_entry

    # Now see if we have enumerated references (just commas, digits, &, and)
    affils = m.group(1).rstrip().lstrip()
    affils = re.sub(r'(&|and)/,', ',', affils, flags=re.IGNORECASE)

    if re.match(r'^[\d,\s]+$', affils):
        for affil in affils.split(','):
            if affil in enumaffils:
                author_entry.append(enumaffils[affil])
    else:
        author_entry.append(affils)

    return author_entry


def parse_author_affil_back_propagate(author_list: List[List[str]], back_prop: int) -> List[List[str]]:
    """Take the author list structure generated by parse_author_affil_split(..)
    and propagate affiliation information backwards to preceeding author
    entries where none was give. Stop before entry $back_prop to avoid
    adding affiliation information to collaboration names.

    given, eg:
      a.b.first, c.d.second (affil)
    implies
      a.b.first (affil), c.d.second (affil)
    and in more complex cases:
      a.b.first, c.d.second (1), e.f.third, g.h.forth (2,3)
    implies
      a.b.first (1), c.d.second (1), e.f.third (2,3), g.h.forth (2,3)
    """
    last_affil=False
    for x in range(len(author_list)-1, max(back_prop-1,-1), -1):
        author_entry = author_list[x]
        if len(author_entry) > 3: #author has affiliation,store
            last_affil = author_entry
        elif last_affil:
            #author doesn't have affil but later one did => copy
            author_entry.extend( last_affil[3:])

    return author_list


def split_authors(authors):
    """ Take and author line as a string and return a reference to a list of the
    different name and affiliation blocks. While this does normalize spacing
    and 'and', it is a key feature that the set of strings returned can be
    concatenated to reproduce the original authors line. This code thus
    provides a very graceful degredation for badly formatted authors lines,
    the text at least shows up."""

    # split authors field into blocks with boundaries of ( and )
    aus = re.split('(\(|\))', authors)
    aus = list(filter(lambda x: x != '', aus))

    blocks = []
    if len(aus) == 1:
        blocks.append(authors)
    else:
        c = ''
        depth = 0
        for bit in aus:
            if bit == '':
                next
            if bit == '(':  # track open parentheses
                depth += 1
                if depth == 1:
                    blocks.append(c)
                    c = '('
                else:
                    c = c + bit
            elif bit == ')':  # track close parentheses
                depth -= 1
                c = c + bit
                if depth == 0:
                    blocks.append(c)
                    c = ''
                else:  # haven't closed, so keep accumulating
                    next
            else:
                c = c + bit
        if c:
            blocks.append(c)

    listx = []

    for block in blocks:
        block = re.sub('\s+', ' ', block)
        if re.match('^\(', block):  # it is a comment
            listx.append(block)
        else:  # it is a name
            block = re.sub(',?\s+(and|\&)\s', ',', block)
            names = re.split('(,|:)\s*', block)
            for name in names:
                if not name:
                    next
                name = name.rstrip().lstrip()
                if name:
                    listx.append(name)

    # Recombine suffixes that were separated with a comma
    parts = []
    for p in listx:
        if re.match(r'^(Jr\.?|Sr\.?\[IV]{2,})$', p) \
                and len(parts) >= 2 \
                and parts[-1] == ',' \
                and not re.match('\)$', parts[-2]):
            separator = parts.pop()
            last = parts.pop()
            recomb = "{}{} {}".format( last, separator, p)
            parts.append(recomb)
        else:
            parts.append(p)

    return parts


def parse_author_affil_utf():
    #TODO implement this
    """Passes $author_line to parse_author_affil() and does TeX to UTF
    conversion on all elements of the resulting array. Output
    structure is the same but should be in UTF and not TeX.
    """
    pass
#   my ($author_line)=@_;
#   my $author_list_ptr=parse_author_affil($author_line);

#   # Go through all fields and do in place TeX to UTF conversion
#   #
#   foreach my $author_entry_ptr (@$author_list_ptr) {
#     for (my $j=0;$j<=$#{$author_entry_ptr};$j++) {
#       $author_entry_ptr->[$j]=tex2UTF($author_entry_ptr->[$j]);
#     }
#   }
#   return($author_list_ptr);
# }