#!/usr/bin/env python3

import requests
import sys
from xml.etree import ElementTree
from pathlib import Path
import argparse
import re

# arg parser
parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="verbose mode", action="store_true")
parser.add_argument("-o", "--output", help="output type (txt/csv)", default="csv", choices=["txt", "csv", "excel_csv"], type=str)
parser.add_argument("-i", "--include-files", help="include the file names where the intrinsics are found in the output", action="store_true")

args = parser.parse_args()

COMMENT_PATTERN = re.compile(r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"', re.DOTALL | re.MULTILINE)

# Pattern to match C++ strings, including escaped quotes and newlines
STRING_PATTERN = re.compile(r'"(?:[^"\\]|\\.)*"', re.DOTALL)


def get_intrinsics_xml_url():
    print("Fetching the latest intrinsics data...")

    base = "/content/dam/develop/public/us/en/include/intrinsics-guide/"
    r = requests.get("https://www.intel.com/content/dam/develop/public/us/en/include/intrinsics-guide/intrinsicsguide.min.js")
    if r.status_code != 200:
        print("Failed to download the intrinsics guide script")
        sys.exit(1)

    # find the URL of the XML file
    start = r.text.find(base)
    if start == -1:
        print("Failed to find the URL of the XML file")
        sys.exit(1)
    end = r.text.find(".xml", start)
    if end == -1:
        print("Failed to find the URL of the XML file")
        sys.exit(1)

    return "https://www.intel.com" + r.text[start:end+4]

def get_intrinsics_def(url):
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)

    cache_file = cache_dir / url.split("/")[-1]
    if cache_file.exists():
        print("Using cached intrinsics data")
        with open(cache_file, "r") as f:
            return ElementTree.fromstring(f.read())
    else:
        print("Fetching intrinsics data...")
        r = requests.get(url)
        if r.status_code != 200:
            print("Failed to download the intrinsics data")
            sys.exit(1)

        with open(cache_file, "w") as f:
            f.write(r.text)

        return ElementTree.fromstring(r.text)

def parse_intrinsics(xml):
    print("Parsing intrinsics data...")

    intrinsics = {}
    for intr in xml.findall(".//intrinsic"):
        name = intr.get("name") # name of the intrinsic
        tech = intr.get("tech") # instruction set
        cat = intr.find("category").text # instruction kind

        # generates an instruction sequence
        is_sequence = intr.get("sequence") == "true"

        # return type of the intrinsic
        ret = intr.find("return")
        if ret is None:
            print(f"Skipping intrinsic {name} with no return type")
            continue
        
        ret_type = ret.get("type")
        params = [ ( p.get("type"), p.get("varname") ) for p in intr.findall("parameter") ]
        desc = intr.find("description").text.replace("\n", " ").strip()

        if args.verbose:
            print(f"Found {ret_type} {name}({', '.join([f'{t} {n}' for t, n in params])})")

        intrinsics[name] = {
            "tech": tech,
            "cat": cat,
            "seq": is_sequence,
            "ret": ret_type,
            "params": params,
            "desc": desc,
            "in_eve": 0,
            "eve_files": set()
        }

    return intrinsics

def find_intrinsics_used(kb):
    print("finding intrinsics used in eve/core...")
    
    core_path = Path("../include/eve/module/core")

    # glob all hpp files in core
    for file in core_path.glob("**/*.hpp"):
        with open(file, "r") as f:
            data = f.read()
        
        # remove comments and strings
        data = re.sub(COMMENT_PATTERN, '', data)
        data = re.sub(STRING_PATTERN, '', data)

        found_in_file = []
        for intrinsic in kb:
            if intrinsic in data:
                kb[intrinsic]["in_eve"] += 1
                kb[intrinsic]["eve_files"].add(str(file))
                found_in_file.append(intrinsic)

        if args.verbose and len(found_in_file) > 0:
            print(f"Found {len(found_in_file)} intrinsics in {file.name}")

intrinsics = parse_intrinsics(get_intrinsics_def(get_intrinsics_xml_url()))
print(f"Intel intrinsics parsed, found {len(intrinsics)} entries")

used_intrinsics = find_intrinsics_used(intrinsics)
print(f"Done! Found {sum([intrinsics[x]['in_eve'] for x in intrinsics])} intrinsics usage in eve/core")

sorted_intrinsics = sorted(intrinsics.items(), key=lambda x: (-x[1]["in_eve"], x[1]["tech"], x[1]["cat"]))
# print(f"Top 10 most used intrinsics in eve/core: \n\t{'\n\t'.join([f'{x[0]}: {x[1]["in_eve"]}' for x in sorted_intrinsics[:10]])}")

if args.output == "txt":
    max_name_len = max([len(i) for i in intrinsics])
    max_tech_len = max([len(intrinsics[i]['tech']) for i in intrinsics])
    max_cat_len = max([len(intrinsics[i]['cat']) for i in intrinsics])
    with open("./cache/usage.txt", "w") as f:
        f.write(f"{'Name':<{max_name_len}} {'Used':>3} - {'Tech':<{max_tech_len}} {'Cat':<{max_cat_len}} (Description)\n")
        for i in sorted_intrinsics:
            f.write(f"{i[0]:<{max_name_len}} {i[1]['in_eve']:>3} - {i[1]['tech']:<{max_tech_len}} {i[1]['cat']:<{max_cat_len}} ({i[1]['desc']})\n")

    if args.include_files:
        with open("./cache/usage_files.txt", "w") as f:
            for i in sorted_intrinsics:
                if i[1]['in_eve'] > 0:
                    f.write(f"{i[0]:<{max_name_len}} - {i[1]['in_eve']:>3} uses in: \n\t{'\n\t'.join(sorted(i[1]['eve_files']))}\n")

elif args.output in ["csv", "excel_csv"]:
    with open("./cache/usage.csv", "w") as f:
        if args.output == "excel_csv":
            f.write("\"sep=,\"\nname,used,tech,cat,desc\n")
        for i in sorted_intrinsics:
            # escape commas in the description
            f.write(f"{i[0]},{i[1]['in_eve']},{i[1]['tech']},{i[1]['cat']},\"{i[1]['desc'].replace('"', '""')}\"\n")
