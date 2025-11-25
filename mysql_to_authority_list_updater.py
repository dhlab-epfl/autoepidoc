#!/usr/bin/env python3
"""
mysql_to_authority_list_updater.py

Generates/Updates existing TEI/EpiDoc-compliant authority lists from MySQL lookup tables.
If the file exists, it updates entries and adds new ones. 
If the file does not exist, it creates it.


Usage:
    python mysql_to_authority_list_updater.py \
        --host 127.0.0.1 \
        --user etl_user \
        --password EtlUserPss \
        --db epidata \
        --out ./authlist
"""

import argparse
import os
from sqlalchemy import create_engine, text
import xml.etree.ElementTree as ET
import datetime

# register Namespaces
ET.register_namespace('', "http://www.tei-c.org/ns/1.0")
ET.register_namespace('crm', "http://www.cidoc-crm.org/cidoc-crm/")

# ramespace Dictionary for XPath lookups
NS = {
    'tei': 'http://www.tei-c.org/ns/1.0',
    'xml': 'http://www.w3.org/XML/1998/namespace'
}

def clean_tree(elem):
    if elem.text and not elem.text.strip():
        elem.text = None
    if elem.tail and not elem.tail.strip():
        elem.tail = None
    
    for child in elem:
        clean_tree(child)

def write_xml(root, filename):
    """
    Cleans, indents, and writes the XML file.
    """
    clean_tree(root)
    
    ET.indent(root, space="  ", level=0)
    
    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)

def get_or_create_tei_root(filepath, xmlid_root, isArtsakh=False):
    """Parses existing file or creates a new TEI root if file missing."""
    if os.path.exists(filepath):
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            # Update revisionDesc
            header = root.find(".//tei:teiHeader", NS)
            if header is not None:
                rev_desc = header.find(".//tei:revisionDesc", NS)
                if rev_desc is None:
                    rev_desc = ET.SubElement(header, "revisionDesc")
                
                # Add a new change record
                ET.SubElement(rev_desc, "change", when=datetime.date.today().isoformat(), who="urn:armepic:agent:updater_script").text = (
                    "Automatic update of ArmEpiC authority lists from DB."
                )
            return root
        except ET.ParseError:
            print(f"Warning: Could not parse {filepath}. Overwriting with new file.")
    
    return make_tei_root(xmlid_root, isArtsakh)

def make_tei_root(xmlid, isArtsakh=False):
    """Create a TEI root element with shared header."""
    TEI = ET.Element(
        "TEI",
        xmlns="http://www.tei-c.org/ns/1.0",
        xmlns_crm="http://www.cidoc-crm.org/cidoc-crm/",
        xmlns_tei="http://www.tei-c.org/ns/1.0",
        attrib={"xml:id": xmlid}
    )

    # Header
    header = ET.SubElement(TEI, "teiHeader")
    fileDesc = ET.SubElement(header, "fileDesc")

    # titleStmt
    titleStmt = ET.SubElement(fileDesc, "titleStmt")
    if isArtsakh:
        ET.SubElement(titleStmt, "title").text = f"ArtsakhEpiC - {xmlid} (hierarchical authority file for ArmEpiC / ArtsakhEpiC)"
    else:
        ET.SubElement(titleStmt, "title").text = f"ArmEpiC - {xmlid} (Authoritative Vocabulary for ArmEpiC)"

    resp = ET.SubElement(titleStmt, "respStmt")
    ET.SubElement(resp, "resp").text = "Compiled by"
    if isArtsakh:
        ET.SubElement(resp, "persName").text = "ArtsakhEpiC / EPFL Digital Humanities Laboratory (DHLAB)"
    else:
        ET.SubElement(resp, "persName").text = "ArmEpiC / EPFL Digital Humanities Laboratory (DHLAB)"

    # publicationStmt
    pub = ET.SubElement(fileDesc, "publicationStmt")
    if isArtsakh:
        ET.SubElement(pub, "authority").text = "ArtsakhEpiC - Armenian Epigraphic Corpus"
    else:
        ET.SubElement(pub, "authority").text = "ArmEpiC - Armenian Epigraphic Corpus"
    ET.SubElement(pub, "publisher").text = "EPFL Digital Humanities Laboratory (DHLAB)"
    ET.SubElement(pub, "pubPlace").text = "Lausanne"
    ET.SubElement(pub, "date", when="2025").text = "2025"
    avail = ET.SubElement(pub, "availability")
    ET.SubElement(avail, "licence", target="https://creativecommons.org/licenses/by/4.0/").text = "CC BY 4.0"

    # sourceDesc
    src = ET.SubElement(fileDesc, "sourceDesc")
    ET.SubElement(src, "p").text = """Shared authority file defining controlled vocabularies for all ArmEpiC subcorpora 
                    (ArmEpiC, ArtsakhEpiC, NoratusDiT etc.), harmonized with international standards 
                    (EAGLE, Getty AAT, CIDOC-CRM, PeriodO) and ready for ingestion into the 
                    European Cultural Heritage Cloud (CHC) / CIDROM infrastructure."""

    # revisionDesc
    rev = ET.SubElement(header, "revisionDesc")
    ET.SubElement(rev, "change", when=datetime.date.today().isoformat(), who="urn:armepic:agent:script").text = (
        "Automatic generation of ArmEpiC authority lists."
    )

    return TEI

