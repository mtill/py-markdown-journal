#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import subprocess
from flask import Flask, send_from_directory, redirect, request
from markdown_it import MarkdownIt
from noteslib import parseEntries, REFERENCE, MARKDOWN_SUFFIX, UNTAGGED_TAG, relativeImageOrLinkRegex
import compile_notes
import os
import html
from pathlib import Path
import shutil


SERVE_DIR = os.environ.get("MARKDOWN_SERVE_DIR", ".")
HIDE_DOTFILES = os.environ.get("MARKDOWN_SERVE_HIDE_DOTFILES", "True") == "True"

app = Flask(__name__)
md = MarkdownIt()
SERVE_PATH = Path(SERVE_DIR).absolute()
JOURNAL_PATH = SERVE_PATH / "journal"


def htmlresponse(title, content):
    return """<!DOCTYPE html>
 
 <html>
  <head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>""" + html.escape(title) + """</title>
  <script>
 document.addEventListener('DOMContentLoaded', (event) => {
   const controls = document.getElementById('tag-controls');
   if(!controls) return;
   const checkboxes = Array.from(controls.querySelectorAll('.tag-checkbox'));
   const entries = Array.from(document.querySelectorAll('.entry'));

  // dblclick on an entry -> request server to open the file in VSCode
  entries.forEach(e => {
    e.addEventListener('dblclick', async (ev) => {
      const loc = e.dataset.location;
      if(!loc) return;
      try {
        const res = await fetch('/_open', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({location: loc})
        });
        if(res.ok){
          e.classList.add('opening');
          setTimeout(()=> e.classList.remove('opening'), 700);
        } else {
          console.warn('open failed', res.status);
        }
      } catch(err){
        console.error(err);
      }
    }, {passive:true});
  });

  // dblclick on the prefix area -> open the page file in VSCode
  const prefix = document.getElementById('prefix_html');
  if(prefix){
    prefix.addEventListener('dblclick', async (ev) => {
      const loc = prefix.getAttribute('location') || prefix.dataset.location;
      if(!loc) return;
      prefix.classList.add('opening');
      try {
        const res = await fetch('/_open', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({location: loc})
        });
        if(!res.ok && res.status !== 204){
          console.warn('open failed', res.status);
        }
      } catch(err){
        console.error(err);
      } finally {
        setTimeout(()=> prefix.classList.remove('opening'), 700);
      }
    }, {passive:true});
  }

  // For unchecked checkboxes: show how many entries WOULD match if we added that tag
  // i.e. count entries that have ALL currently selected tags + this tag.
  function updatePotentialCounts(){
    const selected = checkboxes.filter(cb => cb.checked).map(cb => cb.value);
    checkboxes.forEach(cb => {
      const span = cb.parentElement && cb.parentElement.querySelector('.tag-count');
      if(!span) return;

      if(cb.checked){
        span.textContent = '';
        return;
      }
    
      const candidate = selected.concat([cb.value]);
      let count = 0;
      entries.forEach(e => {
        const tags = (e.dataset.tags || "").split(/\\s+/).filter(Boolean);
        // entry must include all candidate tags
        if(candidate.every(t => tags.includes(t))) count += 1;
      });
      span.textContent = '(' + count + ')';
    });
  }

   // show only entries that have ALL selected tags (AND filtering)
   function updateFilter(shouldScroll){
     const selected = checkboxes.filter(cb => cb.checked).map(cb => cb.value);
 
     entries.forEach(e => {
       const tags = (e.dataset.tags || "").split(/\\s+/).filter(Boolean);
       const match = selected.length === 0 ? true : selected.every(t => tags.includes(t));
       e.style.display = match ? "" : "none";
     });

     updatePotentialCounts();
 
     if(shouldScroll){
       const first = entries.find(e => e.style.display !== 'none');
       if(first) setTimeout(()=> first.scrollIntoView({behavior:'smooth', block:'start'}), 50);
     } else {
       // keep current viewport but ensure entries container is visible
       const container = document.getElementById("entries");
       if(container) container.scrollIntoView({behavior: "auto"});
     }
   }

   function writeHash(){
     const sel = checkboxes.filter(cb => cb.checked).map(cb => encodeURIComponent(cb.value)).join(',');
     history.replaceState(null, '', sel ? '#tags=' + sel : location.pathname + location.search);
   }
 
   function restoreFromHash(){
     const h = location.hash || '';
     const m = h.match(/tags=([^&]+)/);
     if(!m) return;
     const vals = m[1].split(',').map(decodeURIComponent);
     checkboxes.forEach(cb => { cb.checked = vals.includes(cb.value); });
   }
 
  checkboxes.forEach(cb => cb.addEventListener('change', function(){
    updateFilter(true); // scroll to first matching entry after user change
    writeHash();
  }));
 
  restoreFromHash();
  updateFilter(false);
 });
   </script>
  <style>
body {
  font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
  background: #f9fafb;
  color: #111827;
  line-height: 1.45;
  margin: 2em;
}

/* Page container and header */
.page {
  margin: 1.6rem auto;
  padding: 1.2rem;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.header .title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f1720;
}
.header .subtitle {
  color: var(--muted);
  font-size: 0.95rem;
}

/* tag controls (kept / improved) */
.tag-controls {
  position: fixed;
  top: 1rem;
  right: 1rem;
  border: 1px solid rgba(16,22,26,0.06);
  padding: .6rem;
  z-index: 2000;
  overflow: auto;
  background: #fff;
}
.tag-controls label {
  display: inline-block;
  margin: 0 .35rem .25rem 0;
  white-space: nowrap;
  font-size: 0.95rem;
}
@media (max-width:900px) { .tag-controls { max-width: 45vw; } }
@media (max-width:700px) { .tag-controls { position: static; max-width: none; margin-bottom: 1rem; } }

#entries {
}

/* entry card layout */
.entry {
  position: relative;
  background: var(--card);
  border: 1px solid #e8eaec;
  border-radius: 10px;
  padding: 1.05rem 1.15rem;
  margin: 0 0 1.2rem 0;
  box-shadow: 0 6px 20px rgba(15,20,25,0.04);
  transition: transform .12s ease, box-shadow .12s ease;
}

/* tags shown top-right of each entry */
.entry .entry-tags {
  position: absolute;
  top: 0.9rem;
  right: 1rem;
  display: flex;
  gap: .45rem;
  align-items: center;
  z-index: 2;
}
.entry .entry-tags .tag-badge {
  font-size: .72rem;
  padding: .14rem .45rem;
}

/* subtle hover */
.entry:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 30px rgba(15,20,25,0.06);
}
/* visual feedback when opening an entry */
.entry.opening { outline: 2px solid rgba(11,99,214,0.14); transform: translateY(-1px) scale(1.01); }

/* metadata (title/date) */
.entry h1, .entry h2, .entry h3 { margin: 0 0 .35rem 0; line-height: 1.15; }
.entry .meta { font-size: .88rem; color: var(--muted); margin-bottom: .6rem; }

/* tag badges */
.entry .tags { margin-bottom: .6rem; display:flex; gap:.35rem; flex-wrap:wrap; }
.entry .tag-badge {
  display: inline-block;
  background: #eef6ff;
  color: var(--accent);
  font-weight: 600;
  font-size: .78rem;
  padding: .18rem .45rem;
  border-radius: 999px;
  margin-right: .35rem;
  border: 1px solid rgba(11,99,214,0.08);
}

/* content formatting */
.entry p { margin: .45rem 0 .9rem 0; color: #222; line-height: 1.6; }
.entry ul, .entry ol { margin: .5rem 0 .9rem 1.2rem; }
.entry blockquote {
  border-left: 4px solid #e0e6ef;
  background: #fbfdff;
  margin: .6rem 0;
  padding: .6rem 1rem;
  color: #2b2f36;
  border-radius: 6px;
}

/* code blocks and inline code */
.entry pre {
  background: #0f1720;
  color: #e6eef8;
  padding: .85rem;
  border-radius: 6px;
  overflow: auto;
  margin: .7rem 0;
}
.entry code {
  background: #f3f4f6;
  padding: .12rem .28rem;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", "Courier New", monospace;
}

/* images */
.entry img { max-width: 100%; height: auto; border-radius: 8px; display: block; margin: .6rem 0; }

/* links */
.entry a { color: var(--accent); text-decoration: none; }
.entry a:hover { text-decoration: underline; }

/* responsive tweaks */
@media (max-width:900px) { .page { padding: .8rem; } .entry { padding: .9rem; } }

  </style>
  </head>
  <body>\n""" + content + """
  </body>
 </html>
 """


