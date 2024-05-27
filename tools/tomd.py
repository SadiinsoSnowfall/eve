#!/usr/bin/env python3

import pandas as pd
import os

os.makedirs("out/meow", exist_ok=True)

xls = pd.ExcelFile('out/usage_all_x86.xlsx')
df = xls.parse(xls.sheet_names[0]).drop(columns=['Used', 'Is sequence', 'CPUID', 'Tech', 'Category'])

tags = df['Tag'].unique()
tag_names = [tag.replace('AVX512_', '') for tag in tags]

def sort_name(name):
    # order by name ignoring the _mm_, _mm256_ and _mm512_, ties using the full name with prefixes in this order
    base = name.removeprefix('_mm512_').removeprefix('_mm256_').removeprefix('_mm_')
    wid = '0' if name.startswith('_mm_') else '1' if name.startswith('_mm256_') else '2'
    return base + wid

for tag, tag_name in zip(tags, tag_names):
    tag_df = df[df['Tag'] == tag]
    # remove the tag column
    tag_df = tag_df.drop(columns=['Tag'])

    # order by name ignoring the _mm_, _mm256_ and _mm512_ prefixes
    idx = tag_df['Name'].map(sort_name).argsort()
    tag_df = tag_df.iloc[idx]

    # map the Name colums
    tag_df['Name'] = tag_df['Name'].map(lambda x: f"`{x}`")

    # add checkbox column at the begining
    tag_df.insert(0, '✓', '\u274c')
    
    # output to markdown
    with open(f'out/meow/{tag_name}.md', 'w') as f:
        md = tag_df.to_markdown(index=False)
        if len(md) > 65400:
            print(f"Warning: {tag_name} is too long ({len(md)} chars ({len(tag_df)} intr)) - stripping description")

            # put only the Name column, and in four columns
            tag_df = tag_df[['Name']]
            tag_len = len(tag_df)
            q_size = tag_len // 3

            quarters = [ tag_df.iloc[i*q_size:(i+1)*q_size] for i in range(3) ]
            quarters[-1] = pd.concat([quarters[-1], tag_df.iloc[3*q_size:]])

            for quarter in quarters:
                quarter.reset_index(drop=True, inplace=True)
                quarter.columns = ['Name']

            res = pd.concat(quarters, axis=1)

            # add a checkbox at the begining of each cell
            res = res.fillna('')
            res = res.map(lambda x: '\u274c ' + x if x else x)

            md = res.to_markdown(index=False)
            
        f.write(md)
