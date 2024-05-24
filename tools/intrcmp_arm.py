#!/usr/bin/env python3

# pip3 install pandas requests openpyxl Jinja2

import requests
import sys
from pathlib import Path
from pandas import DataFrame
import json
import argparse
import re
import subprocess

ARM_INTR_OPT_PATTERN = re.compile(r'\[([^\]]+)\]')

# just dedup either all the optional parts or none:
# [__arm_]vddupq[_wb]_u32 => [vddupq_u32, __arm_vddupq_wb_u32]
def instr_name_dedup(s):
    return (ARM_INTR_OPT_PATTERN.sub('', s), ARM_INTR_OPT_PATTERN.sub(r'\1', s))

ARM_INTR_URL = "https://developer.arm.com/architectures/instruction-sets/intrinsics/data/intrinsics.json"

DEFAULT_SKIP_ISA = [
    "Helium"
]

DEFAULT_SKIP_GROUPS = [
    "Cryptography",
    "Reinterpret casts",
]

# arg parser
parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="verbose mode", action="store_true")
parser.add_argument("-f", "--format", help="output type (txt/csv)", default="csv", choices=["txt", "csv", "excel_csv", "xlsx"], type=str)
parser.add_argument("-o", "--output", help="output file", default="usage_arm", type=str)
parser.add_argument("--show-usage", help="include the file names where the intrinsics are found in the output", action="store_true")
parser.add_argument("-r", "--refresh", help="refresh the intrinsics data", action="store_true")
parser.add_argument("-c", "--cmp-folder", help="folder to compare with", type=str, default="eve")

# arm specific options
parser.add_argument("--skip-isa", help="skip intrinsics with the specified ISAs", type=str, nargs="+", default=DEFAULT_SKIP_ISA)
parser.add_argument("--skip-groups", help="skip intrinsics with the specified groups", type=str, nargs="+", default=DEFAULT_SKIP_GROUPS)
parser.add_argument("--no-name-dedup", help="do not deduplicate intrinsics with optional name parts", action="store_true")
parser.add_argument("--select-flavor", choices=["all", "short", "long"], default="short", help="select intrinsics by flavor if deduplication is enabled", type=str)

args = parser.parse_args()

# get the top level path using git
top_level = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE).stdout.decode().strip())
include_path = top_level / 'include' / args.cmp_folder

if not include_path.exists():
    print(f"Path {include_path} does not exist")
    sys.exit(1)

COMMENT_PATTERN = re.compile(r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"', re.DOTALL | re.MULTILINE)
STRING_PATTERN = re.compile(r'"(?:[^"\\]|\\.)*"', re.DOTALL)

def get_intrinsics_def():
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)

    cache_file = cache_dir / "arm-intrdata.json"
    if args.refresh or not cache_file.exists():
        print("Fetching intrinsics data...")
        r = requests.get(ARM_INTR_URL)
        if r.status_code != 200:
            print("Failed to download the intrinsics data")
            sys.exit(1)

        with open(cache_file, "w") as f:
            f.write(r.text)

        return json.loads(r.text)
    else:
        print("Using cached intrinsics data")
        with open(cache_file, "r") as f:
            return json.load(f)

def resolve_seq_conflicts(a, b):
    match a, b:
        case (x, y) if x == y:
            return x
        case (_, "maybe+comptime") | ("maybe+comptime", _):
            return "maybe+comptime"
        case ("yes", "no") | ("no", "yes") | ("maybe", _) | (_, "maybe"):
            return "maybe"
        case ("yes+comptime", "no+comptime") |  ("no+comptime", "yes+comptime") | ("yes", "no+comptime") | ("no+comptime", "yes") | ("yes+comptime", "no") | ("no", "yes+comptime"):
            return "maybe+comptime"
        case _:
            print(f"Error: Unhandled sequence conflict: {a} vs {b}")
            exit(1)