def get_content(thefile):
    parsed = parseEntries(thepath=thefile, notebookpath=SERVE_PATH, untaggedtag=None)
    entries_html = []
    all_tags = set()

    # prefix (rendered markdown)
    prefix_md = "\n".join(parsed.get("prefix", []))
    prefix_html = md.render(prefix_md) if prefix_md.strip() else ""
    safe_file_location = html.escape(thefile.relative_to(SERVE_PATH).as_posix())

    ref_files = {}
    for entry in parsed["entries"]:
        if len(entry["content"]) == 2 and entry["content"][1].startswith("[" + REFERENCE + "]("):
            entry_match = relativeImageOrLinkRegex.match(entry["content"][1])
            if entry_match is not None:
                entry_split = entry_match.group(3).split('#')
                entry_ref_path = entry_split[0]
                if entry_ref_path.startswith('/'):
                    entry_ref_path = SERVE_PATH / entry_ref_path[1:]
                else:
                    entry_ref_path = SERVE_PATH / entry_ref_path
                #entry_ref_anchor = entry_split[1]
                if entry_ref_path not in ref_files:
                    ref_files[entry_ref_path] = []
                ref_files[entry_ref_path].append(entry)

    for origin_file, entries_list in ref_files.items():
        if origin_file.exists():
            parsed_refs = parseEntries(thepath=origin_file, notebookpath=SERVE_PATH, originPath=origin_file.parent, untaggedtag=None)
            for entry in entries_list:
                for parsed_ref_entry in parsed_refs["entries"]:
                    if parsed_ref_entry["date"] == entry["date"]:
                        entry["content"] = parsed_ref_entry["content"]
                        entry["location"] = parsed_ref_entry.get("location")
                        entry["tags"].extend(parsed_ref_entry["tags"])
                        break

    for entry in parsed["entries"]:
        tags = entry["tags"]
        if len(tags) == 0:
            tags = [UNTAGGED_TAG]

        for t in tags:
            if t != thefile.stem:
                all_tags.add(t)

        mdsrc = "\n".join(entry["content"])
        rendered = md.render(mdsrc)

        safe_tags_attr = html.escape(" ".join(tags))
        safe_id = html.escape(str(entry["date"].strftime("%Y%m%d %H:%M:%S")))
        safe_location = html.escape(entry.get("location", ""))

        if tags:
            badges = " ".join(f'<span class=\"tag-badge\">{html.escape(t)}</span>' for t in tags)
            tags_html = f'<div class=\"entry-tags\">{badges}</div>'
        else:
            tags_html = ''

        # include data-location so client can request the server to open the file in VSCode
        wrapper = (
            f'<div class=\"entry\" data-tags=\"{safe_tags_attr}\" data-id=\"{safe_id}\" data-location=\"{safe_location}\">\n'
            f'{tags_html}\n'
            f'<div class=\"entry-body\">{rendered}</div>\n'
            f'</div>'
        )
        entries_html.append(wrapper)

    # build tag controls (top-right)
    tags_sorted = sorted(all_tags, key=lambda s: s.lower())
    tag_controls = []
    for t in tags_sorted:
        safe_t = html.escape(t)
        # include a span.tag-count so client-side JS can show counts.
        tag_controls.append(
            f'<label><input type="checkbox" class="tag-checkbox" value="{safe_t}"> {safe_t} '
            f'<span class="tag-count" aria-hidden="true"></span></label><br>'
        )

    # form submits selected tags to /_update so the server can redirect back to the current page preserving selection
    update_controls = """
        <form id="update-form" method="POST" action="/_update/""" + safe_file_location + """" style="display:inline;" onsubmit="if(!confirm('Run update? This will recompile notes.')) return false; 
        var vals=Array.from(document.querySelectorAll('.tag-checkbox:checked')).map(cb=>encodeURIComponent(cb.value)).join(','); 
        document.getElementById('update-tags').value = vals;
        return true;">
        <input type="hidden" name="tags" id="update-tags" value="">
        <input type="hidden" name="return_to" id="update-return" value="">
        <button type="submit" id="update-btn">Update</button>
        </form>
    """

    tag_controls_html = '<div id="tag-controls" class="tag-controls"><div style="text-align:right">' + update_controls + '</div>\n\nTags:<br>' + " ".join(tag_controls) + '</div>'

    body = "<div id=\"prefix_html\" location=\"" + safe_file_location + "\">" + prefix_html + "</div>\n\n" + tag_controls_html + "\n\n<div id=\"entries\">" + ("\n".join(entries_html)) + "\n</div>\n"
    return body

