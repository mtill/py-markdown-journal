import os
import sys
from flask import Flask, render_template_string, request, redirect
from datetime import datetime, timedelta
from markdown_it import MarkdownIt
import re
from noteslib import parseEntries, writeFile
from pathlib import Path
import uuid
import mimetypes
from werkzeug.utils import secure_filename
from flask import send_from_directory, jsonify

app = Flask(__name__)
md = MarkdownIt()
NOTEBOOK_NAME = "notes"
ENTRIES_PER_PAGE = 25

# add media folder (inside notebook path)
NOTEBOOK_PATH = Path(os.environ.get('NOTES_PATH', '.')).resolve()
MEDIA_FOLDER = NOTEBOOK_PATH / "media"
JOURNAL_PATH = NOTEBOOK_PATH / "journal"

JOURNAL_FILE_REGEX = re.compile(r'(YYYY)-Q([1-4])\.md$')


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
    fmts = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")
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


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ NOTEBOOK_NAME }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .entry {
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            list-style-type: none;
            position: relative;
        }
        
        /* smaller / compact filter box */
        #tag-selector {
            position: fixed;
            top: 12px;
            right: 12px;
            background: white;
            padding: 8px 10px;
            border-radius: 6px;
            box-shadow: 0 1px 6px rgba(0,0,0,0.08);
            width: 220px;            /* compact fixed width */
            max-width: 36vw;
            font-size: 13px;         /* smaller text */
            line-height: 1.25;
            z-index: 1000;
        }
        /* New Entry button inside tag-selector (compact) */
        #tag-selector .new-entry-button {
            display: inline-block;
            float: right;
            margin-left: 8px;
            padding: 4px 8px;
            font-size: 12px;
            border-radius: 6px;
            border: 1px solid #ddd;
            background: #2c3e50;
            color: #fff;
            cursor: pointer;
        }
        #tag-selector h3 { margin: 0 0 6px 0; font-size: 1em; display: block; }
        #tag-selector label { font-size: 13px; margin: 4px 0; }
        #tag-selector input[type="search"],
        .date-inputs input[type="date"] {
            padding: 6px;
            font-size: 13px;
        }
        .tag-list { max-height: 180px; overflow:auto; font-size: 13px; margin-top:6px; }
        @media (max-width: 700px) {
            #tag-selector { width: calc(100% - 32px); top: 8px; right: 8px; padding: 8px; }
        }

        /* Hide new-entry by default; reveal when .visible is applied */
        .new-entry { display: none; background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .new-entry.visible { display: block; }

        .pagination {
            display: flex;
            justify-content: center;
            margin: 20px 0;
            gap: 10px;
        }
        
        .pagination a {
            padding: 8px 16px;
            background: #2c3e50;
            color: white;
            text-decoration: none;
            border-radius: 4px;
        }
        
        .pagination a:hover {
            background: #34495e;
        }
        
        .pagination .current {
            padding: 8px 16px;
            background: #95a5a6;
            color: white;
            border-radius: 4px;
        }
        
        .pagination .disabled {
            padding: 8px 16px;
            background: #95a5a6;
            color: white;
            border-radius: 4px;
            opacity: 0.5;
            pointer-events: none;
        }
        
        .entry-date {
            position: absolute;
            top: 20px;
            right: 20px;
            color: #95a5a6;
            font-size: 0.85em;
            font-family: monospace;
            background: #f8f9fa;
            padding: 4px 8px;
            border-radius: 4px;
        }
        
        .entry h2 {
            margin-right: 160px;
            margin-top: 0;
        }

        .date-range {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 12px;
        }

        .date-inputs {
            display: flex;
            gap: 8px;
        }

        .date-inputs input[type="date"] {
            padding: 6px 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
        }

        .range-labels {
            display: flex;
            justify-content: space-between;
            font-size: 0.85em;
            color: #666;
            margin-top: 6px;
        }

        .tag-list {
            max-height: 300px;
            overflow: auto;
            margin-top: 8px;
        }

        /* Add styles for new entry form inputs */
        .new-entry input[type="text"],
        .new-entry textarea {
            width: 100%;
            padding: 8px;
            margin-bottom: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        
        .new-entry textarea {
            min-height: 100px;
            resize: vertical;
        }
        
        .new-entry button.submit {
            background: #2c3e50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
        }
        .new-entry button.cancel {
            background: transparent;
            border: 1px solid #ddd;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            margin-left: 8px;
        }

        /* Edit functionality styles */
        .edit-btn {
            background: var(--accent, #2c3e50);
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            transition: background-color 0.2s;
        }

        .edit-btn:hover {
            background: #34495e;
        }

        .edit-form {
            margin-top: 16px;
        }

        .edit-form input[type="text"],
        .edit-form textarea {
            width: 100%;
            padding: 10px;
            margin-bottom: 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 0.95em;
            transition: border-color 0.2s;
        }

        .edit-form input[type="text"]:focus,
        .edit-form textarea:focus {
            border-color: #2c3e50;
            outline: none;
            box-shadow: 0 0 0 2px rgba(44,62,80,0.1);
        }

        .edit-form textarea {
            min-height: 120px;
            resize: vertical;
            font-family: inherit;
            line-height: 1.5;
        }

        .edit-actions {
            display: flex;
            gap: 8px;
        }

        .edit-actions button {
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            border: none;
            font-size: 0.9em;
            transition: all 0.2s;
        }

        .edit-actions button[type="submit"] {
            background: var(--accent, #2c3e50);
            color: white;
            flex: 1;
        }

        .edit-actions button[type="submit"]:hover {
            background: #34495e;
        }

        .edit-actions button[type="button"] {
            background: #e5e7eb;
            color: #374151;
        }

        .edit-actions button[type="button"]:hover {
            background: #d1d5db;
        }

        /* Animation for edit form transition */
        .edit-form, .entry-content {
            transition: opacity 0.2s;
        }

        /* tag pill style */
        .tag-pill {
            display: inline-block;
            margin: 0 6px 6px 0;
            padding: 4px 8px;
            background: #eef2f7;
            color: #23303b;
            border-radius: 999px;
            font-size: 0.85em;
            border: 1px solid #dbe6ef;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .tag-pill:hover {
            background: #e2e8f0;
            border-color: #cbd5e1;
        }
        /* visually mark staged tag removals */
        .tag-pill.pending { opacity: 0.5; text-decoration: line-through; filter: grayscale(40%); }
        
        @media (max-width: 700px) {
            #tag-selector {
                position: static;
                margin-bottom: 16px;
                max-width: none;
                width: calc(100% - 40px);
            }
            .entry h2 { margin-right: 0; }
            .entry-date { position: static; display: inline-block; margin-bottom: 8px; }
        }
    </style>
</head>
<body>
    <div id="tag-selector">
        <h3>Filter
            <button type="button" id="toggleNewEntry" class="new-entry-button" aria-expanded="false">New Entry</button>
        </h3>
        <form id="tagForm" method="GET" action="/">

            <div class="date-range">
                <label>From</label>
                <div class="date-inputs">
                    <input type="date" name="start" id="start_date" value="{{ start }}" onchange="this.form.submit()">
                </div>
            </div>

            <!-- search input -->
            <div style="margin-bottom:10px;">
                <label>Search</label>
                <input type="search" name="q" id="q" placeholder="Search (regular expression)" value="{{ q | e }}" style="width:100%; padding:8px; border:1px solid #ddd; border-radius:4px;" onchange="this.form.submit()">
                {% if regex_error %}
                <div style="color:#b00020; font-size:0.9em; margin-top:6px;">Invalid regular expression</div>
                {% endif %}
            </div>

            
            <strong>Tags</strong>
            <div class="tag-list">
            {% for tag in all_tags %}
                <label class="tag-checkbox">
                    <input type="checkbox" name="tags" value="{{ tag }}"
                           {% if tag in selected_tags %}checked{% endif %}
                           onchange="submitFormPreservePage()">
                    {{ tag }}
                </label>
            {% endfor %}
            </div>
        </form>
    </div>

    <h1>{{ NOTEBOOK_NAME }}</h1>
    
    <!-- New Entry: hidden by default, revealed via button in tag-selector -->
    <div class="new-entry" id="newEntryPanel" aria-hidden="true">
        <h3>New Entry</h3>
        <form method="POST" action="/new" id="newEntryForm">
            <input type="text" name="title" placeholder="Title" required>
            <textarea name="content" placeholder="Content (Markdown supported)" required>{% if selected_tags %}Tags: {{ ", ".join(selected_tags) }}

{% endif %}</textarea>
            <div style="margin-top:6px">
                <button type="submit" class="submit">Add Entry</button>
                <button type="button" class="cancel" id="cancelNewEntry">Cancel</button>
            </div>
        </form>
    </div>

    <!-- Replace the existing entry list in HTML_TEMPLATE -->
    <ul>
        {% for entry in entries %}
        <li class="entry" data-entry-id="{{ entry.date.strftime('%Y-%m-%d %H:%M:%S') }}">
             <div class="entry-date">{{ entry.date.strftime('%Y-%m-%d') }}</div>
             <div class="entry-content" id="content-{{ entry.date.strftime('%Y-%m-%d %H:%M:%S') }}">
                 <h2>{{ entry.title }}</h2>
                 <p>{{ entry.content | safe }}</p>
                 <!-- Store original markdown in data attribute -->
                 <textarea class="entry-markdown" style="display:none;">{{ entry.markdown }}</textarea>
                 {% if not (entry.tags|length == 1 and entry.tags|first == "untagged") %}
                   <p>Tags:
                   {% for tag in entry.tags %}
                     <button type="button" 
                             class="tag-pill" 
                             onclick="removeTagContent('{{ entry.date.strftime('%Y-%m-%d %H:%M:%S') }}', '{{ tag }}')"
                             title="Remove tag '{{ tag }}' from entry">
                         {{ tag }}
                     </button>
                     {% endfor %}
                   </p>
                 {% endif %}
                 <button onclick="showEdit('{{ entry.date.strftime('%Y-%m-%d %H:%M:%S') }}')" class="edit-btn">Edit</button>
             </div>
            <form method="POST" action="/edit/{{ entry.date.strftime('%Y-%m-%d %H:%M:%S') }}" class="edit-form" id="edit-{{ entry.date.strftime('%Y-%m-%d %H:%M:%S') }}" style="display:none">
                <!-- preserve client-side filters when submitting the edit form -->
                <input type="hidden" name="start" value="{{ start }}">
                <input type="hidden" name="q" value="{{ q }}">
                <input type="hidden" name="page" value="{{ page }}">
                {% for tag in selected_tags %}
                  <input type="hidden" name="tags" value="{{ tag }}">
                {% endfor %}

                <textarea name="content" required>{{ entry.markdown }}</textarea>
                <div class="edit-actions">
                    <button type="submit">Save</button>
                    <button type="button" onclick="hideEdit('{{ entry.date.strftime('%Y-%m-%d %H:%M:%S') }}')">Cancel</button>
                </div>
            </form>
        </li>
        {% endfor %}
    </ul>

    <div class="pagination">
        {% if has_prev %}
            <a href="?page={{ page - 1 }}{% for tag in selected_tags %}&tags={{ tag }}{% endfor %}{% if start %}&start={{ start }}{% endif %}&q={{ q | urlencode }}">Previous</a>
        {% else %}
            <span class="disabled">Previous</span>
        {% endif %}
        
        <span class="current">Page {{ page }} of {{ total_pages }}</span>
        
        {% if has_next %}
            <a href="?page={{ page + 1 }}{% for tag in selected_tags %}&tags={{ tag }}{% endfor %}{% if start %}&start={{ start }}{% endif %}&q={{ q | urlencode }}">Next</a>
        {% else %}
            <span class="disabled">Next</span>
        {% endif %}
    </div>

<script>
(function(){
    // simple helper used by tag checkbox onchange to submit the form
    window.submitFormPreservePage = function() {
        document.getElementById('tagForm').submit();
    };

    // Show the edit form for an entry
    window.showEdit = function(entryId) {
        document.getElementById('content-' + entryId).style.display = 'none';
        document.getElementById('edit-' + entryId).style.display = 'block';
        // focus first textarea in the edit form for convenience
        const ta = document.querySelector('#edit-' + entryId + ' textarea');
        if (ta) ta.focus();
    };

    // Hide the edit form for an entry
    window.hideEdit = function(entryId) {
        document.getElementById('content-' + entryId).style.display = 'block';
        document.getElementById('edit-' + entryId).style.display = 'none';
    };

    // New Entry toggling
    function toggleNewEntry() {
        const panel = document.getElementById('newEntryPanel');
        const btn = document.getElementById('toggleNewEntry');
        if (!panel || !btn) return;
        const isVisible = panel.classList.toggle('visible');
        if (isVisible === true || panel.classList.contains('visible')) {
            panel.classList.add('visible');
            panel.setAttribute('aria-hidden', 'false');
            btn.textContent = 'Close';
            btn.setAttribute('aria-expanded', 'true');
            // focus the title input
            const title = panel.querySelector('input[name="title"]');
            if (title) title.focus();
            panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
            panel.classList.remove('visible');
            panel.setAttribute('aria-hidden', 'true');
            btn.textContent = 'New Entry';
            btn.setAttribute('aria-expanded', 'false');
        }
    }

    document.addEventListener('DOMContentLoaded', function(){
        // existing initializations...
        const toggle = document.getElementById('toggleNewEntry');
        if (toggle) toggle.addEventListener('click', function(){ toggleNewEntry(); });

        const cancelBtn = document.getElementById('cancelNewEntry');
        if (cancelBtn) cancelBtn.addEventListener('click', function(){ toggleNewEntry(); });

        // double-click content to enter edit mode
        document.querySelectorAll('.entry-content').forEach(el => {
            el.addEventListener('dblclick', function(e){
                // ignore dblclicks originating from interactive elements
                if (e.target.closest('button, a, input, textarea, label, .tag-pill')) return;
                const entry = el.closest('.entry');
                if (!entry) return;
                const id = entry.getAttribute('data-entry-id');
                if (id) showEdit(id);
            });
        });
        // keep previous paste-handler and other setup
        // ...existing JS code continues...
    });

    // ...existing JS code (paste handlers etc.) ...
})();
</script>
<script>
// Expose current filter values for form submissions
window.currentFilters = {
    tags: [{% for t in selected_tags %}'{{ t }}'{% if not loop.last %}, {% endif %}{% endfor %}],
    start: '{{ start }}',
    q: '{{ q | e }}',
    page: '{{ page }}'
};
 
// Queue-based tag removal: user stages removals and clicks Apply to perform them.
const pendingRemovals = []; // { entryId, tag, markdown }

function findTagButton(container, tag){
    const btns = container.querySelectorAll('.tag-pill');
    for (const b of btns){
        if (b.textContent.trim() === tag) return b;
    }
    return null;
}

function updatePendingPanel(){
    let panel = document.getElementById('pending-panel');
    if (!panel){
        panel = document.createElement('div');
        panel.id = 'pending-panel';
        Object.assign(panel.style, {
            position: 'fixed',
            left: '20px',
            bottom: '20px',
            background: 'white',
            padding: '10px',
            borderRadius: '8px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
            zIndex: 2000,
            display: 'flex',
            gap: '8px',
            alignItems: 'center'
        });
        document.body.appendChild(panel);
    }
    panel.innerHTML = '';

    const count = pendingRemovals.length;
    const info = document.createElement('span');
    info.textContent = count ? `${count} pending change${count>1?'s':''}` : 'No pending changes';
    panel.appendChild(info);

    const applyBtn = document.createElement('button');
    applyBtn.textContent = 'Apply';
    applyBtn.disabled = count === 0;
    applyBtn.style.padding = '6px 10px';
    applyBtn.style.borderRadius = '6px';
    applyBtn.style.border = 'none';
    applyBtn.style.background = count ? '#1572e8' : '#ccc';
    applyBtn.style.color = '#fff';
    applyBtn.onclick = async function(){
        applyBtn.disabled = true;
        applyBtn.textContent = 'Applying...';
        try {
            // perform removals sequentially
            for (const item of [...pendingRemovals]){
                const fd = new FormData();
                fd.append('content', item.markdown);
                fd.append('remove_tag', item.tag);
                // preserve filters
                if (window.currentFilters){
                    if (window.currentFilters.start) fd.append('start', window.currentFilters.start);
                    if (window.currentFilters.q) fd.append('q', window.currentFilters.q);
                    if (window.currentFilters.page) fd.append('page', window.currentFilters.page);
                    (window.currentFilters.tags || []).forEach(t => fd.append('tags', t));
                }
                const url = '/edit/' + encodeURIComponent(item.entryId);
                const resp = await fetch(url, { method: 'POST', body: fd });
                if (!resp.ok) {
                    console.error('failed to apply removal', item, resp.status);
                    alert('Failed to apply some changes. See console.');
                    applyBtn.disabled = false;
                    applyBtn.textContent = 'Apply';
                    return;
                }
                // on success, remove from pending and unmark button
                const idx = pendingRemovals.findIndex(p => p.entryId===item.entryId && p.tag===item.tag);
                if (idx !== -1) pendingRemovals.splice(idx, 1);
            }
            // reload to reflect changes (preserve filters via currentFilters)
            const params = new URLSearchParams();
            if (window.currentFilters){
                if (window.currentFilters.start) params.set('start', window.currentFilters.start);
                if (window.currentFilters.q) params.set('q', window.currentFilters.q);
                if (window.currentFilters.page) params.set('page', window.currentFilters.page);
                (window.currentFilters.tags || []).forEach(t => params.append('tags', t));
            }
            window.location = window.location.pathname + (params.toString() ? '?'+params.toString() : '');
        } catch (err){
            console.error(err);
            alert('Error applying changes. See console.');
            applyBtn.disabled = false;
            applyBtn.textContent = 'Apply';
        }
    };
    panel.appendChild(applyBtn);

    const resetBtn = document.createElement('button');
    resetBtn.textContent = 'Cancel all';
    resetBtn.style.padding = '6px 10px';
    resetBtn.style.borderRadius = '6px';
    resetBtn.style.border = '1px solid #ddd';
    resetBtn.onclick = function(){
        // unmark all buttons
        pendingRemovals.forEach(it => {
            const container = document.getElementById('content-' + it.entryId);
            if (!container) return;
            const btn = findTagButton(container, it.tag);
            if (btn) btn.classList.remove('pending');
        });
        pendingRemovals.length = 0;
        updatePendingPanel();
    };
    panel.appendChild(resetBtn);
}

// toggle staging a tag removal (called by inline onclick)
function removeTagContent(entryId, tag){
    const container = document.getElementById('content-' + entryId);
    if (!container) return;
    const ta = container.querySelector('.entry-markdown');
    if (!ta) return;

    // check if already pending
    const exists = pendingRemovals.find(p => p.entryId===entryId && p.tag===tag);
    const btn = findTagButton(container, tag);
    if (exists){
        // unstage
        const idx = pendingRemovals.indexOf(exists);
        if (idx !== -1) pendingRemovals.splice(idx, 1);
        if (btn) btn.classList.remove('pending');
    } else {
        // stage removal
        pendingRemovals.push({ entryId: entryId, tag: tag, markdown: ta.value });
        if (btn) btn.classList.add('pending');
    }
    updatePendingPanel();
}

// initialize pending panel on load
document.addEventListener('DOMContentLoaded', function(){ updatePendingPanel(); });
</script>
</body>
</html>
"""

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
def index():
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    
    # Get selected tags from query parameters
    selected_tags = request.args.getlist('tags')
    
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

    # Then apply tag filtering (entry must have all selected tags)
    if selected_tags:
        filtered_entries = [
            entry for entry in date_filtered 
            if all(tag in entry.get('tags', []) for tag in selected_tags)
        ]
    else:
        filtered_entries = date_filtered

    # regex search param
    q = request.args.get('q', '').strip()

    regex = None
    regex_error = False
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

    # compute available_tags from the currently filtered entries (keep selected tags visible)
    available_tags = sorted(
        set(tag for entry in filtered_entries for tag in entry.get('tags', [])) | set(selected_tags)
    )

    # Implement pagination
    start = (page - 1) * ENTRIES_PER_PAGE
    end = start + ENTRIES_PER_PAGE
    paginated_entries = filtered_entries[start:end]
    total_pages = (len(filtered_entries) + ENTRIES_PER_PAGE - 1) // ENTRIES_PER_PAGE if filtered_entries else 1

    return render_template_string(
        HTML_TEMPLATE,
        NOTEBOOK_NAME=NOTEBOOK_NAME,
        entries=paginated_entries,
        all_tags=available_tags,
        selected_tags=selected_tags,
        page=page,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        start=start_date.strftime('%Y-%m-%d'),
        q=q,
        regex_error=regex_error
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


@app.route('/<path:filename>')
def media_file(filename):
    return send_from_directory(NOTEBOOK_PATH, filename)


if __name__ == '__main__':
    NOTEBOOK_NAME = sys.argv[1]
    app.run(debug=True, host='127.0.0.1', port=5000)