def get_list_container(root, tag_name, xml_id_target):
    """Finds the specific list element (e.g. listPlace, listBibl) to update."""
    container = root.find(f".//*[@xml:id='{xml_id_target}']", NS)
    if container is None:
        text_node = root.find(".//tei:text", NS)
        if text_node is None:
            text_node = ET.SubElement(root, "text")
        body = text_node.find(".//tei:body", NS)
        if body is None:
            body = ET.SubElement(text_node, "body")
        
        container = ET.SubElement(body, tag_name, attrib={"xml:id": xml_id_target})
    return container

def update_mat_auth(filepath, rows):
    TEI = get_or_create_tei_root(filepath, "ArmEpiC_ListMaterial")
    lst = get_list_container(TEI, "list", "ArmEpiC_ListMaterial")
    if lst.get("type") != "material":
        lst.set("type", "material")

    existing_items = {item.attrib.get('{http://www.w3.org/XML/1998/namespace}id'): item for item in lst.findall("tei:item", NS)}

    standoff_relations = []

    for row in rows:
        xmlid = row.get("code")
        if not xmlid: continue

        aat = row.get("aat_uri")
        eagle = row.get("eagle_uri")
        matchtype = row.get("relation_type_eagle")
        if aat and eagle and matchtype:
            standoff_relations.append( (xmlid, aat, eagle, matchtype) )

        if xmlid in existing_items:
            item = existing_items[xmlid]
            item.clear() 
            item.set("xml:id", xmlid)
        else:
            item = ET.SubElement(lst, "item", attrib={"xml:id": xmlid})
        
        ET.SubElement(item, "idno", attrib={"type": "urn"}).text = f"urn:armepic:material:{xmlid}"
        if row.get("preflabel_hy"): ET.SubElement(item, "term", attrib={"xml:lang": "hy"}).text = row.get("preflabel_hy")
        if row.get("preflabel_en"): ET.SubElement(item, "term", attrib={"xml:lang": "en"}).text = row.get("preflabel_en")
        if row.get("description_hy"): ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = row.get("description_hy")
        if row.get("description_en"): ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = row.get("description_en")

    if standoff_relations:
        standOff = TEI.find(".//tei:standOff", NS)
        if standOff is None:
            standOff = ET.SubElement(TEI, "standOff")
        
        listRelation = standOff.find(".//tei:listRelation", NS)
        if listRelation is not None:
            standOff.remove(listRelation)
        
        listRelation = ET.SubElement(standOff, "listRelation")
        ET.SubElement(listRelation, "head").text = "Cross-references for materials"
        for mat_id, aat_uri, eagle_uri, matchtype in standoff_relations:
            ET.SubElement(listRelation, "relation", attrib={
                "name": matchtype,
                "active": f"urn:armepic:material:{mat_id}",
                "passive": aat_uri
            })
            ET.SubElement(listRelation, "relation", attrib={
                "name": matchtype,
                "active": f"urn:armepic:material:{mat_id}",
                "passive": eagle_uri
            })

    return TEI

