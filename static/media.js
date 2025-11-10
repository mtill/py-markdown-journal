// images.js - handles upload from disk and clipboard and copying links
async function uploadBlob(blob, filename) {
    const status = document.getElementById('status');
    status.textContent = 'Uploading...';

    try {
        const fd = new FormData();
        fd.append('file', blob, filename || 'clipboard-image');
        const resp = await fetch('/_upload_media', { method: 'POST', body: fd });
        const data = await resp.json();
        if (!resp.ok) {
            status.textContent = 'Upload failed: ' + (data.error || resp.status);
            return null;
        }

        // normalize to an array of uploaded items
        let uploads = [];
        let the_urls = [];
        if (Array.isArray(data.uploads)) uploads = data.uploads;
        else if (data.url && data.name) uploads = [{ url: data.url, name: data.name }];

        const ul = document.getElementById('recentList');
        for (const uploaded_file of uploads) {
            status.textContent = 'Uploaded: ' + uploaded_file.name;
            // prepend to recent list
            const li = document.createElement('li');
            // build inner: show image preview for images, pdf icon for pdfs, otherwise generic link
            const isImage = /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(uploaded_file.name);
            let preview = '<span class="thumb-file">📄</span>';
            if (isImage) {
                preview = `<img class="thumb" src="${uploaded_file.url}" loading="lazy" alt="${uploaded_file.name}">`;
            }
            let liinner = `<a class="thumb-link" href="${uploaded_file.url}" target="_blank">${preview}</a><span class="copy-name" data-url="${uploaded_file.url}" onclick="copyURLToClipboard(this)" title="copy link">🔗 ${uploaded_file.name}</span> <span onclick="deleteFile('${uploaded_file.url}')" class="deletelink" title="Delete file">🗑️</span> &nbsp;— <small>just now</small>`;
            li.innerHTML = liinner;
            // store filename for later removal
            li.setAttribute('data-filename', uploaded_file.name);
            ul.insertBefore(li, ul.firstChild);
            the_urls.push(uploaded_file.url);
        }
        let clip_content = [];
        for (const the_url of the_urls) {
            clip_content.push("![](" + the_url + ")");
        }
        setClipboard(clip_content.join("\n"));
        return data;
    } catch (err) {
        console.error(err);
        status.textContent = 'Upload error';
        return null;
    } finally {
        setTimeout(() => { const s = document.getElementById('status'); if (s) s.textContent = ''; }, 3000);
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


function copyURLToClipboard(entry) {
    const url = entry.getAttribute('data-url') || entry.dataset.url;
    if (!url) return;

    const originalText = entry.textContent;
    setClipboard("![](" + url + ")");
    entry.textContent = 'copied';
    setTimeout(() => { entry.textContent = originalText; }, 1500);
}


function deleteFile(fileUrl) {
    if (!confirm('Are you sure you want to delete this file?\n' + fileUrl)) {
        return;
    }

    const deleteForm = document.getElementById('deleteForm');
    const thepathInput = document.getElementById('thepath');
    thepathInput.value = fileUrl;
    deleteForm.submit();
}


function initMediaPage() {
    const fileInput = document.getElementById('fileInput');

    if (fileInput) {
        fileInput.addEventListener('change', async function(e){
            const f = e.target.files && e.target.files[0];
            if (!f) return;
            await uploadBlob(f, f.name);
            fileInput.value = '';
        });
    }

    // also allow pasting directly into the page (Ctrl+V)
    document.addEventListener('paste', async function(ev){
        if (!ev.clipboardData) return;
        const items = ev.clipboardData.items;
        for (let i=0;i<items.length;i++){
            const it = items[i];
            if (it.type && it.type.startsWith('image/')){
                const blob = it.getAsFile();
                await uploadBlob(blob, 'pasted.' + (it.type.split('/')[1] || 'png'));
                ev.preventDefault();
                return;
            }
        }
    });
}


