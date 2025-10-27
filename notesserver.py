#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import sys
from flask import Flask, render_template, request, redirect
from datetime import datetime, timedelta
from markdown_it import MarkdownIt
import re
import html
from noteslib import parseEntries, writeFile, MARKDOWN_SUFFIX, TAG_NAMESPACE_SEPARATOR, TAG_REGEX
from pathlib import Path
import uuid
import mimetypes
from werkzeug.utils import secure_filename
from flask import send_from_directory, jsonify
import subprocess
import shutil

app = Flask(__name__)
md = MarkdownIt()
NOTEBOOK_NAME = "notes"
ENTRIES_PER_PAGE = 25
HIDE_DOTFILES = True

# add media folder (inside notebook path)
NOTEBOOK_PATH = Path(os.environ.get('NOTES_PATH', '.')).resolve()
MEDIA_FOLDER = NOTEBOOK_PATH / "media"
JOURNAL_PATH = NOTEBOOK_PATH / "journal"

JOURNAL_FILE_REGEX = re.compile(r'(YYYY)-Q([1-4])\.md$')
JS_ENTRY_ID_FORMAT = "%Y%m%d_%H%M%S"


def edit_entry(entry_id_str, content):
    """
    Update an entry in the appropriate quarterly journal file.

    Assumptions:
    - entry_id is a datetime string (several common formats are accepted).
    - The journal filename is "<year>-Q<quarter>.md".
    - Entries are delimited by header lines that start with "### ".
      The header line contains the date/time (and title); we locate the entry
      by matching the date portion and replace the header+body until the next "### " or EOF.
    """

    # try several datetime formats
    dt = None
    fmts = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", JS_ENTRY_ID_FORMAT)
    for fmt in fmts:
        try:
            dt = datetime.strptime(entry_id_str, fmt)
            break
        except Exception:
            continue
    if dt is None:
        try:
            dt = datetime.fromisoformat(entry_id_str)
        except Exception:
            print("edit_entry: could not parse entry_id:", entry_id_str)
            return

    # determine quarter file
    quarter = (dt.month - 1) // 3 + 1
    quarter_filename = f"{dt.year}-Q{quarter}.md"
    journal_file = JOURNAL_PATH / quarter_filename

    if not journal_file.exists():
        print("edit_entry: journal file not found:", journal_file)
        return

    parsedEntries = parseEntries(thepath=journal_file, notebookpath=NOTEBOOK_PATH)
    for entry in parsedEntries["entries"]:
        if entry.get('date') == dt:
            entry["content"] = [content]

            writeFile(filepath=journal_file,
                      prefix=parsedEntries["prefix"],
                      entries=parsedEntries["entries"])
            return


def get_entries(start_date):
    # month to quarter: (i-1)//3+1
    # check if ealiest date of the quarter of that file is before start_date:
    # quarter = (start_date.month - 1) // 3 + 1
    # 1-3 4-6 7-9 10-12

    result = []
    for journal_file in JOURNAL_PATH.glob("**/*.md"):

        m = JOURNAL_FILE_REGEX.match(journal_file.name)
        if m is not None:
            year = int(m.group(1))
            quarter = int(m.group(2))
            journal_file_date = datetime(year=year, month=((quarter*3)+1), day=1) - timedelta(microseconds=-1)
            if journal_file_date < start_date:
                continue

        # Parse entries from the markdown file
        # TODO: Replace 'file.md' with actual markdown file path
        results = parseEntries(thepath=journal_file, notebookpath=NOTEBOOK_PATH)["entries"]
        for entry in results:
            dt = entry.get('date')
            if not isinstance(dt, datetime):
                continue
            if dt.date() < start_date:
                continue
            result.append(entry)

    return result



def add_new_entry(title, content):
    now_date = datetime.now()
    quarter = (now_date.month - 1) // 3 + 1
    quarter_filename = f"{now_date.year}-Q{quarter}.md"
    with open(JOURNAL_PATH / quarter_filename, "a") as f:
        f.write(f"\n\n### {now_date.year}-{now_date.month}-{now_date.day} {now_date.hour}:{now_date.minute} {title}\n\n{content}\n\n")


# Modify the rendering of entries to fix image paths
def fix_image_paths(content, rel_path):
    """Convert relative image paths to /media/ URLs"""
    def repl(m):
        is_image = m.group(1) == '!'
        title = m.group(2)
        path = m.group(3)
        
        if path.startswith(('http://', 'https://')):
            return m.group(0)

        return f'{m.group(1)}[{title}](/{rel_path}/{path})'

    # Match both images and links: ![title](path) or [title](path)
    pattern = r'(!?)\[([^\]]*)\]\(([^)]+)\)'
    return re.sub(pattern, repl, content)