def update_bibl_auth(filepath, rows):
    TEI = get_or_create_tei_root(filepath, "ArmEpiC_ListBibl")
    list_bibl = get_list_container(TEI, "listBibl", "ArmEpiC_ListBibl")
    if list_bibl.get("type") != "bibliographic":
        list_bibl.set("type", "bibliographic")

    existing_items = {item.attrib.get('{http://www.w3.org/XML/1998/namespace}id'): item for item in list_bibl.findall("tei:bibl", NS)}

    for row in rows:
        xmlid = row.get("bibl_id")
        if not xmlid: continue

        if xmlid in existing_items:
            bibl = existing_items[xmlid]
            bibl.clear()
            bibl.set("xml:id", xmlid)
        else:
            bibl = ET.SubElement(list_bibl, "bibl", attrib={"xml:id": xmlid})

        if row.get("authors"): ET.SubElement(bibl, "author").text = row.get("authors")
        if row.get("title"): ET.SubElement(bibl, "title", attrib={"xml:lang": "hy"}).text = row.get("title")
        if row.get("year"): ET.SubElement(bibl, "date", attrib={"when": row.get("year")}).text = row.get("year")
        if row.get("publisher"): ET.SubElement(bibl, "publisher").text = row.get("publisher")
        if row.get("place"): ET.SubElement(bibl, "pubPlace").text = row.get("place")
        if row.get("pages"): ET.SubElement(bibl, "note").text = f"Pages: {row.get('pages')}"
        if row.get("cited_in_inscriptions"): ET.SubElement(bibl, "idno", attrib={"type": "citedIn"}).text = row.get("cited_in_inscriptions")

    return TEI

def update_place_auth(filepath, rows):
    TEI = get_or_create_tei_root(filepath, "ArmEpiC_ListPlace", isArtsakh=True)
    lst = get_list_container(TEI, "listPlace", "Artsakh_ListPlace")

    existing_items = {item.attrib.get('{http://www.w3.org/XML/1998/namespace}id'): item for item in lst.findall("tei:place", NS)}

    for row in rows:
        idno = row.get("place_id")
        if not idno: continue

        if idno in existing_items:
            item = existing_items[idno]
            item.clear()
            item.set("xml:id", idno)
        else:
            item = ET.SubElement(lst, "place", attrib={"xml:id": idno})

        ET.SubElement(item, "idno", attrib={"type": "urn"}).text = f"urn:armepic:artsakh:plc:{idno}"
        plc = ET.SubElement(item, "place")
        
        if row.get("preferred_name_arm"): ET.SubElement(plc, "placeName", attrib={"xml:lang": "hy"}).text = row.get("preferred_name_arm")
        if row.get("preferred_name_rom_iso9985"): ET.SubElement(plc, "placeName", attrib={"xml:lang": "hy-Latn"}).text = row.get("preferred_name_rom_iso9985")
        if row.get("preferred_name_eng"): ET.SubElement(plc, "placeName", attrib={"xml:lang": "en"}).text = row.get("preferred_name_eng")
        
        altnames = row.get("alt_names_arm_semi")
        if altnames:
            for alt in altnames.split(";"):
                ET.SubElement(plc, "placeName", attrib={"type":"alt","xml:lang": "hy"}).text = alt.strip()
        
        altnameseng = row.get("alt_names_eng_semi")
        if altnameseng:
            for alt in altnameseng.split(";"):
                ET.SubElement(plc, "placeName", attrib={"type":"alt","xml:lang": "en"}).text = alt.strip()

        if row.get("place_type_en"): ET.SubElement(plc, "note", attrib={"type":"placeType","xml:lang": "en"}).text = row.get("place_type_en")
        if row.get("place_type_hy"): ET.SubElement(plc, "note", attrib={"type":"placeType","xml:lang": "hy"}).text = row.get("place_type_hy")
        
        if row.get("latitude") and row.get("longitude"):
            coords = ET.SubElement(plc, "note", attrib={"type":"coordinates"})
            ET.SubElement(coords, "geo").text = f"{row.get('latitude')} {row.get('longitude')}"
        
        if row.get("parent_place_id"):
            ET.SubElement(plc, "note", attrib={"type":"relation","target":f"urn:armepic:artsakh:plc:{row.get('parent_place_id')}"}).text = "partOf"
        
        if row.get("ext_wikidata"): ET.SubElement(plc, "idno", attrib={"type":"wikidata"}).text = row.get("ext_wikidata")
        if row.get("ext_geonames"): ET.SubElement(plc, "idno", attrib={"type":"geonames"}).text = row.get("ext_geonames")
        if row.get("ext_pleiades"): ET.SubElement(plc, "idno", attrib={"type":"pleiades"}).text = row.get("ext_pleiades")
        if row.get("time_from") and row.get("time_to"):
            ET.SubElement(plc, "note", attrib={"type":"chronology"}).text = f"{row.get('time_from')} - {row.get('time_to')}"
        if row.get("place_scope"):
            ET.SubElement(plc, "note", attrib={"type":"scope"}).text = row.get("place_scope")

    return TEI

