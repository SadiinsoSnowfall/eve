#!/usr/bin/env python3

import requests
import sys
from xml.etree import ElementTree
from pandas import DataFrame
from pathlib import Path
import argparse
import re
import subprocess

DEFAULT_SKIP_TECHS = [
    "MMX",
    "SVML",
    "Other",
]

DEFAULT_SKIP_CATEGORIES = [
    "Application-Targeted",
    "Cast",
    "Cryptography",
    "General Support",
    "Random",
    "String Compare",
    "Trigonometry",
]

DEFAULT_SKIP_CPUID = [
    "AVX512_VNNI",
    "AVX512IFMA52",
]

AVX512_SET_ORDER = {
    "AVX512_intersect": [
        "AVX512_VP2INTERSECT"
    ],
    "AVX512_VNNI": [
        "AVX512_VNNI",
    ],
    "AVX512_fp16": [
        "AVX512_FP16",
    ],
    "AVX512_bf16": [
        "AVX512_BF16",   
    ],
    "AVX512_extended": [
        "AVX512_VBMI",
        "AVX512_VBMI2",
        "AVX512_BITALG",
        "AVX512VPOPCNTDQ",
        "GFNI",
    ],
    "AVX512_foundation": [
        "AVX512F",
        "AVX512CD",
        "AVX512VL",
        "AVX512BW",
        "AVX512DQ",
    ]
}

def get_avx512_set(cpuid):
    for set_name, set_intrinsics in AVX512_SET_ORDER.items():
        if any([i in cpuid for i in set_intrinsics]):
            return set_name
    return "<AVX512 UNKNOWN>" if "AVX512" in cpuid else ""

# arg parser
parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="verbose mode", action="store_true")
parser.add_argument("-f", "--format", help="output type (txt/csv)", default="csv", choices=["txt", "csv", "excel_csv", "xlsx"], type=str)
parser.add_argument("-o", "--output", help="output file", default="usage_x86", type=str)
parser.add_argument("--show-usage", help="include the file names where the intrinsics are found in the output", action="store_true")
parser.add_argument("-c", "--cmp-folder", help="folder to compare with", type=str, default="eve")
parser.add_argument("-r", "--refresh", help="refresh the intrinsics data", action="store_true")

# x86 specific options
parser.add_argument("--include-ss-sd", help="count SS, SD and SH intrinsics", action="store_true")
parser.add_argument('--include-complex', help='count complex number intrinsics', action='store_true')
parser.add_argument("--include-mmx", help="count MMX/mm64 intrinsics", action="store_true")
parser.add_argument("--include-pure-mask", help="skip intrinsics that are pure mask", type=str, default="no", choices=["yes", "no", "only"])
parser.add_argument("--include-macros", help="skip intrinsics with the specified macros", action="store_true")
parser.add_argument("--include-maskz", help="skip intrinsics with maskz", action="store_true")
parser.add_argument("--skip-tech", help="skip intrinsics with the specified techs", type=str, nargs="+", default=DEFAULT_SKIP_TECHS)
parser.add_argument("--skip-cat", help="skip intrinsics with the specified categories", type=str, nargs="+", default=DEFAULT_SKIP_CATEGORIES)
parser.add_argument("--skip-cpuid", help="skip intrinsics with the specified cpuid flags", type=str, nargs="+", default=DEFAULT_SKIP_CPUID)

args = parser.parse_args()

# get the top level path using git
top_level = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE).stdout.decode().strip())
include_path = top_level / 'include' / args.cmp_folder

if not include_path.exists():
    print(f"Path {include_path} does not exist")
    sys.exit(1)

