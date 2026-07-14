'''
script to upload test to https://fairsharing.org/

'''

import os
import configparser
import time
import argparse
import requests
import json
import re
from collections import defaultdict
from rdflib import Graph


QUERY = """
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dqv: <http://www.w3.org/ns/dqv#>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX vcard: <http://www.w3.org/2006/vcard/ns#>
PREFIX ftr: <https://w3id.org/ftr#>
PREFIX vivo: <http://vivoweb.org/ontology/core#>
PREFIX sio: <http://semanticscience.org/resource/>


SELECT DISTINCT ?metric ?title ?description ?label ?version ?license ?landingPage ?contact ?contactName ?contactEmail ?dimension ?test ?supportedBy
WHERE {
  ?metric a dqv:Metric ;
          dcterms:title ?title ;
          dcterms:description ?description ;
          rdfs:label ?label ;
          dcat:version ?version ;
          dcterms:license ?license ;
          dcat:landingPage ?landingPage ;
          dcterms:creator ?contact ;
          dqv:inDimension ?dimension ;
          sio:SIO_000234 ?test ;
          ftr:supportedBy ?supportedBy .
          
  OPTIONAL {
    ?contact vcard:fn ?contactName ;
             vcard:hasEmail ?contactEmail .
  }
}

"""

QUERY_BENCHMARK = """
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dqv: <http://www.w3.org/ns/dqv#>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX vcard: <http://www.w3.org/2006/vcard/ns#>
PREFIX ftr: <https://w3id.org/ftr#>
PREFIX vivo: <http://vivoweb.org/ontology/core#>
PREFIX dpv: <https://w3id.org/dpv#>

SELECT DISTINCT ?benchmark ?title ?description ?label ?version ?license ?landingPage ?contact ?contactName ?contactEmail
WHERE {
  ?benchmark a ftr:Benchmark ;
          dcterms:title ?title ;
          dcterms:description ?description ;
          rdfs:label ?label ;
          dcat:version ?version ;
          dcterms:license ?license ;
          dcat:landingPage ?landingPage ;
          dcterms:creator ?contact .

  OPTIONAL {
    ?contact vcard:fn ?contactName ;
             vcard:hasEmail ?contactEmail .
  }
}

"""

def extract_orcid(uri):
    match = re.search(r"orcid\.org/([\d\-X]+)", uri)
    return match.group(1) if match else ""

def extract_abbreviation(uri):
    return uri.rstrip("/").split("/")[-1]