def update_scripts_auth(filepath, rows):
    TEI = get_or_create_tei_root(filepath, "ArmEpiC_ListScripts")
    lst = get_list_container(TEI, "list", "ArmEpiC_ListScripts")
    if lst.get("type") != "script": lst.set("type", "script")

    existing_items = {item.attrib.get('{http://www.w3.org/XML/1998/namespace}id'): item for item in lst.findall("tei:item", NS)}

    for row in rows:
        idno = row.get("xml_id")
        if not idno: continue

        if idno in existing_items:
            item = existing_items[idno]
            item.clear()
            item.set("xml:id", idno)
        else:
            item = ET.SubElement(lst, "item", attrib={"xml:id": idno})

        ET.SubElement(item, "idno", attrib={"type": "uri"}).text = f"urn:armepic:script:{idno}"
        if row.get("term_hy"): ET.SubElement(item, "term", attrib={"xml:lang": "hy"}).text = row.get("term_hy")
        if row.get("term_en"): ET.SubElement(item, "term", attrib={"xml:lang": "en"}).text = row.get("term_en")
        if row.get("desc_hy"): ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = row.get("desc_hy")
        if row.get("desc_en"): ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = row.get("desc_en")
        if row.get("note_hy"): ET.SubElement(item, "note", attrib={"xml:lang": "hy"}).text = row.get("note_hy")
        if row.get("note_en"): ET.SubElement(item, "note", attrib={"xml:lang": "en"}).text = row.get("note_en")
        
        biblrefs = row.get("bibl_refs")
        if biblrefs:
            bibl_list = ET.SubElement(item, "listBibl")
            for bibl in biblrefs.split(";"):
                ET.SubElement(bibl_list, "bibl", attrib={"corresp": bibl.strip()})
    return TEI

def update_preserv_auth(filepath, rows):
    TEI = get_or_create_tei_root(filepath, "ArmEpiC_ListPreservation")
    lst = get_list_container(TEI, "list", "ArmEpiC_ListPreservation")
    if lst.get("type") != "preservation": lst.set("type", "preservation")

    existing_items = {item.attrib.get('{http://www.w3.org/XML/1998/namespace}id'): item for item in lst.findall("tei:item", NS)}

    for row in rows:
        idno = row.get("xml_id")
        if not idno: continue

        if idno in existing_items:
            item = existing_items[idno]
            item.clear()
            item.set("xml:id", idno)
        else:
            item = ET.SubElement(lst, "item", attrib={"xml:id": idno})

        if row.get("urn"): ET.SubElement(item, "idno", attrib={"type": "urn"}).text = row.get("urn")
        if row.get("term_hy"): ET.SubElement(item, "term", attrib={"xml:lang": "hy"}).text = row.get("term_hy")
        if row.get("term_en"): ET.SubElement(item, "term", attrib={"xml:lang": "en"}).text = row.get("term_en")
        if row.get("desc_hy"): ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = row.get("desc_hy")
        if row.get("desc_en"): ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = row.get("desc_en")

    return TEI