COMMENT_PATTERN = re.compile(r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"', re.DOTALL | re.MULTILINE)
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

    cache_file = cache_dir / ("x86-intr" + url.split("/")[-1])
    if cache_file.exists() and not args.refresh:
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

        # <instruction form="ymm {z}, ymm, ymm" name="VCVTNE2PS2BF16" xed="VCVTNE2PS2BF16_YMMbf16_MASKmskw_YMMf32_YMMf32_AVX512"/>
        # maybe have multiple or none

        instructions_names = ','.join(sorted([ i.get("name") for i in intr.findall("instruction") ]))

        # CPUID flags 
        cpuid = ' + '.join([ c.text for c in intr.findall("CPUID")])

        # generates an instruction sequence
        is_sequence = "yes" if  intr.get("sequence") == "TRUE" else "no"

        # return type of the intrinsic
        ret = intr.find("return")
        if ret is None:
            print(f"Skipping ill-formed intrinsic {name} with no return type")
            continue
        
        ret_type = ret.get("type")
        params = [ ( p.get("type"), p.get("varname") ) for p in intr.findall("parameter") ]
        desc = intr.find("description").text.replace("\n", " ").strip()

        is_macro = desc.startswith("Macro:")

        conflict_should_skip = False

        if name in intrinsics:
            print(f"Warn: Duplicated intrinsic {name:<25}", end='')

            # sanity check, try to find what differs between the two
            dup = intrinsics[name]

            if dup["tech"] != tech:
                print(f" +tech ({dup['tech']} vs {tech})", end='')

            if dup["cat"] != cat:
                print(f" +cat ({dup['cat']} vs {cat})", end='')

            if dup["cpuid"] != cpuid:
                print(f" +cpuid ({dup['cpuid']} vs {cpuid})", end='')

            if dup["seq"] != is_sequence:
                print(f" +is_sequence ({dup['seq']} vs {is_sequence})", end='')

            if dup["ret"] != ret_type:
                print(f" +ret ({dup['ret']} vs {ret_type})", end='')

            if dup["is_macro"] != is_macro:
                print(f" +is_macro ({dup['is_macro']} vs {is_macro})", end='')

            if dup["instructions"] != instructions_names:
                print(f" +instructions ({dup['instructions']} vs {instructions_names})", end='')

            # attempt to resolve conflicts
            if dup["tech"] != tech:
                if "AVX-512" in dup["tech"]:
                    if "AVX-512" not in tech:
                        conflict_should_skip = True
                        print(" [RESOLVED: AVX512 priority]", end='')
                elif "AVX-512" in tech:
                    print(" [RESOLVED: AVX512 priority]", end='')

            print()

        if conflict_should_skip:
            continue

        # skip intrinsics with the specified techs or categories
        if tech in args.skip_tech or cat in args.skip_cat:
            continue

        # skip SS and SD intrinsics if requested 
        if not args.include_ss_sd and (name.endswith("_sd") or name.endswith("_ss") or name.endswith("_sh")):
            continue

        if not args.include_complex and "complex number" in desc:
            continue

        if not args.include_macros and is_macro:
            continue

        if any([c in cpuid for c in args.skip_cpuid]):
            continue

        if not args.include_maskz and "_maskz_" in name:
            continue

        # ignore MMX intrinsics or those using MMX types in input or output
        if not args.include_mmx and (tech == "MMX" or "__m64" in ret_type or any(["__m64" in t for t, _ in params])):
            continue

        is_pure_mask = "__mmask" in ret_type and all(["__mmask" in t for t, _ in params])

        # test for pure mask manipulation intrinsics
        if (args.include_pure_mask == "no" and is_pure_mask) or (args.include_pure_mask == "only" and not is_pure_mask):
            continue

        if args.verbose:
            print(f"Found {ret_type} {name}({', '.join([f'{t} {n}' for t, n in params])})")

        intrinsics[name] = {
            "name": name,
            "tech": tech,
            "cpuid": cpuid,
            "cat": cat,
            "tag": get_avx512_set(cpuid),
            "instructions": instructions_names,
            "seq": is_sequence,
            "ret": ret_type,
            "is_macro": is_macro,
            "params": params,
            "desc": desc,
            "in_eve": 0,
            "eve_files": set()
        }

    return intrinsics

def find_intrinsics_used(kb):
    print("finding intrinsics used in eve...")

    # glob all hpp files in core
    for file in include_path.glob("**/*.hpp"):
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
            print(f"Found {len(found_in_file)} intrinsics in {file}")

intrinsics = parse_intrinsics(get_intrinsics_def(get_intrinsics_xml_url()))
print(f"Intel intrinsics parsed, found {len(intrinsics)} entries")

used_intrinsics = find_intrinsics_used(intrinsics)
print(f"Done! Found {sum([intrinsics[x]['in_eve'] for x in intrinsics])} intrinsics usage in include/{args.cmp_folder}")

sorted_intrinsics = sorted(intrinsics.values(), key=lambda x: (-x["in_eve"], x["tech"], x["cpuid"], x["cat"], x["name"]))

cols = ["name", "in_eve", "tech", "cpuid", "cat", "tag", "seq", "desc"]
col_names = ["Name", "Used", "Tech", "CPUID", "Category", "Tag", "Is sequence", "Description"]

if args.format == "txt":
    max_lens = [ max(len(str(i[key])) for i in intrinsics.values()) for key in cols ]
    max_lens = [ max(max_lens[i], len(col_names[i])) for i in range(len(cols)) ]

    with open(f"./out/{args.output}.txt", "w") as f:
        if args.show_usage:
            for i in sorted_intrinsics:
                if i['in_eve'] > 0:
                    f.write(f"{i["name"]:<{max_lens[0]}} - {i['in_eve']:>3} uses in: \n\t{'\n\t'.join(sorted(i[1]['eve_files']))}\n")

        else:
            f.write(" │ ".join([col_names[i].ljust(max_lens[i]) for i in range(len(cols))]) + "\n")
            f.write("┼".join(["─" * (max_lens[i] + (2 if i else 1)) for i in range(len(cols))]) + "\n")

            for i in sorted_intrinsics:
                f.write(" │ ".join([str(i[key]).ljust(max_lens[j]) for j, key in enumerate(cols)]) + "\n")

elif args.format in ["csv", "excel_csv", "xlsx"]:
    df = DataFrame(sorted_intrinsics, columns=cols)
    df.rename(columns=dict(zip(cols, col_names)), inplace=True)

    if args.format == "excel_csv":
        df.to_csv(f"./out/{args.output}.csv", index=False, sep=";", quoting=1)
    elif args.format == "csv":
        df.to_csv(f"./out/{args.output}.csv", index=False, sep=",", quoting=1)
    else:
        df.to_excel(f"./out/{args.output}.xlsx", index=False)