def ttl_to_fairsharing_json(path_ttl, query, record_types, countries, subjects, domains, taxonomies, organisations, licences, objects, principles, associations):
    config = configparser.ConfigParser()
    config.read('config.ini')
    name_prefix = config.get('Prefixes', 'name_prefix').strip('"')
    abbr_prefix = config.get('Prefixes', 'abbreviation_prefix').strip('"')
   
    record_types = find_id_by_name(record_types, ["Metric"])
    record_type_id = record_types[0] if record_types else None
    country_id = find_id_by_name(countries, ["Spain"])
 
    subjects_id = find_id_by_label(subjects, ["Subject Agnostic"])
    domains_id = find_id_by_label(domains, ["FAIR", "centrally registered identifier"])
    taxonomies_id = find_id_by_label(taxonomies, ["Not applicable"])
    licence_id = find_id_by_partial_name(licences, "CC BY 4.0")
    organisation_id = find_id_by_partial_name(organisations, "Ontology Engi")
    data_objects = objects.get("data", [])
    # print(json.dumps(data_objects, indent=4)) 
    objects_id = find_id_by_label(data_objects, ["Terminology Artifact"])
    # print(objects_id)

    g = Graph()
    g.parse(path_ttl, format="turtle")
    results = g.query(query)

    # 4 --> related_to
    # 13 --> measure_principle
    measure_id = find_id_by_name(associations, ["measures_principle"])
    related_to =  find_id_by_name(associations, ["related_to"])

    grouped = defaultdict(lambda: {
        "fairsharing_record": {
            "metadata": {
                "contacts": [],
                "status": "in_development",
                "year_creation": 2024,
                "associated_tests": [
                    {
                            "url": "",
                            "description": ""
                    }
                ],
                "associated_tools": [
                    {
                            "url": "",
                            "name": ""
                    }
                ]
            },
            "record_type_id": None,
            "subject_ids": [],
            "object_type_ids": [],
            # "object_type_id": None,
            "domain_ids": [],
            "taxonomy_ids": [],
            "user_defined_tag_ids": [],
            "country_ids": [],
            "publication_ids": [],
            "citation_ids": [],
            "organisation_links_attributes": [
            {
                "organisation_id": None,
                "relation": "maintains",
                "is_lead": True
            }
            ],
            "licence_links_attributes":  [
                    {
                        "licence_id": None, 
                        "relation": "applies_to_content"
                    }
            ],   
            "record_associations_attributes": [
                {
                    "linked_record_id": 6306,
                    "record_assoc_label_id": related_to[0]
                },
                {
                    "linked_record_id": 6978,
                    "record_assoc_label_id": related_to[0]
                },
                {
                    "linked_record_id": None,
                    "record_assoc_label_id": measure_id[0]
                }
            ]  
        }

    })

    for row in results:
        key = str(row.metric)
        print(f"-----{key}")
        record = grouped[key]["fairsharing_record"]["metadata"]

        record["name"] = f"{name_prefix}{str(row.title)}"
        record["description"] = str(row.description)
        record["abbreviation"] = f"{abbr_prefix}{extract_abbreviation(str(row.metric))}"
        record["homepage"] = str(row.landingPage)
        record["associated_tests"][0]["url"] = row.test
        record["associated_tests"][0]["description"] = f"{extract_abbreviation(str(row.metric))} test"
        record["associated_tools"][0]["url"] = row.supportedBy
        record["associated_tools"][0]["name"] = "FOOPS"

        grouped[key]["fairsharing_record"]["record_type_id"] = record_type_id
        grouped[key]["fairsharing_record"]["country_ids"] = country_id
        grouped[key]["fairsharing_record"]["subject_ids"] = subjects_id
        grouped[key]["fairsharing_record"]["object_type_ids"] = objects_id
        # grouped[key]["fairsharing_record"]["object_type_id"] = objects_id[0]
        grouped[key]["fairsharing_record"]["domain_ids"] = domains_id
        grouped[key]["fairsharing_record"]["taxonomy_ids"] = taxonomies_id
        grouped[key]["fairsharing_record"]["organisation_links_attributes"][0]["organisation_id"] = organisation_id
        grouped[key]["fairsharing_record"]["licence_links_attributes"][0]["licence_id"] = licence_id

        email = str(row.contactEmail) if row.contactEmail else ""
        if email.startswith("mailto:"):
            email = email[len("mailto:"):]

        contact = {
            "contact_name": str(row.contactName) if row.contactName else str(row.contact),
            "contact_email": email,
            "contact_orcid": extract_orcid(str(row.contact))
        }

        if contact not in record["contacts"]:
            record["contacts"].append(contact)

        dimension_uri = row.dimension
        principle_text = dimension_uri.split("/")[-1]
        principle_name = f"FAIR Principles {principle_text}"
        principel_id = find_id_by_partial_name(principles, principle_name)
        # print (principle_name)
        # print (principel_id)
        grouped[key]["fairsharing_record"]["record_associations_attributes"][2]["linked_record_id"] = principel_id


    return list(grouped.values())


def item_to_list(path, plist, query,record_types, countries, subjects, domains, taxonomies, organisations, licences, objects, principles, associations):
    """
        iterate metric path 
    """
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".ttl"):
                path_ttl = os.path.join(root, file)
                metrics = ttl_to_fairsharing_json(path_ttl, query, record_types, countries, subjects, domains, taxonomies, organisations, licences, objects, principles, associations)
                plist.extend(metrics)


def items_to_register(metrics, token):
    config = configparser.ConfigParser()
    config.read('config.ini')

    base_url = config.get('Paths', 'fairsharing_api_url').strip('"')
    
    # url_register = "https://api.fairsharing.org/fairsharing_records/"
    url_register = f"{base_url.rstrip('/')}/fairsharing_records/"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    for metric in metrics:
        try:
            response = requests.post(url_register, json=metric, headers=headers, timeout=60)
            print(f"Registering: {metric['fairsharing_record']['metadata']['name']}")
            print(f"Status Code: {response.status_code}")
            if response.status_code == 201:
                print("Metric registered successfully.")
            else:
                print(f"Error ({response.status_code}): {response.text}")
            time.sleep(1)
        except requests.exceptions.RequestException as e:
            print(f"Error sending metric: {e}")


def items_to_preview(metrics):
    '''
    Print the JSON for each metric instead of registering it
    '''
    print("\n--- Previewing generated JSON for each metric ---\n")
    for metric in metrics:
        print(json.dumps(metric, indent=2, ensure_ascii=False))
        print("\n---\n")