def update_monument_auth(filepath, rows):
    TEI = get_or_create_tei_root(filepath, "ArmEpiC_ListMonuments", isArtsakh=True)
    lst = get_list_container(TEI, "list", "ArmEpiC_ListMonuments")
    if lst.get("type") != "monument": lst.set("type", "monument")

    existing_items = {item.attrib.get('{http://www.w3.org/XML/1998/namespace}id'): item for item in lst.findall("tei:object", NS)}

    for row in rows:
        idno = row.get("auto_id")
        if not idno: continue

        if idno in existing_items:
            obj = existing_items[idno]
            obj.clear()
            obj.set("xml:id", idno)
        else:
            obj = ET.SubElement(lst, "object", attrib={"xml:id": idno})

        ET.SubElement(obj, "idno", attrib={"type": "urn"}).text = f"urn:armepic:mon:{idno}"
        
        if row.get("preferred_name_hy"): ET.SubElement(obj, "objectName", attrib={"xml:lang": "hy"}).text = row.get("preferred_name_hy")
        if row.get("preferred_name_rom_iso9985"): ET.SubElement(obj, "objectName", attrib={"xml:lang": "hy-Latn"}).text = row.get("preferred_name_rom_iso9985")
        if row.get("preferred_name_eng"): ET.SubElement(obj, "objectName", attrib={"xml:lang": "en"}).text = row.get("preferred_name_eng")
        
        if row.get("aralt_names_arm_semi"):
            for alt in row.get("aralt_names_arm_semi").split(";"):
                ET.SubElement(obj, "objectName", attrib={"type":"alt","xml:lang": "hy"}).text = alt.strip()
        if row.get("alt_names_eng_semi"):
            for alt in row.get("alt_names_eng_semi").split(";"):
                ET.SubElement(obj, "objectName", attrib={"type":"alt","xml:lang": "en"}).text = alt.strip()
        
        if row.get("type_armenian"): ET.SubElement(obj, "note", attrib={"type":"monumentType","xml:lang": "hy"}).text = row.get("type_armenian")
        if row.get("type_english"): ET.SubElement(obj, "note", attrib={"type":"monumentType","xml:lang": "en"}).text = row.get("type_english")
        
        if row.get("latitude") and row.get("longitude"):
            loc = ET.SubElement(obj, "location")
            ET.SubElement(loc, "geo").text = f"{row.get('latitude')} {row.get('longitude')}"
        
        if row.get("ext_wikidata"): ET.SubElement(obj, "idno", attrib={"type":"wikidata"}).text = row.get("ext_wikidata")
        if row.get("ext_geonames"): ET.SubElement(obj, "idno", attrib={"type":"geonames"}).text = row.get("ext_geonames")
        if row.get("ext_pleiades"): ET.SubElement(obj, "idno", attrib={"type":"pleiades"}).text = row.get("ext_pleiades")
        if row.get("ext_monumentwatch"): ET.SubElement(obj, "idno", attrib={"type":"monumentwatch"}).text = row.get("ext_monumentwatch")
        if row.get("ext_other"): ET.SubElement(obj, "idno", attrib={"type":"other"}).text = row.get("ext_other")
        
        if row.get("place_id"):
            ET.SubElement(obj, "note", attrib={"type":"relation","target":f"urn:armepic:artsakh:plc:{row.get('place_id')}"}).text = "locatedIn"
        if row.get("relations_parent"):
            ET.SubElement(obj, "note", attrib={"type":"relation","target":f"urn:armepic:mon:{row.get('relations_parent')}"}).text = "partOf"
    
    return TEI

def update_inscription_auth(filepath, rows):
    TEI = get_or_create_tei_root(filepath, "ArmEpiC_ListInscriptions")
    lst = get_list_container(TEI, "list", "ArmEpiC_ListInscriptions")
    if lst.get("type") != "inscription": lst.set("type", "inscription")

    existing_items = {item.attrib.get('{http://www.w3.org/XML/1998/namespace}id'): item for item in lst.findall("tei:term", NS)}

    for row in rows:
        idno = row.get("type_id")
        if not idno: continue

        if idno in existing_items:
            item = existing_items[idno]
            item.clear()
            item.set("xml:id", idno)
        else:
            item = ET.SubElement(lst, "term", attrib={"xml:id": idno})

        ET.SubElement(item, "idno", attrib={"type": "urn"}).text = f"urn:armepic:ist:{idno}"
        if row.get("preflabel_hy"): ET.SubElement(item, "termName", attrib={"xml:lang": "hy"}).text = row.get("preflabel_hy")
        if row.get("preflabel_en"): ET.SubElement(item, "termName", attrib={"xml:lang": "en"}).text = row.get("preflabel_en")
        if row.get("desc_hy"): ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = row.get("desc_hy")
        if row.get("desc_en"): ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = row.get("desc_en")
        
        if row.get("examples_local_ids_semi"):
            examples = ET.SubElement(item, "list", attrib={"type":"examples"})
            for ex in row.get("examples_local_ids_semi").split(";"):
                ET.SubElement(examples, "item").text = ex.strip()
        if row.get("notes"): ET.SubElement(item, "note").text = row.get("notes")

    return TEI

