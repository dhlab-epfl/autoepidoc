#!/usr/bin/env python3
"""
export_epidoc.py

Query MySQL inscriptions+places and export one EpiDoc (TEI) XML per inscription.

Usage:
    python mysql_to_epidoc.py --host 127.0.0.1 --user etl_user --password EtlUserPss --db mydata --out ./epidoc_output

Notes:
- Requires pymysql and lxml: pip install pymysql lxml
- Adjust SQL if your column names differ exactly from those used here.
"""

import os
import argparse
import pymysql
from lxml import etree
from datetime import datetime


def safe_text(x):
    """Return string or None; strip whitespace."""
    if x is None:
        return None
    s = str(x).strip()
    return s if s != '' else None

def make_idno_element(type_, text):
    if not text:
        return None
    el = etree.Element("idno")
    el.set("type", type_)
    el.text = text
    return el

def append_if_not_none(parent, element):
    if element is not None:
        parent.append(element)

def tei_element(tag, nsmap=None):
    return etree.Element(tag, nsmap=nsmap)

def create_tei_tree(row):
    """
    Create a TEI (EpiDoc-style) XML tree from a DB row (dict-like).
    Assumes row fields correspond to names in the SELECT below.
    """
    NS = "http://www.tei-c.org/ns/1.0"
    nsmap = {None: NS}
    TEI = etree.Element("{%s}TEI" % NS, nsmap=nsmap)

    # -- teiHeader --
    teiHeader = etree.SubElement(TEI, "{%s}teiHeader" % NS)
    fileDesc = etree.SubElement(teiHeader, "{%s}fileDesc" % NS)
    titleStmt = etree.SubElement(fileDesc, "{%s}titleStmt" % NS)

    # title: use inventory_no or a constructed title
    title_text = safe_text(row.get("inventory_no")) or f"Inscription {row.get('inscription_id')}"
    title = etree.SubElement(titleStmt, "{%s}title" % NS)
    title.text = title_text

    # publicationStmt: include inventory id and external IDs
    publicationStmt = etree.SubElement(fileDesc, "{%s}publicationStmt" % NS)
    append_if_not_none(publicationStmt, make_idno_element("inventory", safe_text(row.get("inventory_no"))))
    append_if_not_none(publicationStmt, make_idno_element("inscription_id", safe_text(row.get("inscription_id"))))

    # external identifiers from place (if present)
    for ext_key, ext_type in [
        ("ext_wikidata", "wikidata"),
        ("ext_geonames", "geonames"),
        ("ext_pleiades", "pleiades"),
        ("ext_other", "other")
    ]:
        val = safe_text(row.get(ext_key)) or safe_text(row.get("place_" + ext_key))
        if val:
            idno = etree.SubElement(publicationStmt, "{%s}idno" % NS)
            idno.set("type", ext_type)
            idno.text = val

    # sourceDesc with place info
    sourceDesc = etree.SubElement(fileDesc, "{%s}sourceDesc" % NS)
    msDesc = etree.SubElement(sourceDesc, "{%s}msDesc" % NS)  # using msDesc generically

    msIdentifier = etree.SubElement(msDesc, "{%s}msIdentifier" % NS)
    # place (use place fields)
    place_fields = {
        "place_id": "place_id",
        "place_type_en": "place_type_en",
        "place_type_hy": "place_type_hy",
        "preferred_name_arm": "preferred_name_arm",
        "preferred_name_rom_iso9985": "preferred_name_rom_iso9985",
        "preferred_name_eng": "preferred_name_eng",
        "alt_names_arm_semi": "alt_names_arm_semi",
        "alt_names_eng_semi": "alt_names_eng_semi",
        "Latitude": "Latitude",
        "Longitude": "Longitude",
        "parent_place_id": "parent_place_id",
        "place_scope": "place_scope",
        "time_from": "time_from",
        "time_to": "time_to"
    }

    # represent place with settlement/country elements where appropriate
    # simple approach: put preferred_name fields into <settlement> and <region> if available
    settlement_text = safe_text(row.get("preferred_name_eng")) or safe_text(row.get("preferred_name_arm")) or safe_text(row.get("preferred_name_rom_iso9985"))
    if settlement_text:
        settlement = etree.SubElement(msIdentifier, "{%s}settlement" % NS)
        settlement.text = settlement_text

    # coordinates: use <geo> element if lat/lon available
    lat = safe_text(row.get("Latitude"))
    lon = safe_text(row.get("Longitude"))
    if lat or lon:
        geo = etree.SubElement(msIdentifier, "{%s}geo" % NS)
        if lat:
            lat_el = etree.SubElement(geo, "{%s}lat" % NS)
            lat_el.text = lat
        if lon:
            lon_el = etree.SubElement(geo, "{%s}long" % NS)
            lon_el.text = lon

    # place id numeric
    place_id = safe_text(row.get("place_id"))
    if place_id:
        pid = etree.SubElement(msIdentifier, "{%s}idno" % NS)
        pid.set("type", "place_id")
        pid.text = place_id

    # add alternative names as notes if present
    alt_arm = safe_text(row.get("alt_names_arm_semi"))
    if alt_arm:
        note = etree.SubElement(msDesc, "{%s}note" % NS)
        note.set("type", "alt_names_arm")
        note.text = alt_arm
    alt_eng = safe_text(row.get("alt_names_eng_semi"))
    if alt_eng:
        note2 = etree.SubElement(msDesc, "{%s}note" % NS)
        note2.set("type", "alt_names_eng")
        note2.text = alt_eng

    # dates for the place (if any)
    time_from = safe_text(row.get("time_from"))
    time_to = safe_text(row.get("time_to"))
    if time_from or time_to:
        history = etree.SubElement(msDesc, "{%s}history" % NS)
        if time_from:
            orig = etree.SubElement(history, "{%s}orig" % NS)
            orig.text = f"place_time_from: {time_from}"
        if time_to:
            change = etree.SubElement(history, "{%s}change" % NS)
            change.text = f"place_time_to: {time_to}"

    # -- fileDesc done. now profileDesc (optional) --
    profileDesc = etree.SubElement(teiHeader, "{%s}profileDesc" % NS)
    # we can add language info from inscription
    lang = safe_text(row.get("language"))
    if lang:
        langUsage = etree.SubElement(profileDesc, "{%s}langUsage" % NS)
        language_el = etree.SubElement(langUsage, "{%s}language" % NS)
        language_el.set("ident", lang)
        language_el.text = lang

    # -- textual body --
    text = etree.SubElement(TEI, "{%s}text" % NS)
    body = etree.SubElement(text, "{%s}body" % NS)

    # main edition/transcription; place Armenian or original language in @xml:lang where possible
    edition_div = etree.SubElement(body, "{%s}div" % NS)
    edition_div.set("type", "edition")
    lang_attr = safe_text(row.get("language"))
    if lang_attr:
        edition_div.set("{http://www.w3.org/XML/1998/namespace}lang", lang_attr)

    # layout_text or primary transcription fields
    primary_text = safe_text(row.get("layout_text")) or safe_text(row.get("Text_T")) or safe_text(row.get("Text_Interpretitve_Arm")) or safe_text(row.get("Text_Moder_Armenain"))
    if primary_text:
        # naive: split on newline and use <lb/> to mark line breaks
        # create a <ab> (anonymous block) for the inscription text
        ab = etree.SubElement(edition_div, "{%s}ab" % NS)
        lines = primary_text.splitlines()
        for idx, line in enumerate(lines, start=1):
            # create text and an lb element between lines
            # Put the line content then an <lb n="..."/> (EpiDoc often uses <lb/> within line)
            # We'll append line text as a text node and then an lb (separating lines)
            if idx == 1:
                # first text node
                if line.strip():
                    ab.text = line
                else:
                    ab.text = ""
            else:
                # after previous element, tail text
                # create an lb
                lb = etree.SubElement(ab, "{%s}lb" % NS)
                lb.set("n", str(idx))
                # set the tail (text after lb)
                lb.tail = line

    # Add a separate div for translation in English if date_display_en or other translation present
    translation_text = safe_text(row.get("date_display_en"))
    if translation_text:
        trans_div = etree.SubElement(body, "{%s}div" % NS)
        trans_div.set("type", "translation")
        trans_div.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        p = etree.SubElement(trans_div, "{%s}p" % NS)
        p.text = translation_text

    # Add bibliographic info if present
    bibl = safe_text(row.get("Bibliography"))
    if bibl:
        notesStmt = etree.SubElement(fileDesc, "{%s}notesStmt" % NS)
        note_bib = etree.SubElement(notesStmt, "{%s}note" % NS)
        note_bib.set("type", "bibliography")
        note_bib.text = bibl

    # add some inscription metadata as notes
    meta_fields = [
        ("date_not_before", "date_not_before"),
        ("date_not_after", "date_not_after"),
        ("dating_certainty", "dating_certainty"),
        ("material_id", "material"),
        ("technique_id", "technique"),
        ("inscription_type", "inscription_type"),
        ("condition", "condition"),
        ("dimensions_json", "dimensions")
    ]
    if any(safe_text(row.get(f)) for f, _ in meta_fields):
        profile_notes = etree.SubElement(teiHeader, "{%s}encodingDesc" % NS)
        for dbfield, note_type in meta_fields:
            val = safe_text(row.get(dbfield)) or safe_text(row.get(dbfield.replace("_id"," ID")))
            if val:
                note = etree.SubElement(profile_notes, "{%s}note" % NS)
                note.set("type", note_type)
                note.text = val

    # return ElementTree
    return etree.ElementTree(TEI)