def get_fairsharing_token():
    config = configparser.ConfigParser()
    config.read('config.ini')

    username = config.get('Auth', 'username').strip('"')
    password = config.get('Auth', 'password').strip('"')
    base_url = config.get('Paths', 'fairsharing_api_url').strip('"')

    url = f"{base_url.rstrip('/')}/users/sign_in"
    payload = {
        "user": {
            "login": username,
            "password": password
        }
    }
    # print(json.dumps(payload, indent=4))
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, json=payload, headers=headers)

    print("Status code:", response.status_code)
    print("Full response JSON:", response.json())

    if response.status_code == 200:
        token = response.json().get("jwt")
        print("Login successful.")
        return token
    else:
        print("Login failed:", response.status_code, response.text)
        return None
    

def query_graphql_fairsharing(query_string, variables=None):

    config = configparser.ConfigParser()
    config.read('config.ini')

    base_url = config.get('Paths', 'fairsharing_api_url').strip('"')
    graphql_key = config.get('Auth', 'graphql_key').strip('"')
    url = f"{base_url.rstrip('/')}/graphql"
    # url = "https://api.fairsharing.org/graphql"

    headers = {
        "Content-Type": "application/json",
        "X-GraphQL-Key": graphql_key
    }

    payload = {
        "query": query_string,
        "variables": variables or {}
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"GraphQL query failed: {response.status_code}")
        print(response.text)
        return None


def fetch_and_store_fairsharing_values(endpoint, token, filename):
    config = configparser.ConfigParser()
    config.read('config.ini')

    base_url = config.get('Paths', 'fairsharing_api_url').strip('"')
    
    url = f"{base_url.rstrip('/')}/search/{endpoint}"
    # url = f"https://api.fairsharing.org/search/{endpoint}"
    print(url)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(f"{endpoint} saved to {filename}")
        if isinstance(data, dict):
            # Buscar la primera clave cuyo valor sea una lista
            for key, value in data.items():
                if isinstance(value, list):
                    print(f"Number of dict records in '{key}': {len(value)}")
                    # print("First 1 records:")
                    # for item in value[:1]:
                    #     print(json.dumps(item, indent=4))
                    break
            else:
                print("Could not determine number of records.")
        elif isinstance(data, list):
            print(f"Number of list records: {len(data)}")
            # print("First 1 records:")
            # for item in data[:1]:
            #     print(json.dumps(item, indent=4))
        else:
            print("Could not determine number of records.")

        
        # print(json.dumps(data, indent=4)) 
        return data
    else:
        print(f"Error fetching {endpoint}: {response.status_code}")
        return None
    
def get_fairsharing_records(record, token, filename):
    config = configparser.ConfigParser()
    config.read('config.ini')

    base_url = config.get('Paths', 'fairsharing_api_url').strip('"')
    
    url = f"{base_url.rstrip('/')}/fairsharing_record/{record}"
    # url = f"https://api.fairsharing.org/fairsharing_records/{record}"
    print(url)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(f"{record} saved to {filename}")
        # print(json.dumps(data, indent=4)) 
        return data
    else:
        print(f"Error fetching {record}: {response.status_code}")
        return None

    
def get_fairsharing_organisations(token, filename, query="Oxford"):
    config = configparser.ConfigParser()
    config.read('config.ini')

    base_url = config.get('Paths', 'fairsharing_api_url').strip('"')
    
    url = f"{base_url.rstrip('/')}/search/organisations"
    # url = "https://api.fairsharing.org/search/organisations"
    print(f"POST to: {url} with query: {query}")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload = {
        "q": query
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Organisations saved to {filename}")
        return data
    else:
        print(f"Error fetching Organisations: {response.status_code}")
        print(response.text)
        return None

def get_fairsharing_relations(token, filename):
    config = configparser.ConfigParser()
    config.read('config.ini')

    base_url = config.get('Paths', 'fairsharing_api_url').strip('"')
    
    url = f"{base_url.rstrip('/')}/recordAssociationLabels"
    # url = "https://api.fairsharing.org/search/organisations"
    print(f"POST to: {url}")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }


    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Organisations saved to {filename}")
        return data
    else:
        print(f"Error fetching Organisations: {response.status_code}")
        print(response.text)
        return None
      
