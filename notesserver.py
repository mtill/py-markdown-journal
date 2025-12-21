#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import sys
import os
import re
import html
from pathlib import Path
import subprocess
import json
import shutil
from werkzeug.utils import secure_filename
from noteslib import parseEntries, writeFile, MARKDOWN_SUFFIX, ENTRY_PREFIX, TAG_PREFIX, TAG_NAMESPACE_SEPARATOR, TAG_REGEX, JOURNAL_FILE_REGEX
from datetime import datetime, timedelta
from flask import Flask, redirect, render_template, request, make_response, send_from_directory, jsonify
from markdown_it import MarkdownIt


config = {}
NOTESSERVER_CONFIG_FILE = os.getenv("NOTESSERVER_CONFIG_FILE", None)
if NOTESSERVER_CONFIG_FILE is not None:
    config_file = Path(NOTESSERVER_CONFIG_FILE)
    print("Loading config from", config_file.as_posix())
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)


def _set_editor_path(command_list):
    if command_list is not None and len(command_list) > 0 and not Path(command_list[0]).is_absolute():
        which_path = shutil.which(command_list[0])
        if which_path is not None:
            command_list[0] = which_path
    return command_list


app = Flask(__name__)
md = MarkdownIt("gfm-like")

NOTEBOOK_PATH = Path(config.get("NOTEBOOK_PATH", ".")).resolve()
NOTEBOOK_NAME = config.get("NOTEBOOK_NAME", NOTEBOOK_PATH.name)
BASIC_SECRET = config.get("BASIC_SECRET", None)
DEFAULT_JOURNAL_TIMEWINDOW_IN_WEEKS = config.get('DEFAULT_JOURNAL_TIMEWINDOW_IN_WEEKS', 2)
JOURNAL_ENTRY_DATE_FORMAT = config.get('JOURNAL_ENTRY_DATE_FORMAT', '%a %d.%m. %H:%M')

NEW_JOURNAL_ENTRY_DEFAULT_TAGS_LIST = config.get('NEW_JOURNAL_ENTRY_DEFAULT_TAGS_LIST', ["inbox"])
SORT_TAGS_BY_NAME = config.get('SORT_TAGS_BY_NAME', False)
HIDE_DOTFILES = config.get('HIDE_DOTFILES', True)

EDITOR_COMMAND_LIST = _set_editor_path(command_list=config.get("EDITOR_COMMAND_LIST", ["code", "{filepath}"]))
EDITOR_GOTO_COMMAND_LIST = _set_editor_path(command_list=config.get("EDITOR_GOTO_COMMAND_LIST", ["code", "--goto", "{filepath}:{line_no}"]))

ALT_EDITOR_COMMAND_LIST = _set_editor_path(command_list=config.get("ALT_EDITOR_COMMAND_LIST", EDITOR_COMMAND_LIST))
ALT_EDITOR_GOTO_COMMAND_LIST = _set_editor_path(command_list=config.get("ALT_EDITOR_GOTO_COMMAND_LIST", EDITOR_GOTO_COMMAND_LIST))

INDEX_PAGE_NAME = config.get("INDEX_PAGE_NAME", "index.md")   # set to None to disable index page special handling
NO_JOURNAL_ENTRIES_ON_INDEX_PAGES = config.get("NO_JOURNAL_ENTRIES_ON_INDEX_PAGES", False)

JOURNAL_PATH = NOTEBOOK_PATH / config.get("JOURNAL_PATH", "journal")
MEDIA_PATH = NOTEBOOK_PATH / config.get("MEDIA_PATH", "media")

NO_ADDITIONAL_TAGS = config.get("NO_ADDITIONAL_TAGS", "[only selected tags]")
INCLUDE_SUBTAGS = config.get("INCLUDE_SUBTAGS", True)

TASKS = config.get("TASKS", {})

