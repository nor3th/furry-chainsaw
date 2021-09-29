import requests
from bs4 import BeautifulSoup
import json

element_mapping = {
    0: 'source',
    1: 'relationship',
    2: 'target'
}

# translate those STIX entities
name_mapping = {
    '<All STIX Cyber-observable Objects>': [],
}

# STIX documentation
stix_url = "https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html"


def parse_relationship(content: list, relationships: list) -> list:
    if content[0] == '—' or content[0] == "Source":
        return relationships

    source = content[0]
    relationship = content[1]
    targets = content[2].split(',')
    for relat in relationship.split(','):
        for target in targets:
            target = target.strip()
            if target in name_mapping.keys():
                targets += name_mapping[target]
            else:
                relationships.append({
                    element_mapping[0]: source,
                    element_mapping[1]: relat.strip(),
                    element_mapping[2]: target
                })

    return relationships


def parse_stix_docs(html_class: dict):
    r = requests.get(stix_url, allow_redirects=True)
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

    return unique_list


def export_json(overall: list):
    json_dict = {}
    # sort by source
    for item in overall:
        source = item[element_mapping[0]]
        relationship = item[element_mapping[1]]
        target = item[element_mapping[2]]
        if source in json_dict:
            if target in json_dict[source]:
                json_dict[source][target].append(relationship)
            else:
                json_dict[source][target] = [relationship]
        else:
            json_dict[source] = {target: [relationship]}

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(json_dict, f, ensure_ascii=False, indent=4)


overall_list = parse_stix_docs({})
export_json(overall_list)