@app.route('/<path:mypath>' + MARKDOWN_SUFFIX)
def serve_markdown(mypath):
    thefile = SERVE_PATH / (mypath + MARKDOWN_SUFFIX)
    content_html = get_content(thefile)
    return htmlresponse(title=mypath, content=content_html)

@app.route('/', defaults={'mypath': ''})
@app.route('/<path:mypath>')
def serve_others(mypath):
    p = SERVE_PATH / mypath
    if not p.is_relative_to(SERVE_PATH):
        return "access denied."

    if p.is_dir():
        folders = []
        files = []
        for child in p.iterdir():
            if HIDE_DOTFILES and child.name.startswith("."):
                continue
            if child.is_dir():
                folders.append(child.name)
            else:
                files.append(child.name)

        folders.sort(key=str.lower)
        files.sort(key=str.lower)
        entries = []
        if SERVE_PATH != p:
            entries.append(" <li>📁 <a href=\"../\">../</a></li>")

        for the_folder in folders:
            entries.append(" <li>📁 <a href=\"./" + html.escape(the_folder) + "/\">" + html.escape(the_folder) + "/</a></li>")
        for the_file in files:
            entries.append(" <li>📄 <a href=\"./" + html.escape(the_file) + "\">" + html.escape(the_file) + "</a></li>")

        content = '<ul>\n' + ("\n".join(entries)) + "\n</ul>\n"
        return htmlresponse(title=mypath, content=content)
    else:
        return send_from_directory(str(SERVE_PATH), mypath)

