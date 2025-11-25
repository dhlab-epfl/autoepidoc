#!/usr/bin/env python3
"""
mysql_to_authority_list.py

Generates TEI/EpiDoc-compliant authority lists from MySQL lookup tables.

Usage:
    python mysql_to_authority_list.py \
        --host 127.0.0.1 \
        --user etl_user \
        --password EtlUserPss \
        --db epidata \
        --out ./authlist

The script assumes the lookup table has (at least) the following columns:
    - code or xml_id
    - prefLabel_hy
    - prefLabel_en
    - description_hy
    - description_en
"""

import argparse
import os
from sqlalchemy import create_engine, text
import xml.etree.ElementTree as ET
from xml.dom import minidom
import datetime


def prettify(elem):
    if elem is None:
        return None
    rough = ET.tostring(elem, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")


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
        ET.SubElement(titleStmt, "title").text = f"ArtsakhEpiC – {xmlid} (hierarchical authority file for ArmEpiC / ArtsakhEpiC)"
    else:
        ET.SubElement(titleStmt, "title").text = f"ArmEpiC – {xmlid} (Authoritative Vocabulary for ArmEpiC)"

    resp = ET.SubElement(titleStmt, "respStmt")
    ET.SubElement(resp, "resp").text = "Compiled by"
    if isArtsakh:
        ET.SubElement(resp, "persName").text = "ArtsakhEpiC / EPFL Digital Humanities Laboratory (DHLAB)"
    else:
        ET.SubElement(resp, "persName").text = "ArmEpiC / EPFL Digital Humanities Laboratory (DHLAB)"

    # publicationStmt
    pub = ET.SubElement(fileDesc, "publicationStmt")
    if isArtsakh:
        ET.SubElement(pub, "authority").text = "ArtsakhEpiC – Armenian Epigraphic Corpus"
    else:
        ET.SubElement(pub, "authority").text = "ArmEpiC – Armenian Epigraphic Corpus"
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

def build_mat_auth(rows):
    TEI = make_tei_root("ArmEpiC_ListMaterial")
    text = ET.SubElement(TEI, "text")
    body = ET.SubElement(text, "body")

    lst = ET.SubElement(body, "list", attrib={"type": "material", "xml:id": "ArmEpiC_ListMaterial"})

    # tuple to hold standoff relations
    standoff_relations = []

    for row in rows:
        xmlid = row.get("code")
        en = row.get("preflabel_en")
        hy = row.get("preflabel_hy")
        desc_en = row.get("description_en")
        desc_hy = row.get("description_hy")
        aat = row.get("aat_uri")
        eagle = row.get("eagle_uri")
        matchtype = row.get("relation_type_eagle")

        if not xmlid:
            continue

        item = ET.SubElement(lst, "item", attrib={"xml:id": xmlid})
        ET.SubElement(item, "idno", attrib={"type": "urn"}).text = f"urn:armepic:material:{xmlid}"

        if hy:
            ET.SubElement(item, "term", attrib={"xml:lang": "hy"}).text = hy
        if en:
            ET.SubElement(item, "term", attrib={"xml:lang": "en"}).text = en

        if desc_hy:
            ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = desc_hy
        if desc_en:
            ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = desc_en
        # add them to a tuple for generation of standoff
        if aat and eagle and matchtype:
            standoff_relations.append( (xmlid, aat, eagle, matchtype) )

    if standoff_relations:
        standOff = ET.SubElement(TEI, "standOff")
        listRelation = ET.SubElement(standOff, "listRelation")
        ET.SubElement(listRelation, "head").text = "Cross-references for materials"
        for mat_id, aat_uri, eagle_uri, matchtype in standoff_relations:
            relation_aat = ET.SubElement(listRelation, "relation", attrib={
                "name": matchtype,
                "active": f"urn:armepic:material:{mat_id}",
                "passive": aat_uri
            })
            relation_eagle = ET.SubElement(listRelation, "relation", attrib={
                "name": matchtype,
                "active": f"urn:armepic:material:{mat_id}",
                "passive": eagle_uri
            })


    return TEI

def build_bibl_auth(rows):
    TEI = make_tei_root("ArmEpiC_ListBibl")
    text = ET.SubElement(TEI, "text")
    body = ET.SubElement(text, "body")
    list_bibl = ET.SubElement(body, "listBibl", attrib={"type": "bibliographic", "xml:id": "ArmEpiC_ListBibl"})
    for row in rows:
        xmlid = row.get("bibl_id")
        authors = row.get("authors")
        title = row.get("title")
        date = row.get("year")
        publisher = row.get("publisher")
        place = row.get("place")
        pages = row.get("pages")
        idno = row.get("cited_in_inscriptions")

        if not xmlid:
            continue
        bibl = ET.SubElement(list_bibl, "bibl", attrib={"xml:id": xmlid})
        if authors:
            ET.SubElement(bibl, "author").text = authors
        if title:
            ET.SubElement(bibl, "title", attrib={"xml:lang": "hy"}).text = title
        if date:
            ET.SubElement(bibl, "date", attrib={"when": date}).text = date
        if publisher:
            ET.SubElement(bibl, "publisher").text = publisher
        if place:
            ET.SubElement(bibl, "pubPlace").text = place
        if pages:
            ET.SubElement(bibl, "note").text = f"Pages: {pages}"
        if idno:
            ET.SubElement(bibl, "idno", attrib={"type": "citedIn"}).text = idno
    return TEI

def build_place_auth(rows):
    TEI = make_tei_root("ArmEpiC_ListPlace", isArtsakh=True)
    text = ET.SubElement(TEI, "text")
    body = ET.SubElement(text, "body")
    lst = ET.SubElement(body, "listPlace", attrib={"xml:id": "Artsakh_ListPlace"})

    for row in rows:
        idno = row.get("place_id")
        prefname = row.get("preferred_name_arm")
        prenamelat = row.get("preferred_name_rom_iso9985")
        prefnameen = row.get("preferred_name_eng")
        # alt names are separated by ;
        altnames = row.get("alt_names_arm_semi")
        altnameslist = altnames.split(";") if altnames else []
        altnameseng = row.get("alt_names_eng_semi")
        altnamesenglist = altnameseng.split(";") if altnameseng else []
        placetypeen = row.get("place_type_en")
        placetypearm = row.get("place_type_hy")
        lat = row.get("latitude")
        lon = row.get("longitude")
        rel = row.get("parent_place_id")
        wiki = row.get("ext_wikidata")
        geonames = row.get("ext_geonames")
        pleiades = row.get("ext_pleiades")
        fromtime = row.get("time_from")
        totime = row.get("time_to")

        scope = row.get("place_scope")

        if not idno:
            continue
        item = ET.SubElement(lst, "place", attrib={"xml:id": idno})
        ET.SubElement(item, "idno", attrib={"type": "urn"}).text = f"urn:armepic:artsakh:plc:{idno}"
        plc = ET.SubElement(item, "place")
        if prefname:
            ET.SubElement(plc, "placeName", attrib={"xml:lang": "hy"}).text = prefname
        if prenamelat:
            ET.SubElement(plc, "placeName", attrib={"xml:lang": "hy-Latn"}).text = prenamelat
        if prefnameen:
            ET.SubElement(plc, "placeName", attrib={"xml:lang": "en"}).text = prefnameen
        for alt in altnameslist:
            ET.SubElement(plc, "placeName", attrib={"type":"alt","xml:lang": "hy"}).text = alt.strip()
        for alt in altnamesenglist:
            ET.SubElement(plc, "placeName", attrib={"type":"alt","xml:lang": "en"}).text = alt.strip()
        if placetypeen:
            ET.SubElement(plc, "note", attrib={"type":"placeType","xml:lang": "en"}).text = placetypeen
        if placetypearm:
            ET.SubElement(plc, "note", attrib={"type":"placeType","xml:lang": "hy"}).text = placetypearm
        if lat and lon:
            coords = ET.SubElement(plc, "note", attrib={"type":"coordinates"})
            ET.SubElement(coords, "geo").text = f"{lat} {lon}"
        if rel:
            ET.SubElement(plc, "note", attrib={"type":"relation","target":f"urn:armepic:artsakh:plc:{rel}"}).text = "partOf"
        if wiki:
            ET.SubElement(plc, "idno", attrib={"type":"wikidata"}).text = wiki
        if geonames:
            ET.SubElement(plc, "idno", attrib={"type":"geonames"}).text = geonames
        if pleiades:
            ET.SubElement(plc, "idno", attrib={"type":"pleiades"}).text = pleiades
        if fromtime and totime:
            ET.SubElement(plc, "note", attrib={"type":"chronology"}).text = f"{fromtime} - {totime}"
        if scope:
            ET.SubElement(plc, "note", attrib={"type":"scope"}).text = scope
    return TEI

def build_scripts_auth(rows):
    TEI = make_tei_root("ArmEpiC_ListScripts")
    text = ET.SubElement(TEI, "text")
    body = ET.SubElement(text, "body")
    lst = ET.SubElement(body, "list", attrib={"type": "script", "xml:id": "ArmEpiC_ListScripts"})

    for row in rows:
        idno = row.get("xml_id")
        term_hy = row.get("term_hy")
        term_en = row.get("term_en")
        desc_hy = row.get("desc_hy")
        desc_en = row.get("desc_en")
        note_hy = row.get("note_hy")
        note_en = row.get("note_en")
        biblrefs = row.get("bibl_refs")
        listbiblrefs = biblrefs.split(";") if biblrefs else []

        if not idno:
            continue
        item = ET.SubElement(lst, "item", attrib={"xml:id": idno})
        ET.SubElement(item, "idno", attrib={"type": "uri"}).text = f"urn:armepic:script:{idno}"
        if term_hy:
            ET.SubElement(item, "term", attrib={"xml:lang": "hy"}).text = term_hy
        if term_en:
            ET.SubElement(item, "term", attrib={"xml:lang": "en"}).text = term_en
        if desc_hy:
            ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = desc_hy
        if desc_en:
            ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = desc_en
        if note_hy:
            ET.SubElement(item, "note", attrib={"xml:lang": "hy"}).text = note_hy
        if note_en:
            ET.SubElement(item, "note", attrib={"xml:lang": "en"}).text = note_en
        if listbiblrefs:
            bibl_list = ET.SubElement(item, "listBibl")
            for bibl in listbiblrefs:
                ET.SubElement(bibl_list, "bibl", attrib={"corresp": bibl.strip()})
    return TEI

def build_preserv_auth(rows):
    TEI = make_tei_root("ArmEpiC_ListPreservation")
    text = ET.SubElement(TEI, "text")
    body = ET.SubElement(text, "body")
    lst = ET.SubElement(body, "list", attrib={"type": "preservation", "xml:id": "ArmEpiC_ListPreservation"})

    for row in rows:
        idno = row.get("xml_id")
        urn = row.get("urn")
        term_hy = row.get("term_hy")
        term_en = row.get("term_en")
        desc_hy = row.get("desc_hy")
        desc_en = row.get("desc_en")

        if not idno:
            continue
        item = ET.SubElement(lst, "item", attrib={"xml:id": idno})
        if urn:
            ET.SubElement(item, "idno", attrib={"type": "urn"}).text = urn
        if term_hy:
            ET.SubElement(item, "term", attrib={"xml:lang": "hy"}).text = term_hy
        if term_en:
            ET.SubElement(item, "term", attrib={"xml:lang": "en"}).text = term_en
        if desc_hy:
            ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = desc_hy
        if desc_en:
            ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = desc_en
    return TEI

def build_monument_auth(rows):
    TEI = make_tei_root("ArmEpiC_ListMonuments", isArtsakh=True)
    text = ET.SubElement(TEI, "text")
    body = ET.SubElement(text, "body")
    lst = ET.SubElement(body, "list", attrib={"type": "monument", "xml:id": "ArmEpiC_ListMonuments"})


    for row in rows:
        idno = row.get("auto_id")
        type_en = row.get("type_english")
        type_hy = row.get("type_armenian")
        name_en = row.get("preferred_name_eng")
        name_hy = row.get("preferred_name_hy")
        name_rom = row.get("preferred_name_rom_iso9985")
        alt_names_en = row.get("alt_names_eng_semi")
        list_alt_names_en = alt_names_en.split(";") if alt_names_en else []
        alt_names_hy = row.get("aralt_names_arm_semi")
        list_alt_names_hy = alt_names_hy.split(";") if alt_names_hy else []
        lat = row.get("latitude")
        lon = row.get("longitude")
        wikidata = row.get("ext_wikidata")
        geonames = row.get("ext_geonames")
        pleiades = row.get("ext_pleiades")
        monumentwatch = row.get("ext_monumentwatch")
        extother = row.get("ext_other")
        place = row.get("place_id")
        relation = row.get("relations_parent")

        if not idno:
            continue
        obj = ET.SubElement(lst, "object", attrib={"xml:id": idno})
        ET.SubElement(obj, "idno", attrib={"type": "urn"}).text = f"urn:armepic:mon:{idno}"
        if name_hy:
            ET.SubElement(obj, "objectName", attrib={"xml:lang": "hy"}).text = name_hy
        if name_rom:
            ET.SubElement(obj, "objectName", attrib={"xml:lang": "hy-Latn"}).text = name_rom
        if name_en:
            ET.SubElement(obj, "objectName", attrib={"xml:lang": "en"}).text = name_en
        for alt in list_alt_names_hy:
            ET.SubElement(obj, "objectName", attrib={"type":"alt","xml:lang": "hy"}).text = alt.strip()
        for alt in list_alt_names_en:
            ET.SubElement(obj, "objectName", attrib={"type":"alt","xml:lang": "en"}).text = alt.strip()
        if type_hy:
            ET.SubElement(obj, "note", attrib={"type":"monumentType","xml:lang": "hy"}).text = type_hy
        if type_en:
            ET.SubElement(obj, "note", attrib={"type":"monumentType","xml:lang": "en"}).text = type_en
        if lat and lon:
            loc = ET.SubElement(obj, "location")
            ET.SubElement(loc, "geo").text = f"{lat} {lon}"
        if wikidata:
            ET.SubElement(obj, "idno", attrib={"type":"wikidata"}).text = wikidata
        if geonames:
            ET.SubElement(obj, "idno", attrib={"type":"geonames"}).text = geonames
        if pleiades:
            ET.SubElement(obj, "idno", attrib={"type":"pleiades"}).text = pleiades
        if monumentwatch:
            ET.SubElement(obj, "idno", attrib={"type":"monumentwatch"}).text = monumentwatch
        if extother:
            ET.SubElement(obj, "idno", attrib={"type":"other"}).text = extother
        if place:
            ET.SubElement(obj, "note", attrib={"type":"relation","target":f"urn:armepic:artsakh:plc:{place}"}).text = "locatedIn"
        if relation:
            ET.SubElement(obj, "note", attrib={"type":"relation","target":f"urn:armepic:mon:{relation}"}).text = "partOf"
    return TEI

def build_inscription_auth(rows):
    TEI = make_tei_root("ArmEpiC_ListInscriptions")
    text = ET.SubElement(TEI, "text")
    body = ET.SubElement(text, "body")
    lst = ET.SubElement(body, "list", attrib={"type": "inscription", "xml:id": "ArmEpiC_ListInscriptions"})

    for row in rows:
        idno = row.get("type_id")
        name_arm = row.get("preflabel_hy")
        name_eng = row.get("preflabel_en")
        desc_arm = row.get("desc_hy")
        desc_eng = row.get("desc_en")
        ex_locales = row.get("examples_local_ids_semi")
        list_ex_locales = ex_locales.split(";") if ex_locales else []
        notes = row.get("notes")

        if not idno:
            continue
        item = ET.SubElement(lst, "term", attrib={"xml:id": idno})
        ET.SubElement(item, "idno", attrib={"type": "urn"}).text = f"urn:armepic:ist:{idno}"
        if name_arm:
            ET.SubElement(item, "termName", attrib={"xml:lang": "hy"}).text = name_arm
        if name_eng:
            ET.SubElement(item, "termName", attrib={"xml:lang": "en"}).text = name_eng
        if desc_arm:
            ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = desc_arm
        if desc_eng:
            ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = desc_eng
        if list_ex_locales:
            examples = ET.SubElement(item, "list",attrib={"type":"examples"})
            for ex in list_ex_locales:
                ET.SubElement(examples, "item").text = ex.strip()
        if notes:
            ET.SubElement(item, "note").text = notes

    return TEI

def build_object_auth(rows):
    TEI = make_tei_root("ArmEpiC_ListObjectType")
    text = ET.SubElement(TEI, "text")
    body = ET.SubElement(text, "body")
    lst = ET.SubElement(body, "list", attrib={"type": "object", "xml:id": "ArmEpiC_ListObjectType"})

    standoff_relations = []

    for row in rows:
        idno = row.get("code")
        term_hy = row.get("preflabel_hy")
        term_en = row.get("preflabel_en")
        desc_hy = row.get("description_hy")
        desc_en = row.get("description_en")
        notes = row.get("notes")
        exactmatch = row.get("exactmatch")
        closematch = row.get("closematch")

        if not idno:
            continue
        item = ET.SubElement(lst, "term", attrib={"xml:id": idno})
        ET.SubElement(item, "idno", attrib={"type": "urn"}).text = f"urn:armepic:object:{idno}"
        if term_hy:
            ET.SubElement(item, "termName", attrib={"xml:lang": "hy"}).text = term_hy
        if term_en:
            ET.SubElement(item, "termName", attrib={"xml:lang": "en"}).text = term_en
        if desc_hy:
            ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = desc_hy
        if desc_en:
            ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = desc_en
        if notes:
            ET.SubElement(item, "note").text = notes
        if exactmatch:
            standoff_relations.append( (idno, exactmatch, "exactMatch") )
        if closematch:
            standoff_relations.append( (idno, closematch, "closeMatch") )
    if standoff_relations:
        print("Generating standoff relations for object types...")
        standOff = ET.SubElement(TEI, "standOff")
        listRelation = ET.SubElement(standOff, "listRelation")
        ET.SubElement(listRelation, "head").text = "Cross-references for object types"
        for obj_id, target_uri, matchtype in standoff_relations:
            relation = ET.SubElement(listRelation, "relation", attrib={
                "name": matchtype,
                "active": f"urn:armepic:object:{obj_id}",
                "passive": target_uri
            })
        
    return TEI

def build_technique_auth(rows):
    TEI = make_tei_root("ArmEpiC_ListTechniques")
    text = ET.SubElement(TEI, "text")
    body = ET.SubElement(text, "body")
    lst = ET.SubElement(body, "list", attrib={"type": "technique", "xml:id": "ArmEpiC_ListTechniques"})

    standoff_relations = []

    for row in rows:
        idno = row.get("code")
        term_hy = row.get("preflabel_hy")
        term_en = row.get("preflabel_en")
        desc_hy = row.get("description_hy")
        desc_en = row.get("description_en")
        notes = row.get("notes")
        exactmatch = row.get("exactmatch")
        closematch = row.get("closematch")
        if not idno:
            continue
        item = ET.SubElement(lst, "term", attrib={"xml:id": idno})
        ET.SubElement(item, "idno", attrib={"type": "urn"}).text = f"urn:armepic:technique:{idno}"
        if term_hy:
            ET.SubElement(item, "termName", attrib={"xml:lang": "hy"}).text = term_hy
        if term_en:
            ET.SubElement(item, "termName", attrib={"xml:lang": "en"}).text = term_en
        if desc_hy:
            ET.SubElement(item, "desc", attrib={"xml:lang": "hy"}).text = desc_hy
        if desc_en:
            ET.SubElement(item, "desc", attrib={"xml:lang": "en"}).text = desc_en
        if notes:
            ET.SubElement(item, "note").text = notes
        if exactmatch:
            standoff_relations.append( (idno, exactmatch, "exactMatch") )
        if closematch:
            standoff_relations.append( (idno, closematch, "closeMatch") )
    if standoff_relations:
        standOff = ET.SubElement(TEI, "standOff")
        listRelation = ET.SubElement(standOff, "listRelation")
        ET.SubElement(listRelation, "head").text = "Cross-references for techniques"
        for tech_id, target_uri, matchtype in standoff_relations:
            relation = ET.SubElement(listRelation, "relation", attrib={
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

    os.makedirs(args.out, exist_ok=True)

    with engine.connect() as conn:

        # Material authority list
        rows = conn.execute(text(f"SELECT * FROM listmat")).mappings().all()
        TEI_mat= build_mat_auth(rows)
        xml_bytes_mat = prettify(TEI_mat)
        # Write file in folder
        fname = os.path.join(args.out, "ArmEpiC_ListMaterial.xml")
        with open(fname, "wb") as f:
            f.write(xml_bytes_mat)
        print("Material authority list generated.")

        # Bibliographic authority list
        rows = conn.execute(text(f"SELECT * FROM listbibl")).mappings().all()
        TEI_bibl = build_bibl_auth(rows)
        xml_bytes_bibl = prettify(TEI_bibl)
        fname = os.path.join(args.out, "ArmEpiC_ListBibl.xml")
        with open(fname, "wb") as f:
            f.write(xml_bytes_bibl)
        print("Bibliographic authority list generated.")

        # Place authority list
        rows = conn.execute(text(f"SELECT * FROM listplaces")).mappings().all()
        TEI_place = build_place_auth(rows)
        xml_bytes_place = prettify(TEI_place)
        fname = os.path.join(args.out, "ArmEpiC_ListPlace.xml")
        with open(fname, "wb") as f:
            f.write(xml_bytes_place)
        print("Place authority list generated.")

        # Script authority list
        rows = conn.execute(text(f"SELECT * FROM listscripts")).mappings().all()
        TEI_scripts = build_scripts_auth(rows)
        xml_bytes_scripts = prettify(TEI_scripts)
        fname = os.path.join(args.out, "ArmEpiC_ListScripts.xml")
        with open(fname, "wb") as f:
            f.write(xml_bytes_scripts)
        print("Script authority list generated.")

        # Preservation authority list
        rows = conn.execute(text(f"SELECT * FROM listpreserv")).mappings().all()
        TEI_preserv = build_preserv_auth(rows)
        xml_bytes_preserv = prettify(TEI_preserv)
        fname = os.path.join(args.out, "ArmEpiC_ListPreservation.xml")
        with open(fname, "wb") as f:
            f.write(xml_bytes_preserv)
        print("Preservation authority list generated.")

        # Monument authority list (contains both listmonum and listsubmonum)
        rows_monum = conn.execute(text(f"SELECT * FROM listmonum")).mappings().all()
        rows_submonum = conn.execute(text(f"SELECT * FROM listsubmonum")).mappings().all()
        all_rows = rows_monum + rows_submonum
        TEI_monument = build_monument_auth(all_rows)
        xml_bytes_monument = prettify(TEI_monument)
        fname = os.path.join(args.out, "ArmEpiC_ListMonuments.xml")
        with open(fname, "wb") as f:
            f.write(xml_bytes_monument)
        print("Monument authority list generated.")

        # Inscription type authority list
        rows = conn.execute(text(f"SELECT * FROM listinscr")).mappings().all()
        TEI_inscription = build_inscription_auth(rows)
        xml_bytes_inscription = prettify(TEI_inscription)
        fname = os.path.join(args.out, "ArmEpiC_ListInscriptions.xml")
        with open(fname, "wb") as f:
            f.write(xml_bytes_inscription)
        print("Inscription type authority list generated.")

        # Object type authority list
        rows = conn.execute(text(f"SELECT * FROM listobjs")).mappings().all()
        TEI_object = build_object_auth(rows)
        xml_bytes_object = prettify(TEI_object)
        fname = os.path.join(args.out, "ArmEpiC_ListObjectType.xml")
        with open(fname, "wb") as f:
            f.write(xml_bytes_object)
        print("Object type authority list generated.")

        # Technique authority list
        rows = conn.execute(text(f"SELECT * FROM listtechniques")).mappings().all()
        TEI_technique = build_technique_auth(rows)
        xml_bytes_technique = prettify(TEI_technique)
        fname = os.path.join(args.out, "ArmEpiC_ListTechniques.xml")
        with open(fname, "wb") as f:
            f.write(xml_bytes_technique)
        print("Technique authority list generated.")
        
        



if __name__ == "__main__":
    main()