def update_object_auth(filepath, rows):
    TEI = get_or_create_tei_root(filepath, "ArmEpiC_ListObjectType")
    lst = get_list_container(TEI, "list", "ArmEpiC_ListObjectType")
    if lst.get("type") != "object": lst.set("type", "object")

    existing_items = {item.attrib.get('{http://www.w3.org/XML/1998/namespace}id'): item for item in lst.findall("tei:term", NS)}
    standoff_relations = []

    for row in rows:
        idno = row.get("code")
        if not idno: continue

        if row.get("exactmatch"): standoff_relations.append( (idno, row.get("exactmatch"), "exactMatch") )
        if row.get("closematch"): standoff_relations.append( (idno, row.get("closematch"), "closeMatch") )

        if idno in existing_items:
            item = existing_items[idno]
            item.clear()
            item.set("xml:id", idno)
        else:
            item = ET.SubElement(lst, "term", attrib={"xml:id": idno})

        ET.SubElement(item, "idno", attrib={"type": "urn"}).text = f"urn:armepic:object:{idno}"
        if row.get("preflabel_hy"): ET.SubElement(item, "termName", attrib={"xml:lang": "hy"}).text = row.get("preflabel_hy")
        if row.get("preflabel_en"): ET.SubElement(item, "termName", attrib={"xml:lang": "en"}).text = row.get("preflabel_en")
        if row.get("description_hy"): ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = row.get("description_hy")
        if row.get("description_en"): ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = row.get("description_en")
        if row.get("notes"): ET.SubElement(item, "note").text = row.get("notes")

    if standoff_relations:
        standOff = TEI.find(".//tei:standOff", NS)
        if standOff is None: standOff = ET.SubElement(TEI, "standOff")
        
        listRelation = standOff.find(".//tei:listRelation", NS)
        if listRelation is not None: standOff.remove(listRelation)
        
        listRelation = ET.SubElement(standOff, "listRelation")
        ET.SubElement(listRelation, "head").text = "Cross-references for object types"
        for obj_id, target_uri, matchtype in standoff_relations:
            ET.SubElement(listRelation, "relation", attrib={
                "name": matchtype,
                "active": f"urn:armepic:object:{obj_id}",
                "passive": target_uri
            })
    return TEI

