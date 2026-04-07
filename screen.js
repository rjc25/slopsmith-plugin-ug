// Ultimate Guitar plugin — search and build functions

async function searchUG() {
    const query = document.getElementById('ug-search').value.trim();
    if (!query) return;
    document.getElementById('ug-list').innerHTML = '<p class="text-gray-500 py-4">Searching Ultimate Guitar...</p>';
    try {
        const resp = await fetch(`/api/plugins/ultimate_guitar/search?q=${encodeURIComponent(query)}`);
        const data = await resp.json();
        if (data.error) {
            document.getElementById('ug-list').innerHTML = `<p class="text-red-400 py-4">${data.error}</p>`;
            return;
        }
        const results = data.results || [];
        if (!results.length) {
            document.getElementById('ug-list').innerHTML = '<p class="text-gray-500 py-4">No Guitar Pro tabs found.</p>';
            return;
        }
        document.getElementById('ug-list').innerHTML = results.map(r => `
            <div class="result-item" onclick="buildFromUG('${encodeURIComponent(r.tab_url)}', '${(r.artist_name + ' - ' + r.song_name).replace(/'/g, "\\'")}')">
                <div>
                    <div class="text-sm font-medium text-white">${r.song_name}</div>
                    <div class="text-xs text-gray-500">${r.artist_name}</div>
                </div>
                <div class="text-xs text-gray-600">★ ${r.rating} (${r.votes})</div>
            </div>
        `).join('');
    } catch (e) {
        document.getElementById('ug-list').innerHTML = `<p class="text-red-400 py-4">Search failed: ${e}</p>`;
    }
}

async function buildFromUG(tabUrl, name) {
    if (!confirm(`Download "${name}" and build CDLC with MIDI audio?`)) return;

    const list = document.getElementById('ug-list');
    list.innerHTML = `
        <div class="py-4">
            <p class="text-gray-300 mb-3">Building: ${name}</p>
            <div class="progress-bar"><div class="fill" id="build-bar" style="width:0%"></div></div>
            <p class="text-xs text-gray-500 mt-2" id="build-stage">Starting...</p>
        </div>`;

    const ws = new WebSocket(`ws://${location.host}/ws/plugins/ultimate_guitar/build?tab_url=${encodeURIComponent(decodeURIComponent(tabUrl))}`);
    ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.progress !== undefined) document.getElementById('build-bar').style.width = msg.progress + '%';
        if (msg.stage) document.getElementById('build-stage').textContent = msg.stage;
        if (msg.done) list.innerHTML = `<p class="text-green-400 py-4">Created: ${msg.filename}<br><span class="text-gray-500">${msg.tracks}</span></p>`;
        if (msg.error) list.innerHTML = `<p class="text-red-400 py-4">${msg.error}</p>`;
    };
    ws.onerror = () => { list.innerHTML = `<p class="text-red-400 py-4">Connection lost</p>`; };
}
