import re
import xml.etree.ElementTree as ET
def dhv_to_epidoc(text):
    """
    Convert Armenian DHV epigraphic markup conventions to EpiDoc XML tags.
    This mapping follows the visible correspondences in the provided table.
    Nested patterns are not handled.
    """

    if not text:
        return ET.element("ab")

    # Insert initial line
    text = '<ab><lb n="1"/>' + text

    line_counter = 2  # Initialize line counter for <lb> tags
    # Function to insert <lb> with incrementing numbers
    def replace_linebreak(match):
        nonlocal line_counter
        tag = f'<lb n="{line_counter}"/>'
        line_counter += 1
        return tag

    # Line breaks: 	word division across lines, or explicit line markers
    text = re.sub(r'/(?=[^>])', replace_linebreak, text)

    # 1271 -> <num value="1271">1271</num> should be between blanks
    text = re.sub(r'(?<=\s)(\d{1,4})(?=\s)', r'<num value="\1">\1</num>', text)


    # Lacuna (extent unknown) — represented by ---
    text = text.replace('---', '<gap reason="lost" extent="unknown" unit="character"/>')
    # «…» -> <gap reason="lost" extent="unknown" unit="character"/>
    text = re.sub(r'«(.*?)»', r'<gap reason="lost" extent="unknown" unit="character"/>', text)
    # [---] -> <gap reason="lost" extent="unknown" unit="character"/>
    text = re.sub(r'\[---\]', r'<gap reason="lost" extent="unknown" unit="character"/>', text)
    # ⎣c.1⎦ -> <gap reason="lost" quantity="1" unit="character" precision="low"/>
    text = re.sub(r'⎣c\.(\d+)⎦', r'<gap reason="lost" quantity="\1" unit="character" precision="low"/>', text)

    # ⎣աբգ⎦ -> <supplied reason="omitted">աբգ</supplied>
    text = re.sub(r'⎣(.*?)⎦', r'<supplied reason="omitted">\1</supplied>', text)

    #  ⎡Ա⎤ -> <supplied reason=“lost”>Ա</supplied>
    text = re.sub(r'⎡(.*?)⎤', r'<supplied reason="lost">\1</supplied>', text)

    # [յ] -> <surplus>յ</surplus>
    text = re.sub(r'\[(.*?)\]', r'<surplus>\1</surplus>', text)



    


    # full stops and numeral markings
    def replacement_func(match):
        # Group 1  captures the full numeral marker, e.g., ":աբգ:"
        if match.group(1):
            # We only want the colons for the output, so we return the XML with "::"
            return f'<g type="punct" subtype="numeral-marker">{match.group(1)}</g>'
        # Group 2 (match.group(2)) captures the single colon ":"
        elif match.group(2):
            return '<g type="fullstopr">:</g>'
        return match.group(0) # Should not happen

    text = re.sub(r'(:[^:]{1,6}:)|(:)', replacement_func, text)

    #Ligatures 
    # handle special case like: {ն ^^Ա}(ստուծո)յ^^
    pattern = re.compile(
        r'\{([^{}]*?)\s*\^\^([\u0531-\u058F]+)\s*\}\s*\(\s*([\u0531-\u058F]+)\s*\)\s*([\u0531-\u058F]+)\^\^'
    )

    def _repl_special(m):
        lig_before = m.group(1).strip()
        first_abbr = m.group(2).strip()          
        expansion = m.group(3).strip()           
        last_abbr = m.group(4).strip()           
        # produce ligature containing the lig_before + first_abbr,
        # then an <expan> with empty initial <abbr>, <ex> and final <abbr>
        return (f'<hi rend="ligature">{lig_before} {first_abbr}</hi>'
                f'<expan><abbr></abbr><ex>{expansion}</ex><abbr>{last_abbr}</abbr></expan>')

    text = pattern.sub(_repl_special, text)

    text = re.sub(r'\{([^{}]+)\}', r'<hi rend="ligature">\1</hi>', text)

    # Honorifics
    # ^^Ա(ստուծո)յ^^  -> <expan><abbr>Ա</abbr><ex>ստուծո</ex><abbr></abbr></expan>
    text = re.sub(r'\^\^([^\^()]+?)\(([^)]*?)\)([^\^()]+?)\^\^', r'<expan><abbr>\1</abbr><ex>\2</ex><abbr>\3</abbr></expan>', text)
    # ^^ս(ո)ք(ա)^^ -> <expan><abbr>ս</abbr><ex>ո</ex><abbr>ք</abbr><ex>ա</ex></expan>
    text = re.sub(r'\^\^([^\^()]+?)\(([^)]*?)\)([^\^()]+?)\(([^)]*?)\)\^\^', r'<expan><abbr>\1</abbr><ex>\2</ex><abbr>\3</abbr><ex>\4</ex></expan>', text)
    # ^^կ⎣ա⎦թ⎣ո⎦ղ⎣իկո⎦ս^^ -> <expan>կ<abbr>կ</abbr><ex>ա</ex><abbr>թ</abbr><ex>ո</ex><abbr>իկո</abbr><ex>ս</ex></expan>
    def sub_honorifics_callback(match):
        inner_text = match.group(1)

        # Case 1: Complex Expansion (Contains ⎣...⎦)
        if '⎣' in inner_text and '⎦' in inner_text:
            
            # Step A: Split the content by the bracketed expansion parts, keeping the parts in the list.
            # E.g., 'կ⎣ա⎦թ⎣ո⎦ղ⎣իկո⎦ս' -> ['կ', '⎣ա⎦', 'թ', '⎣ո⎦', 'ղ', '⎣իկո⎦', 'ս']
            split_parts = re.split(r'(⎣.*?⎦)', inner_text)
            
            result_parts = []
            
            # Step B: Iterate through the parts and apply tagging
            for part in split_parts:
                if not part:
                    continue

                # Expansion Part: starts/ends with ⎣/⎦
                if part.startswith('⎣') and part.endswith('⎦'):
                    content = part[1:-1] # Remove the brackets
                    result_parts.append(f'<ex>{content}</ex>')
                    
                # Abbreviation Part: standard text chunk
                else:
                    result_parts.append(f'<abbr>{part}</abbr>')

            processed_content = "".join(result_parts)
            return f'<expan>{processed_content}</expan>'

        # Case 2: Simple Abbreviation (Does NOT contain ⎣...⎦)
        else:
            return f'<abbr>{inner_text}</abbr>'
    text = re.sub(r'\^\^(.*?)\^\^', sub_honorifics_callback, text)
    # ութե(ան) -> <expan><abbr>ութե</abbr><ex>ան</ex></expan> anythinh but digits or latin letters
    text = re.sub(r'(\w+)\((.*?)\)', r'<expan><abbr>\g<1></abbr><ex>\g<2></ex></expan>', text)

    # Եղի(այ)ի -> <expan><abbr>Եղի</abbr><ex>այ</ex><abbr>ի</abbr></expan>
    # belek             
    text = re.sub(r'(\w+)\(([^)]+)\)(\w+)', r'<expan><abbr>\1</abbr><ex>\2</ex><abbr>\3</abbr></expan>', text)


    # Space left  
    # (vac. c.10) -> <space quantity="10" unit="character"/> (possible spaces in parentheses)
    text = re.sub(r'\(\s*vac\.\s*c\.(\d+)\s*\)', r'<space quantity="\1" unit="character"/>', text)
    # (vac. 20) -> <space quantity="10" unit="character"/>
    text = re.sub(r'\(\s*vac\.\s*(\d+)\s*\)', r'<space quantity="\1" unit="character"/>', text)
    # vac.10 -> <space quantity="10" unit="character"/>
    text = re.sub(r'vac\.(\d+)', r'<space quantity="\1" unit="character"/>', text)
    # (vac.3) -> <space quantity="3" unit="character"/>
    text = re.sub(r'\(\s*vac\.(\d+)\s*\)', r'<space quantity="\1" unit="character"/>', text)

    # (2) -> <num value="2">2</num>
    text = re.sub(r'\((\d+)\)', r'<num value="\1">\1</num>', text)


    text = text + '</ab>'
    return ET.fromstring(text)
"""
input = ":Թիւ: ՉԻ (1271)/ Կ{ամ}{աւ}{ն ^^Ա}(ստուծո)յ^^, ես՝ Յոհանէս, / {որ}դի Իւանէի՝ առաջն{որ}դ ^^Ս(ուր)բ^^ ու/խտիս {Գան}ձաս{ար}ա, հր{ամ}{ան}{աւ} ^^տ(եառ)ն^^ Խաչ/ինո Աթ{աբ}{եկի}ն, ի յիմ հալալ {ար}դե{ան}ց գ{նե}ց/ի զՎ{ար}{դան}աթաղս, {մին} չ{որ}եց եզ{ն ե}ւ այլ  ընծ/էք տվի ի ^^Ս(ուր)բ^^  Կաթողիկէս. {մի}{աբ}{ան}քս տվին զՈհ{ան}ու, զ/{Ակ}{ոբ}ա տ{աւ}նն զ{ամ}էն {եկե}{ղեց}իք{ս ի}նձ {պա}տ{ար}{ագ}. ով խ/{ափան}է, {դա}տի յ^^Ա(ստուծո)յ^^:"
print(dhv_to_epidoc(input))
"""

