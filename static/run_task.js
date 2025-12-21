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
                let msg = 'task ' + task_id + ' executed.';
                const response_json = await resp.json();
                if ('detail' in response_json) {
                    msg = msg + "\n" + response_json['detail'];
                }
                alert(msg);
            }
        } catch (err) {
            console.error(err);
            alert('Error when running the sync command on server. See console.');
        } finally {
        }
    }
}

