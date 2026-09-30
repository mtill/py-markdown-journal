async function run_task(task_id, param) {
    if (confirm('run task: ' + task_id + '?') == true) {
        const newWindow = window.open("", "_blank", "width=600,height=400");
        let output = null;
        if (newWindow) {
            const doc = newWindow.document;
            doc.title = 'task ' + task_id + ' running...';
            const content = doc.createElement('pre');
            content.textContent = doc.title + "\n---------------------------------\n\n";
            doc.body.appendChild(content);
            output = doc.createTextNode('');
            content.appendChild(output);
        }

        try {
            const fd = new FormData();
            if (param !== null) {
                fd.append('param', param);
            }
            const resp = await fetch('/_run_task/' + task_id, { method: 'POST', body: fd });
            if (!resp.ok) {
                const txt = await resp.text();
                if (output) {
                    output.textContent += 'Request failed (' + resp.status + '): ' + txt;
                } else {
                    alert('Failed to run task: ' + resp.status + ' ' + txt);
                }
                return;
            }

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                const { value, done } = await reader.read();
                if (done) {
                    break;
                }
                const text = decoder.decode(value, { stream: true });
                if (output) {
                    output.textContent += text;
                    newWindow.scrollTo(0, newWindow.document.body.scrollHeight);
                }
            }
            const remaining = decoder.decode();
            if (output) {
                output.textContent += remaining + "\n\n---------------------------------\ntask " + task_id + " executed.";
                newWindow.document.title = 'task ' + task_id + ' executed.';
            } else {
                alert('task ' + task_id + ' executed.');
            }
        } catch (err) {
            console.error(err);
            if (output) {
                output.textContent += '\nError when running task: ' + err;
            } else {
                alert('Error when running the task. See console.');
            }
        }
    }
}