JS_ENTRY_ID_FORMAT = "%Y%m%d_%H%M%S"
MYPATH_TAG_REGEX = re.compile("\\s+")
SECRET_COOKIE_NAME = 'basic_secret'
SECRET_COOKIE_MAX_AGE=365*24*60*60
ACCESS_DENIED_MESSAGE_DICT = {"error": "access denied: invalid secret. Please go to <a href=\"/_set_key\">/_set_key</a> to set the secret."}
HEADING_REGEX = re.compile(r'^(#{1,6})\s+(.*)$')

QUICKLAUNCH_HTML = None
QUICKLAUNCH_PATH = NOTEBOOK_PATH / ".quicklaunch.html"
if QUICKLAUNCH_PATH.is_file():
    with open(QUICKLAUNCH_PATH, "r", encoding="utf-8") as f:
        QUICKLAUNCH_HTML = f.read()

CUSTOM_HEADER_CONTENT = None
CUSTOM_HEADER_PATH = NOTEBOOK_PATH / ".header.html"
if CUSTOM_HEADER_PATH.is_file():
    with open(CUSTOM_HEADER_PATH, "r", encoding="utf-8") as f:
        CUSTOM_HEADER_CONTENT = f.read()


def check_secret():
    return BASIC_SECRET is None or len(BASIC_SECRET) == 0 or BASIC_SECRET == request.cookies.get(SECRET_COOKIE_NAME, '')


def remove_tag(rel_path: str, entryId: str, tag_to_remove: str):
    dt = datetime.strptime(entryId, JS_ENTRY_ID_FORMAT)

    if rel_path.startswith("/"):
        rel_path = rel_path[1:]

    journal_file = NOTEBOOK_PATH / rel_path
    if not journal_file.relative_to(NOTEBOOK_PATH):
        return False, "access denied."

    if not journal_file.exists():
        return False, "remove_tag: journal file not found: " + journal_file.as_posix()

    tag_removal_regex = re.compile("\\b" + TAG_PREFIX + re.escape(tag_to_remove) + "\\b", re.IGNORECASE)

    parsedEntries = parseEntries(thepath=journal_file, notebookpath=NOTEBOOK_PATH)
    for entry in parsedEntries["entries"]:
        if entry.get('date') == dt:
            newcontent = []
            for line in entry["content"]:
                newcontent.append(tag_removal_regex.sub('', line))
                #newcontent.append(re.sub("\\b" + TAG_PREFIX + tag_to_remove + "\\b", '', line, flags=re.IGNORECASE))

            entry["content"] = newcontent
            if tag_to_remove in entry["tags"]:
                entry["tags"].remove(tag_to_remove)

            writeFile(filepath=journal_file,
                      prefix=parsedEntries["prefix"],
                      entries=parsedEntries["entries"])
            return True, None

    return False, "remove_tag: entry not found for id: " + entryId


def _emphasize_tag_in_line(line):
    return TAG_REGEX.sub(lambda m: m.group(1) + "<em>" + TAG_PREFIX + m.group(2) + "</em>", line)