@app.route('/_update/<string:file_location>', methods=['POST'])
def _update(file_location):
    # read tags (comma-separated, url-encoded) from the submitted form
    tags = request.form.get('tags', '') or ''
    # read return path (set by client JS) and validate it's an internal path
    return_to = file_location or '/'
    if not return_to.startswith("/"):
        return_to = "/" + return_to
    if not isinstance(return_to, str):
        return_to = '/'

    compile_notes.main(notebookpath=SERVE_PATH, referenceJournalEntries=True)

    # redirect back to root and preserve selected tags in the fragment
    # include tags as fragment on the original page
    location = return_to + (f'#tags={tags}' if tags else '')
    return redirect(location)

@app.route('/_open', methods=['POST'])
def _open():
    """
    Accepts JSON { "location": "<path-or-relative-path>" } and opens the file on the server
    with the installed VSCode ('code'/'code-insiders'/'code-oss'). Only allows paths inside SERVE_PATH.
    """
    data = request.get_json(silent=True) or {}
    loc = data.get('location', '') if isinstance(data, dict) else ''
    if not isinstance(loc, str) or not loc:
        return ('bad request', 400)

    lloc = loc.split('#L', 1)

    if lloc[0].startswith('/'):
        lloc[0] = lloc[0][1:]
    p = Path(lloc[0])
    p = (SERVE_PATH / p).resolve()

    if not p.is_relative_to(SERVE_PATH):
        return ('forbidden', 403)
    if not p.exists():
        return ('not found', 404)

    code_exec = shutil.which('code')
    if not code_exec:
        return ('code executable not found on server', 500)

    try:
        # open in background; --goto could be used if location includes line/col info
        if len(lloc) == 1:
            subprocess.Popen([code_exec, str(p)])
        else:
            subprocess.Popen([code_exec, "--goto", str(p) + ":" + lloc[1]])
    except Exception:
        return ('failed to open', 500)

    return ('', 204)

if __name__ == '__main__':
    app.run(debug=False, host="127.0.0.1", port=5000)

