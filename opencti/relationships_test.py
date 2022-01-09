import json
import os.path
import requests
from bs4 import BeautifulSoup

ALL_SCOs = "<all_SCOs>"
ALL_SDOs = "<all_SDOs>"

headline = ['h1', 'h2', 'h3', 'h4']

simple_SOs = ['binary', 'dictionary', 'enum', 'hex']

element_mapping = {
    0: 'source',
    1: 'relationship',
    2: 'target'
}

local_filename = "./stix-v2.1-os.html"

sco_list = [
  # 'artifact',
  'autonomous-system',
  'directory',
  'domain-name',
  'email-addr',
  'email-message',
  'email-mime-part-type',
  'stixfile', # file original name
  # 'windows-pebinary-ext',
  # 'windows-pe-optional-header-type',
  # 'windows-pe-section-type',
  'ipv4-addr',
  'ipv6-addr',
  'mac-addr',
  'mutex',
  'network-traffic',
  # 'http-request-ext',
  # 'imcp-ext',
  # 'socket-ext',
  # 'tcp-ext',
  'process',
  # 'windows-process-ext',
   # 'windows-service-ext',
  'url',
  'user-account',
  # 'unix-account-ext',
  'windows-registry-key',
  'windows-registry-value-type',
  'x509-certificate',
  'x509-v3-extensions-type',
]

# translate those STIX entities
name_mapping = {
    '<All STIX Cyber-observable Objects>': [ALL_SCOs],
    ALL_SCOs: sco_list
}

# those mapping were added manually, since automatic parsing for nested
# relations was not possible
hard_coded_mapping = {
    'file': {
        'contains': [ALL_SCOs]
    },
    # 'sighting': {
    #     'where_sighted': ['location', 'identity'],
    #     'observed_data': ['observed_data'],
    #     'sighting_of': [ALL_SDOs]
    # },
    # 'relationship': {
    #     'target': [ALL_SCOs, ALL_SDOs],
    #     'source': [ALL_SCOs, ALL_SDOs],
    # },
    'malware-analysis': {
        'sample': ['file', 'network-traffic', 'artifact'],
        'analysis-sco': [ALL_SCOs]
    },
    'malware': {
        'sample': ['file', 'artifact']
    }
}

# STIX documentation
stix_url = "https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html"


def parse_ref_properties(content: list, relationships: list, so_name: str, so_list: list[str]) -> list:
    # print(content)
    if len(content) == 0 or so_name in name_mapping.keys():
        return relationships

    # resolves-to and belongs-to is also a relationship
    if "object_ref" in content[0] or \
            "resolves_to" in content[0] or \
            "belongs_to" in content[0] or \
            "identifier" not in content[1]:
        return relationships

    found_sos = []
    for so in so_list:
        if 'MUST' in content[2]:
            if so in content[2].split('MUST')[1]:
                found_sos.append(so)

    relationship_name = content[0].split('_ref')[0].replace('_', '-')

    if len(found_sos) == 0:
        if so_name in hard_coded_mapping and relationship_name in hard_coded_mapping[so_name]:
            targets = hard_coded_mapping[so_name][relationship_name]
            found_sos += targets
            print(f"Using hardcoded approach for {so_name} -> {relationship_name}: {found_sos}")
        else:
            print(f"Needs post processing ref? {so_name} -> {relationship_name} ({content})")
    # print(f"Possible ref? {content} ({found_sos})")

    for so in found_sos:
        relationships.append({
            element_mapping[0]: so_name,
            element_mapping[1]: relationship_name,
            element_mapping[2]: so
        })

    return relationships


def parse_relationship(content: list, relationships: list) -> list:
    if content[0] == '—' or content[0] == "Source" or content[0] == '\x97':
        return relationships

    source = content[0]
    if source in name_mapping.keys():
        return relationships

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


def get_so(items) -> list:
    so_list = []
    for item in items.findAll("p"):
        so_span = item.find(
            "span",
            {"style": "font-family:Consolas;color:#C7254E;background:#F9F2F4"},
            recursive=False,
            # string=re.compile(r"Type*")
        )
        if so_span and "Type Name" in item.text:
            so_name = item.text.split(": ")[1]
            if so_name in simple_SOs:
                continue

            so_list.append(so_name)
            print(f"SDO found: {so_name}")

    return so_list


def parse_stix_docs(html_class: dict):
    if os.path.isfile(local_filename):
        with open(local_filename, 'r', encoding="ISO-8859-1") as f:
            contents = f.read()
    else:
        r = requests.get(stix_url, allow_redirects=True)
        contents = r.content
        with open(local_filename, "wb") as file:
            file.write(contents)

    soup = BeautifulSoup(contents, 'lxml')
    items = soup.body.div
    relationships = []

    so_list = get_so(items)

    for t in items.find_all('table', html_class):
        parent_headline = set()
        so_name = ""
        for prev_tag in t.find_all_previous(['p'] + headline):
            if prev_tag.name in headline:
                parent_headline.add(prev_tag.name)

            if "Type Name" in prev_tag.text:
                so_name = prev_tag.text.split(": ")[1]
                break

            if len(parent_headline) >= 2:
                # print("Not what I'm looking for")
                break

        # Not the table I'm looking for
        if so_name == "":
            continue

        # Relationship or property table
        table_type = ""
        if html_class:
            info_beginning = True
        else:
            info_beginning = False

        for tr in t.find_all('tr'):
            content = []
            for td in tr.find_all('td'):
                text = ""
                for p_elem in td.find_all('p'):
                    text += p_elem.text

                text = text.replace('\r', '').replace('\n', '').replace('  ', ' ')

                if info_beginning:
                    content.append(text)

                # Detect Property Table
                if "Required Common Properties" in text:
                    table_type = "property"
                    break

                if "Property Name" in text and table_type == "property":
                    info_beginning = True
                    break

                # Detect Relationship Table
                if "Relationship Type" in text:
                    info_beginning = True
                    table_type = "relationship"
                    break

                if "Reverse Relationships" in text:
                    info_beginning = False

            if table_type == "relationship" and (len(content) == 4 or html_class):
                relationships = parse_relationship(content, relationships)
            elif table_type == "property":
                relationships = parse_ref_properties(content, relationships, so_name, so_list)

        if table_type != "":
            print(f"SDO: {so_name} Table type: {table_type}")

    unique_list = list(
        {(v[element_mapping[0]], v[element_mapping[1]], v[element_mapping[2]]): v for v in relationships}.values())

    return unique_list


def export_json(overall: list):
    json_dict = {}
    # sort by source
    # pprint(overall)
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