def get_entries(start_date, stop_date, related_tags, selected_tags, q):
    # month to quarter: (i-1)//3+1

    relevant_files = []
    result = []
    for journal_file in JOURNAL_PATH.glob("**/*.md"):
        m = JOURNAL_FILE_REGEX.match(journal_file.name)
        if m is not None:
            year = int(m.group(1))
            quarter = int(m.group(2))
            quarter_month = ((quarter - 1) * 3) + 1
            journal_file_earliest_date = datetime(year=year, month=quarter_month, day=1)

            next_quarter = quarter + 1
            next_quarter_year = year
            if next_quarter > 4:
                next_quarter = 1
                next_quarter_year += 1
            next_quarter_month = ((next_quarter - 1) * 3) + 1
            journal_file_latest_date = datetime(year=next_quarter_year, month=next_quarter_month, day=1) - timedelta(microseconds=1)

            if not (start_date > journal_file_latest_date or stop_date < journal_file_earliest_date):
                relevant_files.append(journal_file)

        else:   # journal file name did not match regex, not sure what's in --> parsing that file:", journal_file.name)
            relevant_files.append(journal_file)

    for journal_file in relevant_files:
        parsed_entries = parseEntries(thepath=journal_file, notebookpath=NOTEBOOK_PATH, date_format=JOURNAL_ENTRY_DATE_FORMAT)["entries"]
        for entry in parsed_entries:
            if entry["date"] >= start_date and entry["date"] <= stop_date:
                result.append(entry)
        parsed_entries = None

    # at least one tag from related_tags needs to be present
    result_tmp = []
    if related_tags is not None and len(related_tags) != 0:
        for entry in result:
            added_this = False

            for related_tag in related_tags:
                for t in entry["tags"]:
                    if related_tag == t or (INCLUDE_SUBTAGS and t.startswith(related_tag + TAG_NAMESPACE_SEPARATOR)):
                        result_tmp.append(entry)
                        added_this = True
                        break

                if added_this:
                    break

        result = result_tmp

    # Then apply tag filtering (entry must have all selected tags)
    if selected_tags is not None and len(selected_tags) != 0:
        selected_tags_search = list(selected_tags)
        no_additional_selected = False
        if NO_ADDITIONAL_TAGS in selected_tags_search:
            selected_tags_search.remove(NO_ADDITIONAL_TAGS)
            no_additional_selected = True

        result_tmp = []
        for entry in result:
            if all(tag in entry["tags"] for tag in selected_tags_search):
                has_no_additional_tags = False
                if len(entry["tags"]) == len(selected_tags_search):
                    entry["tags"].append(NO_ADDITIONAL_TAGS)
                    has_no_additional_tags = True

                if not no_additional_selected or has_no_additional_tags:
                    result_tmp.append(entry)
        result = result_tmp

    regex_error = False
    regex = None
    if q is not None and len(q) != 0:
        try:
            regex = re.compile(q, re.IGNORECASE)
        except re.error:
            regex_error = True
            result = []

        # apply regex filter if compiled; if invalid regex produce no matches and flag error
        if not regex_error and regex is not None:
            def matches_regex(entry):
                for t in entry.get('content', []):
                    if regex.search(t):
                        return True
                for t in entry.get('tags', []):
                    if regex.search(t):
                        return True
                return False
            result = [e for e in result if matches_regex(e)]

    return result, regex_error


def _find_tag_wiki_page(tag):
    tag_path_str = tag.replace(TAG_NAMESPACE_SEPARATOR, "/")
    tag_path = NOTEBOOK_PATH / (tag_path_str + MARKDOWN_SUFFIX)

    if tag_path.is_file():
        return ("/" + tag_path.relative_to(NOTEBOOK_PATH).as_posix(), True)

    if tag_path.parent.is_dir():
        for i in tag_path.parent.iterdir():
            if i.is_file() and i.name.lower() == tag_path.name.lower():
                return ("/" + i.relative_to(NOTEBOOK_PATH).as_posix(), True)

    return ("/" + tag_path.relative_to(NOTEBOOK_PATH).as_posix(), False)


def parseMarkdown(p):
    mypath_content = []
    mypath_tag = None
    related_tags = {}
    headings = []
    heading_counter = 0

    mypath_relative = p.relative_to(NOTEBOOK_PATH)
    title = "/" + mypath_relative.as_posix()
    mypath_relative_parts = list(mypath_relative.parts)
    if INDEX_PAGE_NAME is not None and p.name == INDEX_PAGE_NAME:
        mypath_relative_parts.pop()
    else:
        mypath_relative_parts[-1] = p.stem
    if len(mypath_relative_parts) != 0:
        mypath_relative_parts = map(lambda s: MYPATH_TAG_REGEX.sub("", s).lower(), mypath_relative_parts)
        mypath_tag = TAG_NAMESPACE_SEPARATOR.join(mypath_relative_parts)
        related_tags[mypath_tag] = True

    if p.is_file():
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                for line_tag in TAG_REGEX.findall(line):
                    line_tag = line_tag[1].lower()
                    related_tags[line_tag] = True

                heading_match = HEADING_REGEX.match(line)
                if heading_match:
                    heading_level = len(heading_match.group(1))
                    heading_text = heading_match.group(2).strip()
                    headings.append((heading_level, heading_text))
                    line = f'<h{heading_level} id="heading-{heading_counter}">{heading_text}</h{heading_level}>\n\n'
                    heading_counter += 1

                mypath_content.append(_emphasize_tag_in_line(line=line))

        mypath_content = md.render("".join(mypath_content))

    else:
        mypath_content = "<h2>Not Found</h2><p>The requested path does not exist: <b>/" + html.escape(p.relative_to(NOTEBOOK_PATH).as_posix()) + "</b></p>"

    return mypath_content, related_tags.keys(), mypath_tag, title, headings


