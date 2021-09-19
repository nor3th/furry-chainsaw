import os
import re
import sys
import requests
from bs4 import BeautifulSoup

element_mapping = {
    0: 'source',
    1: 'relationship',
    2: 'target'
}

name_mapping = {
    'identity': ['individual', 'organization', 'sector'],
    'location': ['region', 'country', 'city', 'position'],
    'file': ['stixfile']
}

stix_url = "https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html"


def parse_relationship(content: list, relationships: list) -> list:
    if content[0] == '—' or content[0] == "Source":
        return relationships

    source = content[0]
    relationship = content[1]
    for relat in relationship.split(','):
        for target in content[2].split(','):
            relationships.append({
                element_mapping[0]: source,
                element_mapping[1]: relat.strip(),
                element_mapping[2]: target.strip()
            })

    return relationships


def parse_stix_docs(html_class: dict):
    r = requests.get(stix_url, allow_redirects=True)
    #contents = open('stix-v2.1.html', 'r', encoding='windows-1251').read()
    contents = r.content
    soup = BeautifulSoup(contents, 'lxml')
    items = soup.body.div
    relationships = []
    for t in items.find_all('table', html_class):
        if html_class:
            rel_beginning = True
        else:
            rel_beginning = False
        for tr in t.find_all('tr'):
            content = []
            for td in tr.find_all('td'):
                text = ""
                for p_elem in td.find_all('p'):
                    text += p_elem.text

                if rel_beginning:
                    content.append(text)

                if "Relationship Type" in text:
                    rel_beginning = True
                    break

                if "Reverse Relationships" in text:
                    rel_beginning = False

            if len(content) == 4 or html_class:
                relationships = parse_relationship(content, relationships)

    unique_list = list(
        {(v[element_mapping[0]], v[element_mapping[1]], v[element_mapping[2]]): v for v in relationships}.values())

    if html_class:
        print("---- Running on Summary table ---- ")
    else:
        print("---- Parsing entire page ---- ")

    return unique_list


def parse_config(rels, path):
    file_text = open(path, 'r').read()
    found_connection = 0
    not_found_connection = 0
    found_relationship = 0
    not_found_relationship = 0

    for rel in rels:
        target_name = rel[element_mapping[2]]
        source_name = rel[element_mapping[0]]
        relationship_name = rel[element_mapping[1]]

        if target_name in name_mapping.keys():
            targets = name_mapping[target_name]
        else:
            targets = [target_name]

        if source_name in name_mapping.keys():
            sources = name_mapping[source_name]
        else:
            sources = [source_name]

        for target in targets:
            for source in sources:
                name = f"{source.capitalize()}_{target.capitalize()}(.*)"
                natch = re.search(name, file_text, re.IGNORECASE)
                if natch:
                    _, relation = natch.group().split('[', 1)
                    if relationship_name in relation:
                        found_relationship += 1
                    else:
                        not_found_relationship += 1
                        # print(f"{name} -> {natch.group()}")
                        print(f"{name} needs relationship {relationship_name}")

                    found_connection += 1
                else:
                    print(f"Didn't find {name}")
                    not_found_connection += 1

    print("== Result ==")
    print(f"Object to Object found/not found {found_connection}/{not_found_connection}")
    print(f"Object relationships found/not found {found_relationship}/{not_found_relationship}")
    print("")

def compare(overall: list, summary: list):
    for entry in overall:
        if entry not in summary:
            print(f"Summary is missing {entry}")

    for entry in summary:
        if entry not in overall:
            print(f"Overall is missing {entry}")


if len(sys.argv) < 2:
    print(f"Please provide the path of the OpenCTI 'opencti-platform/opencti-front/src/utils/Relation.js' file")
    exit()

if not os.path.isfile(sys.argv[1]):
    print(f"{sys.argv[1]} is not a file")
    exit()

overall_list = parse_stix_docs({})
parse_config(overall_list, sys.argv[1])

# Compare STIX tables
summary_list = parse_stix_docs({'class': "afffffffff3"})
parse_config(summary_list, sys.argv[1])

compare(overall_list, summary_list)
