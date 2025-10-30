#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
from flask import Flask, render_template, request, redirect
from datetime import datetime, timedelta
from markdown_it import MarkdownIt
import re
import html
from noteslib import parseEntries, writeFile, MARKDOWN_SUFFIX, TAG_NAMESPACE_SEPARATOR, TAG_REGEX, JOURNAL_FILE_REGEX
from pathlib import Path
import uuid
import mimetypes
from werkzeug.utils import secure_filename
from flask import send_from_directory, jsonify
import subprocess
import json
import shutil


app = Flask(__name__)
md = MarkdownIt("gfm-like")
NOTEBOOK_NAME = os.getenv('NOTEBOOK_NAME', 'notes')

code_cmd = shutil.which('code') or 'code'
EDITOR_COMMAND_LIST = [code_cmd, "--goto", "{filepath}:{line_no}"]
EDITOR_COMMAND = os.getenv('EDITOR_COMMAND', None)
if EDITOR_COMMAND is not None:
    EDITOR_COMMAND_LIST = json.loads(EDITOR_COMMAND)


ENTRIES_PER_PAGE = 25
HIDE_DOTFILES = True

# add media folder (inside notebook path)
NOTEBOOK_PATH = Path(os.environ.get('NOTES_PATH', '.')).resolve()
MEDIA_FOLDER = NOTEBOOK_PATH / "media"
JOURNAL_PATH = NOTEBOOK_PATH / "journal"

JS_ENTRY_ID_FORMAT = "%Y%m%d_%H%M%S"
NO_ADDITIONAL_TAGS = "[only selected tags]"


def remove_tag(entryId, tag_to_remove):
    dt = datetime.strptime(entryId, JS_ENTRY_ID_FORMAT)

    # determine quarter file
    quarter = (dt.month - 1) // 3 + 1
    quarter_filename = f"{dt.year}-Q{quarter}.md"
    journal_file = JOURNAL_PATH / quarter_filename

    if not journal_file.exists():
        print("remove_tag: journal file not found:", journal_file)
        return False

    parsedEntries = parseEntries(thepath=journal_file, notebookpath=NOTEBOOK_PATH)
    for entry in parsedEntries["entries"]:
        if entry.get('date') == dt:
            newcontent = []
            for line in entry["content"]:
                newcontent.append(re.sub("\\bx" + tag_to_remove + "\\b", '', line))

            entry["content"] = newcontent
            entry["tags"].remove(tag_to_remove)

            writeFile(filepath=journal_file,
                      prefix=parsedEntries["prefix"],
                      entries=parsedEntries["entries"])
            return True

    print("remove_tag: entry not found for id:", entryId)
    return False


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


def parseMarkdown(p):
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

    return show_journal, mypath_content, mypath_tags, mypath_tag, title


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

        if not p.is_relative_to(NOTEBOOK_PATH):
            return "access denied."

        if p.is_dir():
            if (p / ".hidden").exists():
                return "access denied."

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

        else:

            if p.is_file():

                if p.suffix == MARKDOWN_SUFFIX:
                    show_journal, mypath_content, mypath_tags, mypath_tag, title = parseMarkdown(p=p)

                else:

                    return send_from_directory(directory=NOTEBOOK_PATH, path=p.relative_to(NOTEBOOK_PATH).as_posix())

            else:

                if p.suffix != MARKDOWN_SUFFIX:
                    p = p.parent / (p.name + MARKDOWN_SUFFIX)
                    if p.is_file():
                        show_journal, mypath_content, mypath_tags, mypath_tag, title = parseMarkdown(p=p)
                        mypath = mypath + MARKDOWN_SUFFIX

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
                for mypath_tag_search in mypath_tags:
                    if mypath_tag_search in entry["tags"]:
                        date_filtered_tmp.append(entry)
                        break
            date_filtered = date_filtered_tmp

        # Then apply tag filtering (entry must have all selected tags)
        if selected_tags:
            selected_tags_search = list(selected_tags)
            no_additional_selected = False
            if NO_ADDITIONAL_TAGS in selected_tags_search:
                selected_tags_search.remove(NO_ADDITIONAL_TAGS)
                no_additional_selected = True

            filtered_entries = []
            for entry in date_filtered:

                if all(tag in entry["tags"] for tag in selected_tags_search):
                    has_no_additional_tags = False
                    if len(entry["tags"]) == len(selected_tags_search):
                        entry["tags"].append(NO_ADDITIONAL_TAGS)
                        has_no_additional_tags = True

                    if not no_additional_selected or has_no_additional_tags:
                        filtered_entries.append(entry)

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
                for t in entry.get('content', []):
                    if regex.search(t):
                        return True
                for t in entry.get('tags', []):
                    if regex.search(t):
                        return True
                return False
            filtered_entries = [e for e in filtered_entries if matches_regex(e)]
        elif regex_error:
            filtered_entries = []

        for e in filtered_entries:
            e["content"] = md.render("\n".join(e["content"]))

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
            mypath=mypath,
            mypath_tags=mypath_tags,
            new_entry_tags=new_entry_tags,
            title=title,
            mypath_content=mypath_content,
            JS_ENTRY_ID_FORMAT=JS_ENTRY_ID_FORMAT,
            entries=paginated_entries,
            all_tags=available_tags,
            selected_tags=selected_tags,
            NO_ADDITIONAL_TAGS=NO_ADDITIONAL_TAGS,
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

@app.route('/remove_tag', methods=['POST'])
def remove_tag_route():
    entryId = request.form.get('entryId') or request.args.get('entryId')
    tag_to_remove = request.form.get('remove_tag') or request.args.get('remove_tag')

    result = remove_tag(entryId=entryId, tag_to_remove=tag_to_remove)
    if result:
        return jsonify({'ok': True})

    return jsonify({'error': 'failed to remove tag'}), 400


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

@app.route('/edit', methods=['POST'])
def edit():
    """
    Server-side: open the given notebook-relative path in editor on the server.
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

    #code --goto "{filepath}:{line_no}"'
    args = list(EDITOR_COMMAND_LIST)
    for i in range(len(args)):
        args[i] = args[i].replace("{filepath}", str(target)).replace("{line_no}", str(line_no))
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        return jsonify({'error': 'failed to launch', 'detail': str(exc)}), 500

    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5000)