# ---- Main ----

def main(args):
    # connect to DB
    conn = pymysql.connect(
        host=args.host,
        user=args.user,
        password=args.password,
        database=args.db,
        port=int(args.port),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

    # SQL: select inscription fields plus place fields (joined on place_find)
    # Adjust column names if they differ (use backticks if necessary)
    sql = """
    SELECT
      i.inscription_id,
      i.inventory_no,
      i.monument_id,
      i.sub_monument__id,
      i.place_original,
      i.place_find,
      i.place_geo,
      i.date_not_before,
      i.date_not_after,
      i.date_display_hy,
      i.date_display_en,
      i.dating_certainty,
      i.language,
      i.script_id,
      i.material_id AS material_id,
      i.technique_id AS technique_id,
      i.inscription_type,
      i.condition,
      i.dimensions_json,
      i.description,
      i.workflow_status,
      i.created_at,
      i.updated_at,
      i.layout_text,
      i.text_t,
      i.text_interpretitve_arm,
      i.text_moder_armenain,
      i.photo_credit,
      i.image_master_path,
      i.drawing_reference,
      i.drawing_master_path,
      i.bibliography,

      -- place fields (from places table)
      p.place_id,
      p.place_type_en,
      p.place_type_hy,
      p.preferred_name_arm,
      p.preferred_name_rom_iso9985,
      p.preferred_name_eng,
      p.alt_names_arm_semi,
      p.alt_names_eng_semi,
      p.Latitude,
      p.Longitude,
      p.parent_place_id,
      p.ext_wikidata,
      p.ext_geonames,
      p.ext_pleiades,
      p.ext_other,
      p.place_scope,
      p.time_from,
      p.time_to

    FROM `epigraphy_sample_v2_updated-5.xlsx - epigraphy_sample_v2` i
    LEFT JOIN `place_master_plc_only-2.xlsx - place` p ON i.place_find = p.place_id
    WHERE 1=1
    """
    # Optional: limit for testing
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"

    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    # ensure output dir exists
    os.makedirs(args.out, exist_ok=True)
    print(rows)

    written = 0
    for row in rows:
        tree = create_tei_tree(row)

        # choose filename: prefer inventory_no if present, else inscription_id
        inv = safe_text(row.get("inventory_no"))
        ins_id = safe_text(row.get("inscription_id"))
        filename_base = inv if inv else f"inscription_{ins_id}"
        # sanitize filename
        safe_fn = "".join(c for c in filename_base if c.isalnum() or c in "._-")
        filename = os.path.join(args.out, safe_fn + ".xml")

        # write with XML declaration and pretty print
        tree.write(filename, encoding="utf-8", xml_declaration=True, pretty_print=True)
        written += 1

    print(f"Wrote {written} EpiDoc files to {os.path.abspath(args.out)}")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export inscriptions to EpiDoc TEI XML files.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--port", default=3306)
    parser.add_argument("--out", default="./epidoc_output")
    parser.add_argument("--limit", default=None, help="Optional: limit number of inscriptions to export (for testing)")
    args = parser.parse_args()
    main(args)
