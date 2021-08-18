import requests
# 910: topic
# 279: subclass of
# 31: instance of
def get_entities(query):
    r = requests.get(f"https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&type=item&search={query}&limit=1").json()



    return r

def get_info_by_id(id):
    #sparql_query = f"""
    """
        SELECT ?wdLabel ?ps_Label ?ps_ ?p {{
            VALUES (?item) {{(wd:{id})}}
  
            ?item ?p ?statement .
            ?statement ?ps ?ps_ .
          
            ?wd wikibase:claim ?p.
            ?wd wikibase:statementProperty ?ps.
          
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
        }} ORDER BY ?wd ?statement ?ps_
     """

    sparql_query = f"""
        SELECT ?wdLabel ?ps_Label ?ps_ {{
            VALUES (?item) {{(wd:{id})}}
  
            ?item ?p ?statement .
            ?statement ?ps ?ps_ .
          
            ?wd wikibase:claim ?p.
            ?wd wikibase:statementProperty ?ps.
          
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
            FILTER (?ps = ps:P31 || ?ps = ps:P279)
        }} ORDER BY ?wd ?statement ?ps_
        """
    r = requests.get(f"https://query.wikidata.org/sparql?query={sparql_query}&format=json").json()["results"]["bindings"]
    return r