def find_id_by_name(data, names):
    ids = []
    for name in names:
        found = False
        for item in data:
            if item.get("name", "").lower() == name.lower():
                ids.append(item.get("id"))
                found = True
                break
        if not found:
            print(f"Name not found: {name}")
    return ids


def find_id_by_label(data, labels):

    ids = []
    for label in labels:
        found = False
        for item in data:
            if item.get("label", "").lower() == label.lower():
                ids.append(item.get("id"))
                found = True
                break
        if not found:
            print(f"Label not found: {label}")
    return ids

def find_id_by_partial_name(data, term):

    for item in data:
        if isinstance(item, dict) and term.lower() in item.get("name", "").lower():
            return item.get("id")
    print(f"No match with: {term}")
    return None

def main():
    ''' 
        init register process
    '''

    parser = argparse.ArgumentParser(description="Script managed files .ttl")
    parser.add_argument(
        '-i', help="Source folder where the TTL files for the metrics are located. Use to be ../doc/metric/", required=True)

    args = parser.parse_args()
    path_source = args.i

    metrics = []

    print("----- START of the process ------")
    token = get_fairsharing_token()

    record_types = fetch_and_store_fairsharing_values("record_types", token, "record_types.json")["data"]
    countries = fetch_and_store_fairsharing_values("countries", token, "countries.json")
    subjects = fetch_and_store_fairsharing_values("subjects", token, "subjects.json")["data"]
    domains = fetch_and_store_fairsharing_values("domains", token, "domains.json")["data"]
    taxonomies = fetch_and_store_fairsharing_values("taxonomies", token, "taxonomies.json")
    object_types = fetch_and_store_fairsharing_values("object_types", token, "objects.json")
    # record_associations_types = get_fairsharing_relations(token, "objects_relation.json")["data"]
    # print(record_associations_types)

    query_organisations = """

        query SearchOrgs($term: String!) {
        searchOrganisations(q: $term) {
            id
            name
        }
    }
    """

    result_organisations = query_graphql_fairsharing(
        query_string=query_organisations,
        variables={"term": "Ontology Engineering"}
    )

    query_licenses = """
    query SearchLicences($term: String!) {
        searchLicences(q: $term) {
            id
            name
            url
        }
        }
    """
    result_licences = query_graphql_fairsharing(
        query_string=query_licenses,
        variables={"term": "Creative Commons"}
    )

    query_fair_principles = """
    query {
        recordType(id: 17) {
        name
        fairsharingRecords {
            id
            name
        }
        }
    }
    """

    result_principles = query_graphql_fairsharing(
        query_string=query_fair_principles,
        variables={"term": "FAIR Principles"}
    )


    # print(result_principles)
    # query_subjects = """
    # query SearchSubjects($term: String!) {
    #     searchSubjects(q: $term) {
    #         id
    #         label
    #     }
    #     }
    # """
    # result_subjects = query_graphql_fairsharing(
    #     query_string=query_subjects,
    #     variables={"term": "Subject Agnostic"}
    # )
    # print(result_subjects)
    # query_records = """
    # query SearchRecords($term: String!) {
    #     allFairsharingRecords(q: $term) {
    #         id
    #         name
    #     }
    # }
    # """
    # query_records = """
    # query {
    # fairsharingRecord(id: 6808){
    #     name
    #     abbreviation
    #     type
    #     objectTypes {
    #         id
    #         label
    #     }
    #     recordAssociations {
    #         id
    #         recordAssocLabel
    #         linkedRecord {
    #                 id
    #                 name
    #                 type
    #             }
    #         }
    #     }
    # }
    # """
    # result_records = query_graphql_fairsharing(
    #     query_string=query_records
    # )
    # print(result_records)

    query_associations = """
    query {
        recordAssociationLabels {
            id
            name
            parentId
        }
    }
    """
    result_associations = query_graphql_fairsharing(
        query_string=query_associations,
        # variables={"term": "measure"}
    )
    print(result_associations)
    licences = result_licences.get("data", {}).get("searchLicences", [])
    organisations = result_organisations.get("data", {}).get("searchOrganisations", [])
    principles = result_principles.get("data", {}).get("recordType", {}).get("fairsharingRecords", [])
    associations = result_associations.get("data", {}).get("recordAssociationLabels", [])
    item_to_list(path_source, metrics, QUERY, record_types, countries, subjects, domains, taxonomies, organisations, licences, object_types, principles, associations)
    items_to_preview(metrics)
    items_to_register(metrics, token)
    print("----- END of the process ------")


if __name__ == "__main__":
    main()