def process_intrinsics(data):
    intrinsics = { }
    resolved_conflicts = 0
    unresolved_conflicts = 0

    for i in data:
        base_name = i["name"]
        isa = i["SIMD_ISA"]
        archs = '/'.join(i["Architectures"])
        group = i["instruction_group"].replace('|', '/')
        ret_type = i["return_type"]["value"]
        params = i["arguments"]
        desc = i["description"]

        is_sequence = None
        can_be_comptime = False

        if 'instructions' not in i:
            is_sequence = 'comptime'
        else:
            for ibundle in i["instructions"]:
                # all nop
                if all([x["base_instruction"] == "NOP" for x in ibundle["list"]]):
                    can_be_comptime = True
                    continue

                bundle_is_seq = 'yes' if len(ibundle["list"]) > 1 else 'no'
                if is_sequence is None or is_sequence == bundle_is_seq:
                    is_sequence = bundle_is_seq
                else: # not first time and different => maybe
                    is_sequence = 'maybe'

        if is_sequence is None and not can_be_comptime:
            print(f"Error: No instructions found for intrinsic {base_name}")
            exit(1)

        if is_sequence is None:
            is_sequence = 'comptime'
        elif can_be_comptime:
            is_sequence = is_sequence + ' + comptime'

        # arm intrinsics have optional parts in their names
        if args.no_name_dedup or '[' not in base_name:
            dedup_names = [ base_name ]
        else:
            short, long = instr_name_dedup(base_name)
            if args.select_flavor == "short":
                dedup_names = [ short ]
            elif args.select_flavor == "long":
                dedup_names = [ long ]
            else:
                dedup_names = [ short, long ]

        # find tag
        tag = ""
        
        # check for bf16
        if "bfloat16" in ret_type or any([ "bfloat16" in x for x in params ]):
            tag = "bf16"
        elif "float16" in ret_type or any([ "float16" in x for x in params ]):
            tag = "fp16"
        elif "poly" in ret_type or any([ "poly" in x for x in params ]):
            tag = "poly"

        # filter by isa
        if any([x in args.skip_isa for x in isa.split('/')]):
            continue

        # filter by group
        if any([x in args.skip_groups for x in group.split('/')]):
            continue

        for name in dedup_names:
            c_ret = ret_type
            c_params = params
            c_seq = is_sequence
            c_group = group
            c_archs = archs
            c_isa = isa
            c_tag = tag
            c_desc = desc
            
            if name in intrinsics:
                # sanity check, try to find what differs between the two
                conflicts = set()
                dup = intrinsics[name]
                resolved = False

                if dup["isa"] != isa:
                    conflicts.add("isa")

                if dup["arch"] != archs:
                    conflicts.add("arch")

                if dup["group"] != group:
                    conflicts.add("group")

                if dup["ret"] != ret_type:
                    conflicts.add("ret")

                if dup["seq"] != is_sequence:
                    conflicts.add("seq")

                if len(dup["params"]) != len(params) or any([a != b for a, b in zip(dup["params"], params)]):
                    conflicts.add("params")

                if len(conflicts) > 0:
                    c_desc = "<conflicted>"

                # resolve sequence conflicts
                if "seq" in conflicts:
                    c_seq = resolve_seq_conflicts(dup["seq"], is_sequence)
                    conflicts.remove("seq")

                if "group" in conflicts:
                    conflicts.remove("group")
                    c_group = "<multiple>"

                if "arch" in conflicts:
                    conflicts.remove("arch")
                    c_archs = "<multiple>"

                if "isa" in conflicts:
                    conflicts.remove("isa")
                    c_isa = "<multiple>"

                # conflict only because of the return type and/or the params
                # this is mostly cause when using the "short version" of the intrinsics, which erase the type in the name
                # in this case, we can just update the return type and the params and set them to "multiple"
                if conflicts <= {"ret", "params"}:
                    conflicts.clear()
                    c_ret = "<multiple>" if "ret" in conflicts else dup["ret"]
                    c_params = [ "<multiple>"  if a != b else a for a, b in zip(dup["params"], params) ] if "params" in conflicts else params

                if len(conflicts) == 0:
                    resolved = True
                    resolved_conflicts += 1
                else:
                    unresolved_conflicts += 1

                if args.verbose or not resolved:
                    print(f"Error: Duplicate entry found for intrinsic {name:<33}", end='')

                    if dup["isa"] != isa:
                        conflicts.add("isa")
                        print(f" +ISA ({dup['isa']} vs {isa})", end='')

                    if dup["arch"] != archs:
                        conflicts.add("arch")
                        print(f" +Arch ({dup['arch']} vs {archs})", end='')

                    if dup["group"] != group:
                        conflicts.add("group")
                        print(f" +Group (\"{dup['group']}\" vs \"{group}\")", end='')

                    if dup["ret"] != ret_type:
                        conflicts.add("ret")
                        print(f" +Ret ({dup['ret']} vs {ret_type})", end='')

                    if dup["seq"] != is_sequence:
                        conflicts.add("seq")
                        print(f" +Seq ({dup['seq']} vs {is_sequence})", end='')

                    if len(dup["params"]) != len(params) or any([a != b for a, b in zip(dup["params"], params)]):
                        conflicts.add("params")
                        print(f" +Params", end='')

                    print()

            if args.verbose:
                print(f"Found {ret_type} {name}({', '.join(params)})")

            intrinsics[name] = {
                "name": name,
                "isa": c_isa,
                "arch": c_archs,
                "tag": c_tag,
                "group": c_group,
                "ret": c_ret,
                "desc": c_desc,
                "seq": c_seq,
                "in_eve": 0,
                "params": c_params,
                "eve_files": set(),
            }

    if unresolved_conflicts > 0 or resolved_conflicts > 0:
        print(f"Resolved {resolved_conflicts} name conflicts, {unresolved_conflicts} conflicts remain")
    
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

intrinsics = process_intrinsics(get_intrinsics_def())
print(f"ARM intrinsics parsed, found {len(intrinsics)} entries")

used_intrinsics = find_intrinsics_used(intrinsics)
print(f"Done! Found {sum([intrinsics[x]['in_eve'] for x in intrinsics])} intrinsics usage in include/{args.cmp_folder}")

sorted_intrinsics = sorted(intrinsics.values(), key=lambda x: (-x["in_eve"], x["isa"], x["arch"], x["tag"], x["group"], x["name"]))

cols = ["name", "in_eve", "isa", "arch", "tag", "group", "seq", "desc"]
col_names = ["Name", "Used", "ISA", "Archs", "Tag", "Group", "Is sequence", "Description"]

if args.format == "txt":
    max_lens = [ max(len(str(i[key])) for i in intrinsics.values()) for key in cols ]
    max_lens = [ max(max_lens[i], len(col_names[i])) for i in range(len(cols)) ]

    with open(f"./out/{args.output}.txt", "w") as f:
        if args.show_usage:
            for i in sorted_intrinsics:
                if i['in_eve'] > 0:
                    f.write(f"{i['name']:<{max_lens[0]}} - {i['in_eve']:<{max_lens[1]}} uses in: \n\t{'\n\t'.join(sorted(i['eve_files']))}\n")
        
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
