#!/usr/bin/env python3
"""
export_epidoc.py

Query MySQL inscriptions and related metadata tables to export one EpiDoc (TEI) XML file per inscription.

Usage:
    python mysql_to_epidoc.py --host 127.0.0.1 --user databaseuser --password userpassword --db databasename --out ./output_folder

Notes:
- Adjust SQL queries if your column names differ from those used here.
"""

import os
import argparse
import re
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
from sqlalchemy import create_engine, text as sql_text
#import code in the helpers directory
from helpers.text_to_epidoc import dhv_to_epidoc
# --------------------------
# HELPER FUNCTIONS
# --------------------------

def prettify(elem):
    """
    Converts an XML ElementTree element into a pretty-printed XML string.
    Adds indentation and UTF-8 encoding for human readability.
    """
    rough_string = ET.tostring(elem, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8")



def build_epidoc(record, conn, authority):
    """
    Build an EpiDoc-compliant XML structure (TEI element) for a given inscription record.

    Args:
        record: A SQLAlchemy row mapping representing one inscription record.
        conn: Active SQLAlchemy connection object (used for additional queries).
        authority: String defining the authority or project responsible for the dataset.

    Returns:
        An XML ElementTree element representing the TEI root.
    """

    # Create the root <TEI> element with TEI namespace and attributes
    TEI = ET.Element("TEI", xmlns="http://www.tei-c.org/ns/1.0", attrib={"xml:lang": "en", "xmlns:space": "preserve"})

    # ------------------ TEI HEADER ------------------
    # The <teiHeader> contains metadata about the document
    teiHeader = ET.SubElement(TEI, "teiHeader")
    fileDesc = ET.SubElement(teiHeader, "fileDesc")

    # --- titleStmt: Titles and responsibility statements ---
    titleStmt = ET.SubElement(fileDesc, "titleStmt")
    ET.SubElement(titleStmt, "title", attrib={"xml:lang": "eng"}).text = "Placeholder for title of document in english (provided later)"
    ET.SubElement(titleStmt, "title", attrib={"xml:lang": "hy"}).text = "Արձանագրության վերնագիրը հայերեն"
    ET.SubElement(titleStmt, "respStmt").text = "Placeholder for responsibility statement"

    # --- editionStmt: Edition version and date ---
    editionStmt = ET.SubElement(fileDesc, "editionStmt")
    ET.SubElement(editionStmt, "edition", attrib={"xml:lang": "eng", "n": "1.0"}).text = f"First digital edition ({datetime.datetime.now().strftime('%Y-%m-%d')})"
    ET.SubElement(editionStmt, "edition", attrib={"xml:lang": "hy"}).text = f"Առաջին թվային հրատարակություն ({datetime.datetime.now().strftime('%Y-%m-%d')})"

    # --- publicationStmt: Authority, identifiers, and license info ---
    publicationStmt = ET.SubElement(fileDesc, "publicationStmt")
    ET.SubElement(publicationStmt, "authority", attrib={"xml:lang": "en"}).text = (
        "ArtsakhEpiC – Regional Corpus of Armenian Inscriptions from Artsakh, "
        "part of the ArmEpiC (Armenian Epigraphic Corpus) hosted by the EPFL Digital Humanities Laboratory (DHLAB)"
    )
    ET.SubElement(publicationStmt, "authority", attrib={"xml:lang": "hy"}).text = (
        "ԱրցախԷպիԿ (ArtsakhEpiC)՝ հայկական արձանագրությունների տարածաշրջանային հավաքածու, ընդգրկված ՀայԷպիԿ (ArmEpiC) համահայկական թվային կորպուսի մեջ, "
        "տեղակայված՝ Լոզանի Ֆեդերալ Պոլիտեխնիկական Ինստիտուտի Թվային Մարդաբանության Լաբորատորիայում (DHLAB)"
    )

    # Unique identifiers for the file and corpus
    ET.SubElement(publicationStmt, "idno", attrib={"type": "filename"}).text = f"{record['inscription_id']}.xml"
    ET.SubElement(publicationStmt, "idno", attrib={"type": "armepic"}).text = f"urn:armepic:artsakh:ins:{record['inscription_id']}"

    # License and access information
    availability = ET.SubElement(publicationStmt, "availability")
    ET.SubElement(availability, "license", attrib={"target": "https://creativecommons.org/licenses/by-nc/4.0/"}).text = "CC BY-NC 4.0"
    ET.SubElement(availability, "p", attrib={"xml:lang": "en"}).text = (
        "This record may be freely reused for non-commercial research and teaching purposes with proper attribution."
    )
    ET.SubElement(availability, "p", attrib={"xml:lang": "hy"}).text = (
        "Այս գրառումը կարելի է ազատորեն օգտագործել ոչ առևտրային հետազոտական և կրթական նպատակներով՝ պատշաճ հղմամբ։"
    )

    # --- sourceDesc: Description of source manuscripts and collections ---
    sourceDesc = ET.SubElement(fileDesc, "sourceDesc")
    ET.SubElement(sourceDesc, "collection", attrib={"xml:id": "urn:armepic:coll:artsakhepic", "xml:lang": "en"}).text = "ArtsakhEpiC – Corpus of Armenian Inscriptions from Artsakh"
    ET.SubElement(sourceDesc, "collection", attrib={"xml:id": "urn:armepic:coll:armepic", "xml:lang": "en"}).text = "ArmEpiC – Armenian Epigraphic Corpus"
    msDesc = ET.SubElement(sourceDesc, "msDesc")

    # --- msIdentifier: Monument or sub-monument information ---
    msIdentifier = ET.SubElement(msDesc, "msIdentifier")
    repository = ET.SubElement(msIdentifier, "repository", attrib={"ref": f"urn:armepic:mon:{record['monument_id']}"})

    # Query for monument metadata
    mon_res = conn.execute(sql_text("SELECT preferred_name_eng, preferred_name_hy FROM listmonum WHERE auto_id = :mid"),
                           {"mid": record.get("monument_id") or ""})
    mon = mon_res.mappings().fetchone()
    if mon and mon.get("preferred_name_eng"):
        ET.SubElement(repository, "objectName", attrib={"xml:lang": "en"}).text = mon["preferred_name_eng"]
        # Assign XML ID based on monument name
        msDesc.set("xml:id", f"ms_{mon['preferred_name_eng'].replace(' ', '_').replace('/', '').replace('(', '').replace(')', '')}")
    if mon and mon.get("preferred_name_hy"):
        ET.SubElement(repository, "objectName", attrib={"xml:lang": "hy"}).text = mon["preferred_name_hy"]

    # --- Sub-monument information ---
    msPart = ET.SubElement(msDesc, "msPart")
    msIdentifier2 = ET.SubElement(msPart, "msIdentifier")
    repo2 = ET.SubElement(msIdentifier2, "repository", attrib={"ref": f"urn:armepic:mon:{record['sub_monument__id']}"})
    submon_res = conn.execute(sql_text("SELECT preferred_name_eng, preferred_name_arm FROM listsubmonum WHERE auto_id = :smid"),
                              {"smid": record.get("sub_monument__id") or ""})
    submon = submon_res.mappings().fetchone()
    if submon and submon.get("preferred_name_eng"):
        ET.SubElement(repo2, "objectName", attrib={"xml:lang": "en"}).text = submon["preferred_name_eng"]
        msPart.set("xml:id", f"ms_{submon['preferred_name_eng'].replace(' ', '_').replace('/', '').replace('(', '').replace(')', '')}")
    if submon and submon.get("preferred_name_arm"):
        ET.SubElement(repo2, "objectName", attrib={"xml:lang": "hy"}).text = submon["preferred_name_arm"]

    # --- Physical Description Section (materials, object type, technique, etc.) ---
    physDesc = ET.SubElement(msDesc, "physDesc")
    objectDesc = ET.SubElement(physDesc, "objectDesc")
    supportDesc = ET.SubElement(objectDesc, "supportDesc")
    support = ET.SubElement(supportDesc, "support")

    # Query for object type (e.g., stele, khachkar, tombstone)
    obj_res = conn.execute(sql_text("SELECT prefLabel_en, prefLabel_hy FROM listobjs WHERE code = :oid"),
                           {"oid": record["object_id"]})
    obj = obj_res.mappings().fetchone()
    if obj and obj.get("prefLabel_en"):
        ET.SubElement(support, "objectType", attrib={"ref": f"urn:armepic:objecttype:{record['object_id']}", "xml:lang": "en"}).text = obj["prefLabel_en"]
    if obj and obj.get("prefLabel_hy"):
        ET.SubElement(support, "objectType", attrib={"xml:lang": "hy"}).text = obj["prefLabel_hy"]

    # Query for material (e.g., basalt, limestone)
    mat_res = conn.execute(sql_text("SELECT prefLabel_en, prefLabel_hy FROM listmat WHERE code = :code"),
                           {"code": record["material_id"]})
    mat = mat_res.mappings().fetchone()
    if mat and mat.get("prefLabel_en"):
        ET.SubElement(support, "material", attrib={"ref": f"urn:armepic:material:{record['material_id']}", "xml:lang": "en"}).text = mat["prefLabel_en"]
    if mat and mat.get("prefLabel_hy"):
        ET.SubElement(support, "material", attrib={"xml:lang": "hy"}).text = mat["prefLabel_hy"]

    # Query for technique (e.g., engraved, painted)
    tech_res = conn.execute(sql_text("SELECT prefLabel_en, prefLabel_hy FROM listtechniques WHERE code = :code"),
                            {"code": record["technique_id"]})
    tech = tech_res.mappings().fetchone()
    if tech and tech.get("prefLabel_en"):
        ET.SubElement(support, "rs", attrib={"type": "technique", "ref": f"urn:armepic:technique:{record['technique_id']}", "xml:lang": "en"}).text = tech["prefLabel_en"]
    if tech and tech.get("prefLabel_hy"):
        ET.SubElement(support, "rs", attrib={"type": "technique", "xml:lang": "hy"}).text = tech["prefLabel_hy"]

    # Query for condition / preservation state
    if record.get("condition_hy"):
        condelem = ET.SubElement(supportDesc, "condition")
        cond = conn.execute(sql_text("SELECT desc_hy, desc_en FROM listpreserv WHERE xml_id = :code"),
                            {"code": record["condition_hy"]})
        cond_res = cond.mappings().fetchone()
        if cond_res and cond_res.get("desc_en"):
            ET.SubElement(condelem, "p", attrib={"xml:lang": "en"}).text = cond_res["desc_en"]
        if cond_res and cond_res.get("desc_hy"):
            ET.SubElement(condelem, "p", attrib={"xml:lang": "hy"}).text = cond_res["desc_hy"]

    # Layout (e.g., line arrangement or writing format)
    layoutDesc = ET.SubElement(objectDesc, "layoutDesc")
    ET.SubElement(layoutDesc, "layout", attrib={"xml:lang": "hy"}).text = record.get("layout_text_hy") or ""
    ET.SubElement(layoutDesc, "layout", attrib={"xml:lang": "eng"}).text = record.get("layout_text_en") or ""

    # Script or handwriting description
    handDesc = ET.SubElement(physDesc, "handDesc")
    handNote = ET.SubElement(handDesc, "handNote", attrib={"xml:id": f"hand_{record['inscription_id']}", "scriptRef": f"urn:armepic:script:{record['script_id']}"})
    scriptRes = conn.execute(sql_text("SELECT term_en, term_hy FROM listscripts WHERE xml_id = :code"),
                             {"code": record["script_id"]})
    script = scriptRes.mappings().fetchone()
    if script and script.get("term_en"):
        ET.SubElement(handNote, "term", attrib={"xml:lang": "en"}).text = script["term_en"]
    if script and script.get("term_hy"):
        ET.SubElement(handNote, "term", attrib={"xml:lang": "hy"}).text = script["term_hy"]

    # --- History: provenance, origin place, and dating ---
    history = ET.SubElement(msDesc, "history")
    origin = ET.SubElement(history, "origin")
    origPlace = ET.SubElement(origin, "origPlace")
    placeName = ET.SubElement(origPlace, "placeName", attrib={"ref": f"urn:armepic:place:{record['place_geo']}"})

    # Query place of origin
    plc_res = conn.execute(sql_text("SELECT preferred_name_arm, preferred_name_eng FROM listplaces WHERE place_id = :pid"),
                           {"pid": record["place_geo"] or ""})
    plc = plc_res.mappings().fetchone()
    if plc and plc.get("preferred_name_eng"):
        ET.SubElement(placeName, "name", attrib={"xml:lang": "eng"}).text = plc["preferred_name_eng"]
    if plc and plc.get("preferred_name_arm"):
        ET.SubElement(placeName, "name", attrib={"xml:lang": "hy"}).text = plc["preferred_name_arm"]

    # Date fields in Armenian and Gregorian calendars
    origDate = ET.SubElement(origin, "origDate")
    if record.get("date_display_according_to_armenain_era"):
        ET.SubElement(origDate, "date", attrib={"calendar": "#cal_armenian", "when": record.get("date_display_according_to_armenain_era")}).text = record["date_display_according_to_armenain_era"]
    if record.get("date_display_en"):
        ET.SubElement(origDate, "date", attrib={"calendar": "#cal_gregorian", "when": record.get("date_display_en")}).text = record["date_display_en"]

    # Provenance: find and current observation places
    if record.get("place_find"):
        prov = ET.SubElement(history, "provenance", attrib={"type": "found"})
        placeFind = ET.SubElement(prov, "placeName", attrib={"ref": f"urn:armepic:place:{record['place_find']}"})
        plc2_res = conn.execute(sql_text("SELECT preferred_name_hy, preferred_name_eng FROM listmonum WHERE auto_id = :pid"),
                                {"pid": record["place_find"] or ""})
        plc2 = plc2_res.mappings().fetchone()
        prov2 = ET.SubElement(history, "provenance", attrib={"type": "observed"})
        placeObs = ET.SubElement(prov2, "placeName", attrib={"ref": f"urn:armepic:place:{record['place_find']}"})
        if plc2 and plc2.get("preferred_name_eng"):
            ET.SubElement(placeFind, "name", attrib={"xml:lang": "en"}).text = plc2["preferred_name_eng"]
            ET.SubElement(placeObs, "name", attrib={"xml:lang": "en"}).text = plc2["preferred_name_eng"]
        if plc2 and plc2.get("preferred_name_hy"):
            ET.SubElement(placeFind, "name", attrib={"xml:lang": "hy"}).text = plc2["preferred_name_hy"]
            ET.SubElement(placeObs, "name", attrib={"xml:lang": "hy"}).text = plc2["preferred_name_hy"]

    # --- Profile Description (keywords and classification) ---
    profileDesc = ET.SubElement(teiHeader, "profileDesc")
    textClass = ET.SubElement(profileDesc, "textClass")
    keywords = ET.SubElement(textClass, "keywords")

    insctype_res = conn.execute(sql_text("SELECT prefLabel_en, prefLabel_hy FROM listinscr WHERE type_id = :tid"),
                                {"tid": record["inscription_type"]})
    insctype = insctype_res.mappings().fetchone()
    if insctype and insctype.get("prefLabel_en"):
        ET.SubElement(keywords, "term", attrib={"xml:lang": "en", "ref": f"urn:armepic:inscriptiontype:{record['inscription_type']}"}).text = insctype["prefLabel_en"]
    if insctype and insctype.get("prefLabel_hy"):
        ET.SubElement(keywords, "term", attrib={"xml:lang": "hy"}).text = insctype["prefLabel_hy"]

    # --- Facsimile (image and drawing references) ---
    facsimile = ET.SubElement(TEI, "facsimile")
    surface = ET.SubElement(facsimile, "surface", attrib={"xml:id": f"surf_{record['inscription_id']}"})
    list_bibls = []
    if record.get("bibliography"):
        list_bibls = [b.strip() for b in record["bibliography"].split(";") if b.strip()]
    n = 1
    for bibl in list_bibls:
        bibltype = conn.execute(sql_text("SELECT type FROM listbibl WHERE bibl_id = :code"), {"code": bibl})
        bibltype_res = bibltype.mappings().fetchone()
        ET.SubElement(surface, "graphic", attrib={
            "n": str(n),
            "source": f"urn:armepic:bibl:{bibl}",
            "ana": bibltype_res["type"] if bibltype_res and bibltype_res.get("type") else 'other'
        })
        n += 1

    # --- Text body: edition, commentary, and bibliography ---
    text = ET.SubElement(TEI, "text")
    body = ET.SubElement(text, "body")

    # Edition (main textual content placeholder)
    edition = ET.SubElement(body, "div", attrib={"type": "edition"})
    gentext = dhv_to_epidoc(record.get("text_t", ""))
    edition.append(gentext)

    # Commentary (bilingual descriptive text)
    commentary = ET.SubElement(body, "div", attrib={"type": "commentary"})
    if record.get("description_hy"):
        ET.SubElement(commentary, "p", attrib={"xml:lang": "hy"}).text = record["description_hy"]
    if record.get("description_en"):
        ET.SubElement(commentary, "p", attrib={"xml:lang": "en"}).text = record["description_en"]

    # Bibliography references
    bibliography = ET.SubElement(body, "div", attrib={"type": "bibliography"})
    listBibl = ET.SubElement(bibliography, "listBibl")

    # Query references citing this inscription
    bibl_rows = conn.execute(sql_text("SELECT title, authors, year FROM listbibl "
                                      "WHERE FIND_IN_SET(:iid, cited_in_inscriptions)"),
                             {"iid": record["inscription_id"]}).fetchall()
    for b in bibl_rows:
        ET.SubElement(listBibl, "bibl").text = f"{b['authors']} ({b['year']}): {b['title']}"

    return TEI


def main():
    """
    Main execution function:
    - Parses command-line arguments
    - Connects to the MySQL database
    - Iterates over inscription records
    - Builds and writes EpiDoc XML files for each entry
    """
    parser = argparse.ArgumentParser(description="Export inscriptions from MySQL into EpiDoc XML files.")
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="3306")
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", default="./epidoc_xml")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--authority", default="ArmEpic - digital collection of armenian epigraphic inscriptions")
    args = parser.parse_args()

    # XML model header for EpiDoc validation
    header = '''<?xml-model href="https://www.stoa.org/epidoc/schema/9.7/tei-epidoc.rng"
            type="application/xml"
            schematypens="http://relaxng.org/ns/structure/1.0"?>
        <?xml-model href="https://www.stoa.org/epidoc/schema/9.7/tei-epidoc.rng"
            type="application/xml"
            schematypens="http://purl.oclc.org/dsdl/schematron"?>\n'''

    # Ensure output directory exists
    os.makedirs(args.out, exist_ok=True)

    # Create SQLAlchemy connection to MySQL
    engine_url = f"mysql+pymysql://{args.user}:{args.password}@{args.host}:{args.port}/{args.db}"
    engine = create_engine(engine_url)

    # Execute query and process each inscription record
    with engine.connect() as conn:
        result = conn.execute(sql_text(f"SELECT * FROM epigraphysamples LIMIT {args.limit}"))
        for row in result.mappings():
            tei = build_epidoc(row, conn, args.authority)
            xml_str = prettify(tei)


            # Remove the XML declaration from minidom output and prepend EpiDoc model header
            xml_text = re.sub(r'^\s*<\?xml[^>]*\?>\s*', '', xml_str.decode("utf-8"), count=1)
            # Clean up line break tags followed by newlines/whitespace
            xml_text = re.sub(r'<lb([^>]*)/>\s*\n\s*', r'<lb\1/>', xml_text)
            out_text = (header + xml_text).encode("utf-8")

            # Write to XML file named after the inscription ID
            fname = os.path.join(args.out, f"{row['inscription_id']}.xml")
            with open(fname, "wb") as f:
                f.write(out_text)
            print(f"Exported {fname}")


if __name__ == "__main__":
    main()
