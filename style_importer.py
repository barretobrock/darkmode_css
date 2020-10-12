"""
This script reads in a new JSON blob and handles adding in changes to our repo of CSS files.
"""
import os
import sys
import json
import time
from kavalkilu import Log


logg = Log('css-style-import', arg_parse=False)
# Where we store the broken-down styles for manual inspection
styles_dir = os.path.abspath('styles')
# Where we store the JSON file that we'll import into the Stylus fork
target_styles_path = os.path.abspath('style-pack.json')


class TermColor:
    """Terminal colors"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def build_confirm(pretext: str, highlight: str, question: str) -> str:
    """Build out an input line"""
    div = '-' * 20
    var = input(f'{div}\n{pretext} {TermColor.OKBLUE}{highlight}{TermColor.ENDC} - '
                f'{TermColor.OKGREEN}{question}{TermColor.ENDC} (y/n)')
    return var.lower().strip()


# This should be the JSON file that will replace our styles.json file the user has made changes to
source_styles_path = sys.argv[1]
if not os.path.exists(source_styles_path):
    raise FileNotFoundError('The file path added was not found')

for fpath in [styles_dir, target_styles_path]:
    if not os.path.exists(fpath):
        raise FileNotFoundError(f'Path {fpath} not found. Please run this script in the '
                                f'darkmode directory on the project root.')

# Read in the source & target (master styles) files as a json blob
with open(source_styles_path) as src, open(target_styles_path) as tgt:
    source_styles = json.loads(src.read())
    target_styles = json.loads(tgt.read())

styles_dict = {}
for path, styles in zip(['src', 'tgt'], [source_styles, target_styles]):
    # Populate styles into the style dict
    for style in styles:
        style_name = style['name']
        if style_name in styles_dict.keys():
            # Dict already written for this style. Just add another item to the dict
            styles_dict[style_name][path] = style
        else:
            # Make new item in topmost dict & add style there
            styles_dict[style_name] = {path: style}

# Now we iterate through each item in our style dictionary, making comparisons
# and determining which styles are new, etc.
# Keep track of style changes
style_changes = {k: [] for k in ['add', 'change', 'remove']}
for style_name, style_grp in styles_dict.copy().items():
    if 'tgt' not in style_grp.keys():
        # See if new style (no tgt key if so)
        keep_new = build_confirm('Found a new style:', style_name, 'Import it to the master list?')
        if keep_new == 'y':
            logg.debug(f'Added new style: {style_name}.')
            style_changes['add'].append(style_name)
            styles_dict[style_name]['tgt'] = style_grp['src']
        else:
            logg.debug(f'Skipped new style: {style_name}.')
    elif 'src' not in style_grp.keys():
        # See if removed/nonexistent style (no 'src' key if so)
        remove_style = build_confirm('Missing style from source list:', style_name,
                                     'Delete also from the master list?')
        if remove_style == 'y':
            logg.debug(f'Removing style: {style_name}.')
            style_changes['remove'].append(style_name)
            _ = styles_dict.pop(style_name)
        else:
            logg.debug(f'Skipped removing style from master: {style_name}.')
    elif style_grp['src']['sections'] != style_grp['tgt']['sections']:
        # See if changed style
        replace_style = build_confirm('Found change in style:', style_name, 'Replace the master style with these?')
        if replace_style == 'y':
            logg.debug(f'Replacing style: {style_name}.')
            style_changes['change'].append(style_name)
            styles_dict[style_name]['tgt'] = style_grp['src']
        else:
            logg.debug(f'Skipped change to style: {style_name}.')

# Confirm the changes
logg.debug('Style import process completed.')
formatted_txt = "Confirm the style changes:\n"
for k, v in style_changes.items():
    style_list = '\n\t- {}\n'.format('\n\t- '.join(v)) if len(v) > 0 else '\n'
    formatted_txt += f'{TermColor.OKBLUE}{k}{TermColor.ENDC}: {style_list}'
confirm = input(f'{formatted_txt}{TermColor.OKGREEN}Look good?{TermColor.ENDC} (y/n)').lower().strip()
if confirm != 'y':
    logg.debug('Changes not accepted. Stopping instance.')
    sys.exit(1)

logg.debug('Style import process completed. Beginning CSS breakout process...')

# Go through the styles we've added to the 'tgt' group; build their css and write it to the file.
master_styles = []
for style_name, style_grp in styles_dict.items():
    if 'tgt' in style_grp.keys():
        style = style_grp['tgt']
        style_code = ''.join([x['code'] for x in style['sections']])

        style_file_name = f'{style_name.replace(" ", "_").lower()}.css'
        # Save code in css file named after the theme
        with open(os.path.join(styles_dir, style_file_name), 'w') as f:
            f.write(style_code)

        # Add style to master list of styles
        master_styles.append(style)

logg.debug('Styles written to CSS. Cleaning stale styles from CSS folder.')
# Scan all styles in the CSS folder, remove any that aren't in the master styles list
root, dirs, files = next(os.walk(styles_dir))
accepted_files = [f"{x['name'].replace(' ', '_').lower()}.css" for x in master_styles]
removed_files = []
for file in files:
    if file not in accepted_files:
        print(f'{file} not in list of master styles. Removing...')
        os.remove(os.path.join(styles_dir, file))
        removed_files.append(file)
if len(removed_files) > 0:
    rem_file_txt = "\n\t- {}".format('\n\t- '.join(removed_files))
    logg.debug(f'Total CSS files removed: {len(removed_files)} \n{rem_file_txt}')

logg.debug('Cleaning JSON file of metadata & updating timestamps...')
for i, style in enumerate(master_styles):
    update_ts = int(round(time.time() * 1000, 0))
    # Update keys in the style dict to enforce some requirements
    style.update({
        # Set the enabled key to False for every style except Global Theme
        'enabled': style['name'] in ['Global Theme', 'Dark Stylus'],
        # make sure any adopted styles no longer point to their original sources to avoid conflict
        'updateUrl': None,
        'md5Url': None,
        'originalMd5': None,
        'url': None,
        'updateDate': update_ts,
        '_rev': update_ts
    })
    master_styles[i] = style

logg.debug('Writing cleaned styles to JSON.')
# Write master styles to file
with open(target_styles_path, 'w') as f:
    f.write(json.dumps(master_styles, indent=4))

logg.debug('Script complete!')