@app.route('/')
@app.route('/<path:mypath>')
def index(mypath="/"):
    if mypath.startswith("/"):
        mypath = "." + mypath

    show_journal = True
    title = "[" + NOTEBOOK_NAME + "] journal"

    # Get selected tags from query parameters
    selected_tags = request.args.getlist('tags')
    mypath_tags = None
    mypath_tag = None

    mypath_content = None
    if mypath != "_journal":
        p = NOTEBOOK_PATH / mypath
        if not p.exists():
            return "not found."
        if not p.is_relative_to(NOTEBOOK_PATH):
            return "access denied."

        if p.is_dir():
            show_journal = False
            folders = []
            files = []
            for child in p.iterdir():
                if HIDE_DOTFILES and child.name.startswith("."):
                    continue
                if child.is_dir():
                    folders.append(child)
                else:
                    files.append(child)

            folders.sort(key=lambda s: s.name.lower())
            files.sort(key=lambda s: s.name.lower())
            entries = []
            if NOTEBOOK_PATH != p:
                entries.append("<tr><td>📁</td><td><a href=\"../\">../</a></td><td></td></tr>")

            for the_folder in folders:
                entries.append("<tr><td>📁</td><td><a href=\"./" + html.escape(the_folder.name) + "/\">" + html.escape(the_folder.name) + "/</a></td><td></td></tr>")
            for the_file in files:
                entries.append("<tr><td>📄</td><td><a style=\"margin-right:1em\" href=\"./" + html.escape(the_file.name) + "\">" + html.escape(the_file.name) + "</a></td><td>" + datetime.fromtimestamp(the_file.stat().st_mtime).strftime("%d.%m.%Y %H:%M") + "</td></tr>")

            content = '<table>\n' + ("\n".join(entries)) + "</table>\n"
            mypath_content = render_template("folder.html", title=mypath, content=content)

        elif p.is_file():

            if p.suffix == MARKDOWN_SUFFIX:

                show_journal = True
                mypath_content = []
                mypath_tags = []
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        mypath_content.append(line)
                        for line_tag in TAG_REGEX.findall(line):
                            if line_tag not in mypath_tags:
                                mypath_tags.append(line_tag)
                mypath_content = md.render("".join(mypath_content))

                mypath_relative = p.relative_to(NOTEBOOK_PATH)
                title = "[" + NOTEBOOK_NAME + "] " + mypath_relative.as_posix()
                mypath_relative_parts = list(mypath_relative.parts)
                mypath_relative_parts[-1] = p.stem
                mypath_tag = TAG_NAMESPACE_SEPARATOR.join(mypath_relative_parts)
                if mypath_tag not in mypath_tags:
                    mypath_tags.append(mypath_tag)

            else:

                return send_from_directory(directory=NOTEBOOK_PATH, path=p.relative_to(NOTEBOOK_PATH))


    if show_journal:

        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        
        # Get start date string from query parameters (format: YYYY-MM-DD)
        start_str = request.args.get('start', '')

        today_date = datetime.now().date()

        # default start = today - 8 weeks
        default_start_date = today_date - timedelta(weeks=8)

        # If user provided a start date, try to parse it; otherwise use default
        start_date = default_start_date
        if start_str:
            try:
                parsed = datetime.strptime(start_str, '%Y-%m-%d').date()
                start_date = parsed
            except Exception:
                start_date = default_start_date

        date_filtered = get_entries(start_date=start_date)

        # at least one tag from mypath_tags needs to be present
        date_filtered_tmp = []
        if mypath_tags is not None:
            for entry in date_filtered:
                for mypath_tag in mypath_tags:
                    if mypath_tag in entry["tags"]:
                        date_filtered_tmp.append(entry)
                        break
            date_filtered = date_filtered_tmp

        # Then apply tag filtering (entry must have all selected tags)
        if selected_tags:
            filtered_entries = [
                entry for entry in date_filtered 
                if all(tag in entry["tags"] for tag in selected_tags)
            ]
        else:
            filtered_entries = date_filtered

        # regex search param
        q = request.args.get('q', '').strip()

        regex_error = False
        regex = None
        if q:
            try:
                regex = re.compile(q, re.IGNORECASE)
            except re.error:
                regex_error = True

        # apply regex filter if compiled; if invalid regex produce no matches and flag error
        if regex and not regex_error:
            def matches_regex(entry):
                if regex.search(entry.get('title', '')):
                    return True
                if regex.search(entry.get('content', '')):
                    return True
                for t in entry.get('tags', []):
                    if regex.search(t):
                        return True
                return False
            filtered_entries = [e for e in filtered_entries if matches_regex(e)]
        elif regex_error:
            filtered_entries = []

        for e in filtered_entries:
            # Fix image paths before rendering markdown
            e["markdown"] = "\n".join(e["content"])
            e["content"] = md.render(fix_image_paths(e["markdown"], e["rel_path"].parent.as_posix()))

        # compute available_tags and tag counts from the currently filtered entries (keep selected tags visible)
        tag_counts = {}
        for entry in filtered_entries:
            for tag in entry.get('tags', []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        # ensure selected tags are present in counts (show zero if needed)
        for t in selected_tags:
            tag_counts.setdefault(t, 0)
        available_tags = sorted(set(tag_counts.keys()) | set(selected_tags))


        # Implement pagination
        start = (page - 1) * ENTRIES_PER_PAGE
        end = start + ENTRIES_PER_PAGE
        paginated_entries = filtered_entries[start:end]
        total_pages = (len(filtered_entries) + ENTRIES_PER_PAGE - 1) // ENTRIES_PER_PAGE if filtered_entries else 1

        new_entry_tags = list(selected_tags)
        if mypath_tag is not None:
            new_entry_tags.insert(0, mypath_tag)

        return render_template(
            "main.html",
            showOpenInBrower=False,
            showOpenInVSCode=True,
            mypath=mypath,
            mypath_tags=mypath_tags,
            new_entry_tags=new_entry_tags,
            title=title,
            mypath_content=mypath_content,
            JS_ENTRY_ID_FORMAT=JS_ENTRY_ID_FORMAT,
            entries=paginated_entries,
            all_tags=available_tags,
            selected_tags=selected_tags,
            tag_counts=tag_counts,
            page=page,
            total_pages=total_pages,
            has_prev=page > 1,
            has_next=page < total_pages,
            start=start_date.strftime('%Y-%m-%d'),
            q=q,
            regex_error=regex_error
        )
    
    else:

        return render_template(
            "folder.html",
            title=title,
            content=mypath_content
        )


# Add new route for creating entries
@app.route('/new', methods=['POST'])
def new_entry():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    
    if title and content:
        add_new_entry(title, content)
    
    return redirect('/')

# Add new route for editing entries
@app.route('/edit/<entry_id>', methods=['POST'])
def edit_entry_route(entry_id):
    content = request.form.get('content', '').strip()

    remove_tag = request.form.get('remove_tag') or request.args.get('remove_tag')
    if remove_tag:
        content = re.sub("\\bx" + remove_tag + "\\b", '', content)

    edit_entry(entry_id_str=entry_id, content=content)
    
    # Preserve filter parameters (prefer POSTed form values, fall back to query args)
    params = []
    
    tags = request.form.getlist('tags') or request.args.getlist('tags')
    for tag in tags:
        params.append(f'tags={tag}')

    start = request.form.get('start') or request.args.get('start')
    if start:
        params.append(f'start={start}')

    q = request.form.get('q') or request.args.get('q')
    if q:
        params.append(f'q={q}')
        
    page = request.form.get('page') or request.args.get('page')
    if page:
        params.append(f'page={page}')


    redirect_url = '/'
    if params:
        redirect_url += '?' + '&'.join(params)
        
    return redirect(redirect_url)

@app.route('/upload_image', methods=['POST'])
def upload_image():
    MEDIA_FOLDER.mkdir(parents=True, exist_ok=True)
    file = request.files.get('image')
    if not file:
        return jsonify({'error': 'no file'}), 400
    if not (file.content_type and file.content_type.startswith('image')):
        return jsonify({'error': 'not an image'}), 400

    # determine extension
    orig_name = secure_filename(file.filename or '')
    ext = Path(orig_name).suffix
    if not ext:
        ext = mimetypes.guess_extension(file.content_type) or '.png'

    filename = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + uuid.uuid4().hex + ext
    dest = MEDIA_FOLDER / filename
    file.save(str(dest))

    # return URL that the client can insert (served by /media/<filename>)
    return jsonify({'url': f'/media/{filename}'})

@app.route('/open_in_vscode', methods=['POST'])
def open_in_vscode():
    """
    Server-side: open the given notebook-relative path in VS Code on the server.
    Expects form data 'rel_path' (the path relative to NOTEBOOK_PATH).
    Returns JSON.
    """
    rel = request.form.get('rel_path') or (request.json and request.json.get('rel_path'))
    if not rel:
        return jsonify({'error': 'missing path'}), 400

    line_no = request.form.get('line_no') or (request.json and request.json.get('line_no'))
    if not line_no:
        return jsonify({'error': 'missing line number'}), 400

    try:
        target = (NOTEBOOK_PATH / Path(rel)).resolve()
    except Exception:
        return jsonify({'error': 'invalid path'}), 400

    # Ensure target is inside NOTEBOOK_PATH
    try:
        if not target.is_relative_to(NOTEBOOK_PATH):
            return jsonify({'error': 'access denied'}, 403)
    except AttributeError:
        # Python <3.9 fallback
        try:
            target.relative_to(NOTEBOOK_PATH)
        except Exception:
            return jsonify({'error': 'access denied'}, 403)

    if not target.exists():
        return jsonify({'error': 'file not found'}), 404

    code_cmd = shutil.which('code') or 'code'
    args = [code_cmd, '--goto', f'{str(target)}:{str(line_no)}']
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        return jsonify({'error': 'failed to launch', 'detail': str(exc)}), 500

    return jsonify({'ok': True})


if __name__ == '__main__':
    NOTEBOOK_NAME = sys.argv[1]
    app.run(debug=True, host='127.0.0.1', port=5000)

