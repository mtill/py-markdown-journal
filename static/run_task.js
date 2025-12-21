async function run_task(task_id, param) {
    if (confirm('run task: ' + task_id + '?') == true) {
        try {
            const fd = new FormData();
            if (param !== null) {
                fd.append('param', param);
            }
            const resp = await fetch('/_run_task/' + task_id, { method: 'POST', body: fd });
            if (!resp.ok) {
                const txt = await resp.text();
                alert('Failed to sync: ' + resp.status + ' ' + txt);
            } else {
                const response_json = await resp.json();
                if ('detail' in response_json) {
                    const newWindow = window.open("", "_blank", "width=600,height=400");
                    if (newWindow) {
                        const doc = newWindow.document;
                        doc.title = 'task ' + task_id + ' executed.';
                        const content = doc.createElement('pre');
                        content.textContent = doc.title + "\n---------------------------------\n\n" + response_json['detail'];
                        doc.body.appendChild(content);
                    }

                } else {
                    alert('task ' + task_id + ' executed.');
                }
            }
        } catch (err) {
            console.error(err);
            alert('Error when running the sync command on server. See console.');
        } finally {
        }
    }
}