def update_technique_auth(filepath, rows):
    TEI = get_or_create_tei_root(filepath, "ArmEpiC_ListTechniques")
    lst = get_list_container(TEI, "list", "ArmEpiC_ListTechniques")
    if lst.get("type") != "technique": lst.set("type", "technique")

    existing_items = {item.attrib.get('{http://www.w3.org/XML/1998/namespace}id'): item for item in lst.findall("tei:term", NS)}
    standoff_relations = []

    for row in rows:
        idno = row.get("code")
        if not idno: continue

        if row.get("exactmatch"): standoff_relations.append( (idno, row.get("exactmatch"), "exactMatch") )
        if row.get("closematch"): standoff_relations.append( (idno, row.get("closematch"), "closeMatch") )

        if idno in existing_items:
            item = existing_items[idno]
            item.clear()
            item.set("xml:id", idno)
        else:
            item = ET.SubElement(lst, "term", attrib={"xml:id": idno})

        ET.SubElement(item, "idno", attrib={"type": "urn"}).text = f"urn:armepic:technique:{idno}"
        if row.get("preflabel_hy"): ET.SubElement(item, "termName", attrib={"xml:lang": "hy"}).text = row.get("preflabel_hy")
        if row.get("preflabel_en"): ET.SubElement(item, "termName", attrib={"xml:lang": "en"}).text = row.get("preflabel_en")
        if row.get("description_hy"): ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = row.get("description_hy")
        if row.get("description_en"): ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = row.get("description_en")
        if row.get("notes"): ET.SubElement(item, "note").text = row.get("notes")

    if standoff_relations:
        standOff = TEI.find(".//tei:standOff", NS)
        if standOff is None: standOff = ET.SubElement(TEI, "standOff")
        
        listRelation = standOff.find(".//tei:listRelation", NS)
        if listRelation is not None: standOff.remove(listRelation)
        
        listRelation = ET.SubElement(standOff, "listRelation")
        ET.SubElement(listRelation, "head").text = "Cross-references for techniques"
        for tech_id, target_uri, matchtype in standoff_relations:
            ET.SubElement(listRelation, "relation", attrib={
                "name": matchtype,
                "active": f"urn:armepic:technique:{tech_id}",
                "passive": target_uri
            })
    return TEI

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--port", default="3306")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    # DB connection
    url = f"mysql+pymysql://{args.user}:{args.password}@{args.host}:{args.port}/{args.db}"
    engine = create_engine(url)

    # Ensure output directory exists
    os.makedirs(args.out, exist_ok=True)

    with engine.connect() as conn:

        # Material
        fname = os.path.join(args.out, "ArmEpiC_ListMaterial.xml")
        rows = conn.execute(text(f"SELECT * FROM listmat")).mappings().all()
        TEI = update_mat_auth(fname, rows)
        write_xml(TEI, fname)
        print("Material authority list updated.")

        # Bibl
        fname = os.path.join(args.out, "ArmEpiC_ListBibl.xml")
        rows = conn.execute(text(f"SELECT * FROM listbibl")).mappings().all()
        TEI = update_bibl_auth(fname, rows)
        write_xml(TEI, fname)
        print("Bibliographic authority list updated.")

        # Place
        fname = os.path.join(args.out, "ArmEpiC_ListPlace.xml")
        rows = conn.execute(text(f"SELECT * FROM listplaces")).mappings().all()
        TEI = update_place_auth(fname, rows)
        write_xml(TEI, fname)
        print("Place authority list updated.")

        # Scripts
        fname = os.path.join(args.out, "ArmEpiC_ListScripts.xml")
        rows = conn.execute(text(f"SELECT * FROM listscripts")).mappings().all()
        TEI = update_scripts_auth(fname, rows)
        write_xml(TEI, fname)
        print("Script authority list updated.")

        # Preservation
        fname = os.path.join(args.out, "ArmEpiC_ListPreservation.xml")
        rows = conn.execute(text(f"SELECT * FROM listpreserv")).mappings().all()
        TEI = update_preserv_auth(fname, rows)
        write_xml(TEI, fname)
        print("Preservation authority list updated.")

        # Monuments
        fname = os.path.join(args.out, "ArmEpiC_ListMonuments.xml")
        rows_monum = conn.execute(text(f"SELECT * FROM listmonum")).mappings().all()
        rows_submonum = conn.execute(text(f"SELECT * FROM listsubmonum")).mappings().all()
        TEI = update_monument_auth(fname, rows_monum + rows_submonum)
        write_xml(TEI, fname)
        print("Monument authority list updated.")

        # Inscriptions
        fname = os.path.join(args.out, "ArmEpiC_ListInscriptions.xml")
        rows = conn.execute(text(f"SELECT * FROM listinscr")).mappings().all()
        TEI = update_inscription_auth(fname, rows)
        write_xml(TEI, fname)
        print("Inscription type authority list updated.")

        # Objects
        fname = os.path.join(args.out, "ArmEpiC_ListObjectType.xml")
        rows = conn.execute(text(f"SELECT * FROM listobjs")).mappings().all()
        TEI = update_object_auth(fname, rows)
        write_xml(TEI, fname)
        print("Object type authority list updated.")

        # Techniques
        fname = os.path.join(args.out, "ArmEpiC_ListTechniques.xml")
        rows = conn.execute(text(f"SELECT * FROM listtechniques")).mappings().all()
        TEI = update_technique_auth(fname, rows)
        write_xml(TEI, fname)
        print("Technique authority list updated.")

if __name__ == "__main__":
    main()