@app.route('/', methods=['GET'])
@app.route('/<path:mypath>', methods=['GET'])
def index(mypath="/"):
    if not check_secret():
        return jsonify(ACCESS_DENIED_MESSAGE_DICT), 403

    if mypath.startswith("/"):
        mypath = "." + mypath

    title = "/_journal"

    # Get selected tags from query parameters
    selected_tags = request.args.getlist('tags')
    if selected_tags is None:
        selected_tags = []

    related_tags = None
    mypath_tag = None
    headings = []

    mypath_content = None
    if mypath != "_journal":
        p = NOTEBOOK_PATH / mypath

        if not p.is_relative_to(NOTEBOOK_PATH):
            return "access denied."

        if p.is_dir():
            if (p / ".hidden").exists():
                return "access denied."

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
                entries.append({"name": "..", "is_folder": True})

            for the_folder in folders:
                entries.append({"name": the_folder.name, "is_folder": True, "absolute_path": "/" + the_folder.relative_to(NOTEBOOK_PATH).as_posix() + "/"})
            for the_file in files:
                entries.append({"name": the_file.name, "is_folder": False, "absolute_path": "/" + the_file.relative_to(NOTEBOOK_PATH).as_posix(), "mtime": datetime.fromtimestamp(the_file.stat().st_mtime).strftime("%d.%m.%Y %H:%M")})

            delete_msg = request.args.get('delete_msg', '')
            return render_template("folder.html",
                                   NOTEBOOK_NAME=NOTEBOOK_NAME,
                                   abs_path="/" + p.relative_to(NOTEBOOK_PATH).as_posix(),
                                   entries=entries,
                                   delete_msg=delete_msg,
                                   QUICKLAUNCH_HTML=QUICKLAUNCH_HTML,
                                   CUSTOM_HEADER_CONTENT=CUSTOM_HEADER_CONTENT)

        else:

            if p.is_file():
                if p.suffix == MARKDOWN_SUFFIX:
                    mypath_content, related_tags, mypath_tag, title, headings = parseMarkdown(p=p)
                else:
                    return send_from_directory(directory=NOTEBOOK_PATH, path=p.relative_to(NOTEBOOK_PATH).as_posix())

            else:

                if len(p.suffix) == 0:
                    p = p.parent / (p.name + MARKDOWN_SUFFIX)
                    mypath = mypath + MARKDOWN_SUFFIX
                    mypath_content, related_tags, mypath_tag, title, headings = parseMarkdown(p=p)
                elif p.suffix == MARKDOWN_SUFFIX:
                    mypath_content, related_tags, mypath_tag, title, headings = parseMarkdown(p=p)
                else:
                    return jsonify({'error': 'file not found: ' + p.as_posix()}), 400


        if INDEX_PAGE_NAME is not None and p.name == INDEX_PAGE_NAME and NO_JOURNAL_ENTRIES_ON_INDEX_PAGES:
            return render_template(
                "main_nojournal.html",
                NOTEBOOK_NAME=NOTEBOOK_NAME,
                mypath=mypath,
                title=title,
                mypath_content=mypath_content,
                headings=headings,
                QUICKLAUNCH_HTML=QUICKLAUNCH_HTML,
                CUSTOM_HEADER_CONTENT=CUSTOM_HEADER_CONTENT
            )


    today_date = datetime.now()
    start_str = request.args.get('start', None)
    stop_str = request.args.get('stop', None)

    # default start = today - DEFAULT_JOURNAL_TIMEWINDOW_IN_WEEKS weeks
    default_start_date = today_date - timedelta(weeks=DEFAULT_JOURNAL_TIMEWINDOW_IN_WEEKS)

    # If user provided a start date, try to parse it; otherwise use default
    start_date = default_start_date
    stop_date = today_date
    if start_str is not None and len(start_str) != 0:
        try:
            parsed = datetime.strptime(start_str, '%Y-%m-%d')
            start_date = parsed
        except Exception:
            start_date = default_start_date
    if stop_str is not None and len(stop_str) != 0:
        try:
            parsed = datetime.strptime(stop_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(microseconds=1)
            stop_date = parsed
        except Exception:
            stop_date = today_date

    # regex search param
    q = request.args.get('q', None)
    q = '' if q is None else q.strip()

    filtered_entries, regex_error = get_entries(start_date=start_date, stop_date=stop_date, related_tags=related_tags, selected_tags=selected_tags, q=q)
    for e in filtered_entries:
        econtent = []
        for line in e["content"]:
            econtent.append(_emphasize_tag_in_line(line=line))
        e["content"] = md.render("\n".join(econtent))

    tag_freshness = {}
    tag_counts = {}
    for entry in filtered_entries:
        for tag in entry['tags']:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            if tag not in tag_freshness:
                tag_freshness[tag] = entry['date']
            else:
                if entry['date'] > tag_freshness[tag]:
                    tag_freshness[tag] = entry['date']

    # ensure selected tags are present in counts (show zero if needed)
    for t in selected_tags:
        tag_counts.setdefault(t, 0)
    available_tags = set(tag_counts.keys() | selected_tags)   # by using sets (and not lists), duplicates will be removed

    if SORT_TAGS_BY_NAME:
        available_tags = sorted(available_tags)
    else:
        available_tags = sorted(available_tags, key=lambda at: (tag_freshness[at], at), reverse=True)

    tagWikiPages = {}
    for a in available_tags:
        tagWikiPages[a] = _find_tag_wiki_page(tag=a)

    new_entry_tags = list(NEW_JOURNAL_ENTRY_DEFAULT_TAGS_LIST)
    if mypath_tag is not None and mypath_tag not in new_entry_tags:
        new_entry_tags.append(mypath_tag)
    for s_t in selected_tags:
        if s_t != NO_ADDITIONAL_TAGS and s_t != mypath_tag and s_t not in new_entry_tags:
            new_entry_tags.append(s_t)

    new_entry_tags_str = None
    if len(new_entry_tags) > 0:
        new_entry_tags_str = " ".join([TAG_PREFIX + t for t in new_entry_tags])

    latest_journal_page = "/" + ((JOURNAL_PATH / (today_date.strftime("%Y-Q") + str((today_date.month - 1)//3 + 1) + MARKDOWN_SUFFIX)).relative_to(NOTEBOOK_PATH).as_posix())

    return render_template(
        "main.html",
        mypath=mypath,
        related_tags=related_tags,
        new_entry_tags_str=new_entry_tags_str,
        NOTEBOOK_NAME=NOTEBOOK_NAME,
        latest_journal_page=latest_journal_page,
        title=title,
        mypath_content=mypath_content,
        headings=headings,
        JS_ENTRY_ID_FORMAT=JS_ENTRY_ID_FORMAT,
        entries=filtered_entries,
        all_tags=available_tags,
        tagWikiPages=tagWikiPages,
        selected_tags=selected_tags,
        tag_counts=tag_counts,
        start=start_date.strftime('%Y-%m-%d'),
        stop=stop_date.strftime('%Y-%m-%d'),
        q=q,
        regex_error=regex_error,
        NO_ADDITIONAL_TAGS=NO_ADDITIONAL_TAGS,
        QUICKLAUNCH_HTML=QUICKLAUNCH_HTML,
        CUSTOM_HEADER_CONTENT=CUSTOM_HEADER_CONTENT,
        ENTRY_PREFIX=ENTRY_PREFIX
    )


@app.route('/_remove_tag', methods=['POST'])
def remove_tag_route():
    if not check_secret():
        return jsonify(ACCESS_DENIED_MESSAGE_DICT), 403

    rel_path = request.form.get('rel_path') or request.args.get('rel_path')
    entryId = request.form.get('entryId') or request.args.get('entryId')
    tag_to_remove = request.form.get('remove_tag') or request.args.get('remove_tag')

    msg = "invalid request"
    if rel_path is not None and entryId is not None and tag_to_remove is not None:
        is_success, msg = remove_tag(rel_path=rel_path, entryId=entryId, tag_to_remove=tag_to_remove)
        if is_success:
            return jsonify({'ok': True})

    return jsonify({'error': msg}), 400


@app.route("/_set_key", methods=['GET'])
def get_set_key_form():
    #key = request.cookies.get(SECRET_COOKIE_NAME, '')
    return render_template("setkey.html",
                           key='',
                           was_updated=False,
                           QUICKLAUNCH_HTML=QUICKLAUNCH_HTML,
                           CUSTOM_HEADER_CONTENT=CUSTOM_HEADER_CONTENT)


@app.route("/_set_key", methods=['POST'])
def set_key():
    key = request.form.get('key', '')
    if not key:
        return jsonify({'error': 'missing key'}), 400

    response = make_response(render_template("setkey.html",
                                             key=key,
                                             was_updated=True,
                                             QUICKLAUNCH_HTML=QUICKLAUNCH_HTML,
                                             CUSTOM_HEADER_CONTENT=CUSTOM_HEADER_CONTENT
                                            )
                            )
    response.set_cookie(SECRET_COOKIE_NAME, key, max_age=SECRET_COOKIE_MAX_AGE)
    return response


@app.route('/_run_task/<task_id>', methods=['POST'])
def run_task(task_id):
    if not check_secret():
        return jsonify(ACCESS_DENIED_MESSAGE_DICT), 403

    command_list = TASKS.get(task_id, None)
    if command_list is None:
        return jsonify({'error': "task not specified in config file."}), 500

    command_list_copy = list(command_list)
    #command_list_copy[0] = (Path.cwd() / command_list_copy[0]).as_posix()
    command_list_copy.append(NOTEBOOK_PATH.as_posix())

    param = request.form.get('param', None)
    if param is not None:
        command_list_copy.append(param)

    try:
        subprocess.Popen(command_list_copy, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        return jsonify({'error': 'failed to run task ' + task_id, 'detail': str(exc)}), 500

    return jsonify({'ok': True})


@app.route('/_edit', methods=['POST'])
def edit():
    """
    Server-side: open the given notebook-relative path in editor on the server.
    Expects form data 'rel_path' (the path relative to NOTEBOOK_PATH).
    Returns JSON.
    """

    if not check_secret():
        return jsonify(ACCESS_DENIED_MESSAGE_DICT), 403

    rel = request.form.get('rel_path', None)
    if not rel:
        return jsonify({'error': 'missing path'}), 400

    line_no = request.form.get('line_no', None)
    open_in_alt_editor = request.form.get('open_in_alt_editor', False)

    if rel.startswith("/"):
        rel = rel[1:]
    try:
        target = (NOTEBOOK_PATH / rel).resolve()
    except Exception:
        return jsonify({'error': 'invalid path'}), 400

    if not target.is_relative_to(NOTEBOOK_PATH):
        return jsonify({'error': 'access denied'}, 403)

    if not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)

    #code --goto "{filepath}:{line_no}"'
    args = None
    if open_in_alt_editor:
        args = list(ALT_EDITOR_COMMAND_LIST) if line_no is None else list(ALT_EDITOR_GOTO_COMMAND_LIST)
    else:
        args = list(EDITOR_COMMAND_LIST) if line_no is None else list(EDITOR_GOTO_COMMAND_LIST)

    for i in range(len(args)):
        args[i] = args[i].replace("{filepath}", str(target)).replace("{line_no}", str(line_no))
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        return jsonify({'error': 'failed to launch', 'detail': str(exc)}), 500

    return jsonify({'ok': True})


@app.route('/_delete', methods=['POST'])
def delete():
    """Delete a file specified by form data 'thepath'."""
    if not check_secret():
        return jsonify(ACCESS_DENIED_MESSAGE_DICT), 403

    delete_msg = ""
    p = request.form.get('thepath', None)
    redirect_to = request.form.get("redirect_to", "/_media")
    if p is not None:
        if p.startswith("/"):
            p = p[1:]
        file_to_delete = Path(NOTEBOOK_PATH / p).resolve()
        if file_to_delete.is_relative_to(NOTEBOOK_PATH):
            if file_to_delete.exists() and file_to_delete.is_file():
                try:
                    file_to_delete.unlink()
                except Exception as e:
                    delete_msg = f"Error deleting file: {str(e)}"
            else:
                delete_msg = "File not found: " + file_to_delete.as_posix()
        else:
            delete_msg = f'access denied (not in {NOTEBOOK_PATH.as_posix()})'

    return redirect(redirect_to + (f"?delete_msg={delete_msg}" if delete_msg else ""))


@app.route('/_media')
def media_page():
    """Page to upload media and list recent uploads."""
    if not check_secret():
        return jsonify(ACCESS_DENIED_MESSAGE_DICT), 403

    today = datetime.now()
    quarter_foldername = f"{today.year}-Q{((today.month - 1) // 3) + 1}"
    media_dir = MEDIA_PATH / quarter_foldername
    media_dir.mkdir(parents=True, exist_ok=True)
    media_rel_dir_str = "/" + media_dir.relative_to(NOTEBOOK_PATH).as_posix()

    delete_msg = request.args.get('delete_msg', '')

    files = []
    for f in media_dir.iterdir():
        if f.is_file():
            files.append({
                'name': f.name,
                'mtime': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'size': f.stat().st_size,
                'url': "/" + f.relative_to(NOTEBOOK_PATH).as_posix()
            })

    # sort by mtime desc and limit
    files.sort(key=lambda x: x['mtime'], reverse=True)
    files = files[:10]

    return render_template('media.html',
                           NOTEBOOK_NAME=NOTEBOOK_NAME,
                           files=files,
                           delete_msg=delete_msg,
                           media_rel_dir_str=media_rel_dir_str,
                           CUSTOM_HEADER_CONTENT=CUSTOM_HEADER_CONTENT)


@app.route('/_upload_media', methods=['POST'])
def upload_media():
    """Accept uploaded files (any type) and save to /media/ with a unique name."""
    if not check_secret():
        return jsonify(ACCESS_DENIED_MESSAGE_DICT), 403

    today = datetime.now()
    quarter_foldername = f"{today.year}-Q{((today.month - 1) // 3) + 1}"
    media_dir = MEDIA_PATH / quarter_foldername
    media_dir.mkdir(parents=True, exist_ok=True)

    uploaded_files = request.files.getlist('file')
    if not uploaded_files or len(uploaded_files) == 0:
        return jsonify({'error': 'no file uploaded'}), 400

    uploads = []
    for uploaded_file in uploaded_files:
        orig_filename = uploaded_file.filename or ''
        safe_name = secure_filename(orig_filename) or ''
        # preserve extension from the original filename if present
        ext = os.path.splitext(safe_name)[1]
        # generate unique base name (timestamp + random counter if needed)
        base = datetime.now().strftime('%Y%m%d-%H%M%S')
        unique_name = base + ext
        target_path = media_dir / unique_name
        # ensure uniqueness if a collision occurs
        counter = 1
        while target_path.exists():
            unique_name = f"{base}-{counter}{ext}"
            target_path = media_dir / unique_name
            counter += 1

        try:
            uploaded_file.save(str(target_path))
            uploads.append({
                'url': "/" + target_path.relative_to(NOTEBOOK_PATH).as_posix(),
                'name': unique_name
            })
        except Exception as exc:
            return jsonify({'error': 'failed to save', 'detail': str(exc)}), 500

    return jsonify({'ok': True, 'uploads': uploads})



if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=int(sys.argv[1]) if len(sys.argv) > 1 else 5000)

