// highlight entries that have the 'highlighted' tag
function applyHighlights(){
    document.querySelectorAll('.entry').forEach(el => {
        const tags = (el.dataset.tags || '').split(/\s+/).filter(Boolean);
        if (tags.includes('highlighted')) el.classList.add('highlighted');
        else el.classList.remove('highlighted');

        if (tags.includes('inbox')) el.classList.add('in_inbox');
        else el.classList.remove('in_inbox');
    });
}

// simple helper used by tag checkbox onchange to submit the form
function submitFormPreservePage(entryId) {
    const theform = document.getElementById('tagForm');
    const theurl = new URL(theform.action);
    if (entryId === null) {
      theurl.hash = "journal_entries";
    } else {
      theurl.hash = entryId;
    }
    theform.action = theurl.toString();
    theform.submit();
}

function toggleControls() {
    const controls = document.getElementById('controls');
    const theToggle = document.getElementById('controlstoggle');
    if (controls.style.display === 'none') {
        controls.style.display = 'block';
        theToggle.innerText = 'hide';
    } else {
        controls.style.display = 'none';
        theToggle.innerText = 'show';
    }
}

async function setClipboard(text) {
  const type = "text/plain";
  const clipboardItemData = {
    [type]: text,
  };
  const clipboardItem = new ClipboardItem(clipboardItemData);
  await navigator.clipboard.write([clipboardItem]);
}

// credits: https://gist.github.com/ethanny2/44d5ad69970596e96e0b48139b89154b
function detectDoubleTap(doubleTapMs) {
    let timeout, lastTap = 0

    return function detectDoubleTap(event) {
        const currentTime = Date.now()
        const tapLength = currentTime - lastTap
        if (tapLength > 0 && tapLength < doubleTapMs) {
            event.preventDefault()
            const doubleTap = new CustomEvent("doubletap", {
                bubbles: true,
                detail: event
            })
            event.target.dispatchEvent(doubleTap)
        } else {
            timeout = setTimeout(() => clearTimeout(timeout), doubleTapMs)
        }
        lastTap = currentTime
    }
}


async function removeTag(btn, rel_path, entryId, tag){
    if (tag === "{{ NO_ADDITIONAL_TAGS}}") {
        return;
    }

    if (!confirm('Are you sure you want to remove tag "' + tag + '"?\n')) {
        return;
    }
    
    try {
        const fd = new FormData();
        fd.append('rel_path', rel_path);
        fd.append('entryId', entryId);
        fd.append('remove_tag', tag);
        const resp = await fetch('/_remove_tag', { method: 'POST', body: fd });
        if (!resp.ok) {
            const txt = await resp.text();
            alert('Failed to remove tag: ' + resp.status + ' ' + txt);
        } else {
            //btn.parentElement.removeChild(btn.parentElement);
            let count_display = document.getElementById("tag-count-" + tag);
            if (count_display && !isNaN(Number(count_display.textContent))) {
                count_display.textContent = parseInt(count_display.textContent) - 1;
            }
        }
        btn.parentElement.classList.add('removed');
        btn.parentElement.removeChild(btn);
    } catch (err) {
        console.error(err);
        alert('Error removing tag. See console.');
    }
}

// Opens entry in editor on the server via AJAX POST to /_edit
async function openInEditor(thetype, entryId){
    let rel = null;
    let line_no = null;

    if (thetype == "entry") {
        const li = document.querySelector(`.entry[id="${entryId}"]`);
        if (!li) return alert('entry not found');
        rel = li.getAttribute('data-rel-path');
        if (!rel) return alert('no path available for this entry');
        line_no = li.getAttribute('data-line-no');
        if (!line_no) return alert('no line number available for this entry');
    } else {
        rel = entryId;
    }

    try {
        const fd = new FormData();
        fd.append('rel_path', rel);
        if (line_no !== null) {
            fd.append('line_no', line_no);
        }
        const resp = await fetch('/_edit', { method: 'POST', body: fd });
        if (!resp.ok) {
            const txt = await resp.text();
            alert('Failed to open in editor on server: ' + resp.status + ' ' + txt);
        } else {
        }
    } catch (err) {
        console.error(err);
        alert('Error opening in editor on server. See console.');
    } finally {
    }
}


document.addEventListener('DOMContentLoaded', function(){
    // initial highlight pass and start watching for later changes
    applyHighlights();

    // double-click content to enter edit mode
    document.querySelectorAll('.entry').forEach(el => {
        //el.addEventListener('dblclick', function(e){
        //    openInEditor(thetype="entry", entryId=el.getAttribute('id'))
        //});
        el.title="click to copy reference to this entry; double-click to open entry in editor";
        el.addEventListener('click', (event) => {
            setClipboard('[journal entry ' + el.getAttribute('data-datestr') + '](' + el.getAttribute('data-location') + ')');
        });
        el.addEventListener('doubletap', (event) => {
            openInEditor(thetype="entry", entryId=el.getAttribute('id'))
        });
    });

    // initialize the new event
    document.addEventListener('pointerup', detectDoubleTap(500));
});

