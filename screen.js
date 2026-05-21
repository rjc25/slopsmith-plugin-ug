// Ultimate Guitar plugin — search, configure audio, and build functions

let _ugSelectedTabUrl = null;
let _ugSelectedName = null;
let _ugAudioFile = null;      // File object for real audio (from drag-drop/picker)

// ── Audio drop zone ───────────────────────────────────────────────────
(function() {
    setTimeout(() => {
        const audioDropzone = document.getElementById('ug-audio-dropzone');
        const audioFileInput = document.getElementById('ug-audio-file-input');
        if (!audioDropzone || !audioFileInput) return;

        audioDropzone.addEventListener('click', () => audioFileInput.click());

        audioDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            audioDropzone.classList.add('border-accent/60', 'bg-accent/5');
        });

        audioDropzone.addEventListener('dragleave', () => {
            audioDropzone.classList.remove('border-accent/60', 'bg-accent/5');
        });

        audioDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            audioDropzone.classList.remove('border-accent/60', 'bg-accent/5');
            const file = e.dataTransfer.files[0];
            if (file) ugHandleAudioFile(file);
        });

        audioFileInput.addEventListener('change', () => {
            if (audioFileInput.files[0]) ugHandleAudioFile(audioFileInput.files[0]);
        });
    }, 100);
})();

function ugHandleAudioFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['mp3', 'ogg', 'wav', 'flac'].includes(ext)) {
        alert('Only MP3, OGG, WAV, and FLAC audio files are supported.');
        return;
    }
    _ugAudioFile = file;
    // Clear the local path input since a file was selected
    const pathInput = document.getElementById('ug-audio-path');
    if (pathInput) pathInput.value = '';

    const label = document.getElementById('ug-audio-label');
    if (label) label.textContent = file.name;

    const status = document.getElementById('ug-audio-status');
    if (status) {
        status.classList.remove('hidden');
        status.textContent = `Audio file selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
        status.className = 'mt-2 text-xs text-green-400';
    }
}

function ugToggleAudioMode() {
    const mode = document.querySelector('input[name="ug-audio-mode"]:checked').value;
    const audioSection = document.getElementById('ug-audio-section');
    const stemSection = document.getElementById('ug-stem-section');

    if (mode === 'real') {
        audioSection.classList.remove('hidden');
        stemSection.classList.remove('hidden');
    } else {
        audioSection.classList.add('hidden');
        stemSection.classList.add('hidden');
        document.getElementById('ug-stem-check').checked = false;
        document.getElementById('ug-stem-options').classList.add('hidden');
    }
}

function ugToggleStemOptions() {
    const checked = document.getElementById('ug-stem-check').checked;
    document.getElementById('ug-stem-options').classList.toggle('hidden', !checked);
}

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
            <div class="result-item" onclick="ugSelectTab('${encodeURIComponent(r.tab_url)}', '${(r.artist_name + ' - ' + r.song_name).replace(/'/g, "\\'")}')">
                <div>
                    <div class="text-sm font-medium text-white">${r.song_name}</div>
                    <div class="text-xs text-gray-500">${r.artist_name}</div>
                </div>
                <div class="text-xs text-gray-600">${'★'} ${r.rating} (${r.votes})</div>
            </div>
        `).join('');
    } catch (e) {
        document.getElementById('ug-list').innerHTML = `<p class="text-red-400 py-4">Search failed: ${e}</p>`;
    }
}

function ugSelectTab(encodedUrl, name) {
    _ugSelectedTabUrl = decodeURIComponent(encodedUrl);
    _ugSelectedName = name;

    // Hide search, show configure panel
    document.getElementById('ug-search-section').classList.add('hidden');
    document.getElementById('ug-configure').classList.remove('hidden');
    document.getElementById('ug-selected-name').textContent = name;
}

function ugBackToSearch() {
    _ugSelectedTabUrl = null;
    _ugSelectedName = null;
    _ugAudioFile = null;

    document.getElementById('ug-configure').classList.add('hidden');
    document.getElementById('ug-search-section').classList.remove('hidden');

    // Reset audio controls
    const midiRadio = document.querySelector('input[name="ug-audio-mode"][value="midi"]');
    if (midiRadio) midiRadio.checked = true;
    ugToggleAudioMode();

    const audioLabel = document.getElementById('ug-audio-label');
    if (audioLabel) audioLabel.textContent = 'Drop audio or click to browse';
    const audioPath = document.getElementById('ug-audio-path');
    if (audioPath) audioPath.value = '';
    const audioFileInput = document.getElementById('ug-audio-file-input');
    if (audioFileInput) audioFileInput.value = '';
    const audioStatus = document.getElementById('ug-audio-status');
    if (audioStatus) {
        audioStatus.classList.add('hidden');
        audioStatus.className = 'mt-2 text-xs text-gray-600 hidden';
    }

    // Reset stem options
    const stemCheck = document.getElementById('ug-stem-check');
    if (stemCheck) stemCheck.checked = false;
    const stemOpts = document.getElementById('ug-stem-options');
    if (stemOpts) stemOpts.classList.add('hidden');
    const replicateKey = document.getElementById('ug-replicate-key');
    if (replicateKey) replicateKey.value = '';
}

function ugReadFileAsBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result.split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

async function ugBuild() {
    if (!_ugSelectedTabUrl) return;

    const audioMode = document.querySelector('input[name="ug-audio-mode"]:checked').value;
    const stemCheck = document.getElementById('ug-stem-check');
    const doStems = stemCheck && stemCheck.checked && audioMode === 'real';
    const replicateKey = doStems ? (document.getElementById('ug-replicate-key')?.value.trim() || '') : '';

    if (doStems && !replicateKey) {
        alert('Enter your Replicate API key for stem separation.');
        return;
    }

    // Determine audio params
    let audioServerPath = '';
    let audioLocalPath = '';

    if (audioMode === 'real') {
        if (_ugAudioFile) {
            // Upload audio file to server first, get back a temp path
            const audioB64 = await ugReadFileAsBase64(_ugAudioFile);
            try {
                const uploadResp = await fetch('/api/plugins/ultimate_guitar/upload_audio', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: _ugAudioFile.name, data: audioB64 }),
                });
                const uploadData = await uploadResp.json();
                if (uploadData.error) {
                    alert(uploadData.error);
                    return;
                }
                audioServerPath = uploadData.audio_path;
            } catch (err) {
                alert('Failed to upload audio file: ' + err);
                return;
            }
        } else {
            audioLocalPath = document.getElementById('ug-audio-path')?.value.trim() || '';
        }

        if (!audioServerPath && !audioLocalPath) {
            alert('Select or specify an audio file, or switch to MIDI mode.');
            return;
        }
    }

    // Hide configure, show progress
    document.getElementById('ug-configure').classList.add('hidden');
    document.getElementById('ug-progress').classList.remove('hidden');
    document.getElementById('ug-result').classList.add('hidden');
    document.getElementById('ug-bar').style.width = '0%';
    document.getElementById('ug-stage').textContent = 'Starting...';
    const logEl = document.getElementById('ug-progress-log');
    if (logEl) logEl.innerHTML = '';

    const params = new URLSearchParams({
        tab_url: _ugSelectedTabUrl,
    });
    if (audioServerPath) params.set('audio_path', audioServerPath);
    if (audioLocalPath) params.set('audio_local_path', audioLocalPath);
    if (doStems) params.set('stem_split', '1');
    if (replicateKey) params.set('replicate_key', replicateKey);

    const ws = new WebSocket(`ws://${location.host}/ws/plugins/ultimate_guitar/build?${params}`);
    ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.progress !== undefined)
            document.getElementById('ug-bar').style.width = msg.progress + '%';
        if (msg.stage) {
            document.getElementById('ug-stage').textContent = msg.stage;
            // Add to progress log
            if (logEl) {
                const line = document.createElement('p');
                line.className = 'text-xs text-gray-600';
                line.textContent = msg.stage;
                // Highlight sync offset line
                if (msg.stage.includes('Auto-sync offset')) {
                    line.className = 'text-xs text-accent';
                }
                logEl.appendChild(line);
                logEl.scrollTop = logEl.scrollHeight;
            }
        }
        if (msg.done) {
            document.getElementById('ug-progress').classList.add('hidden');
            document.getElementById('ug-result').classList.remove('hidden');
            let extra = '';
            if (msg.audio_offset) {
                extra += `<p class="text-xs text-gray-500 mt-1">Audio offset: ${msg.audio_offset}</p>`;
            }
            if (msg.stems) {
                extra += `<p class="text-xs text-gray-500 mt-1">${msg.stems}</p>`;
            }
            document.getElementById('ug-result').innerHTML = `
                <div class="bg-green-900/20 border border-green-800/30 rounded-xl p-5 text-center">
                    <p class="text-green-400 font-semibold mb-1">CDLC Created!</p>
                    <p class="text-sm text-gray-400">${msg.filename}</p>
                    <p class="text-xs text-gray-500 mt-1">Tracks: ${msg.tracks}</p>
                    ${extra}
                    <button onclick="ugReset()" class="mt-4 px-4 py-2 bg-dark-600 hover:bg-dark-500 rounded-xl text-sm text-gray-300 transition">Search Again</button>
                </div>`;
        }
        if (msg.error) {
            document.getElementById('ug-progress').classList.add('hidden');
            document.getElementById('ug-result').classList.remove('hidden');
            document.getElementById('ug-result').innerHTML = `
                <div class="bg-red-900/20 border border-red-800/30 rounded-xl p-5 text-center">
                    <p class="text-red-400 font-semibold mb-1">Build Failed</p>
                    <p class="text-sm text-gray-400">${msg.error}</p>
                    <button onclick="ugReset()" class="mt-4 px-4 py-2 bg-dark-600 hover:bg-dark-500 rounded-xl text-sm text-gray-300 transition">Try Again</button>
                </div>`;
        }
    };
    ws.onerror = () => {
        document.getElementById('ug-progress').classList.add('hidden');
        document.getElementById('ug-result').classList.remove('hidden');
        document.getElementById('ug-result').innerHTML = `<p class="text-red-400">Connection lost</p>
            <button onclick="ugReset()" class="mt-3 text-xs text-gray-500 hover:text-white">Try again</button>`;
    };
}

function ugReset() {
    _ugSelectedTabUrl = null;
    _ugSelectedName = null;
    _ugAudioFile = null;

    // Show search, hide everything else
    document.getElementById('ug-search-section').classList.remove('hidden');
    document.getElementById('ug-configure').classList.add('hidden');
    document.getElementById('ug-progress').classList.add('hidden');
    document.getElementById('ug-result').classList.add('hidden');

    // Reset audio controls
    const midiRadio = document.querySelector('input[name="ug-audio-mode"][value="midi"]');
    if (midiRadio) midiRadio.checked = true;
    ugToggleAudioMode();

    const audioLabel = document.getElementById('ug-audio-label');
    if (audioLabel) audioLabel.textContent = 'Drop audio or click to browse';
    const audioPath = document.getElementById('ug-audio-path');
    if (audioPath) audioPath.value = '';
    const audioFileInput = document.getElementById('ug-audio-file-input');
    if (audioFileInput) audioFileInput.value = '';
    const audioStatus = document.getElementById('ug-audio-status');
    if (audioStatus) {
        audioStatus.classList.add('hidden');
        audioStatus.className = 'mt-2 text-xs text-gray-600 hidden';
    }

    // Reset stem options
    const stemCheck = document.getElementById('ug-stem-check');
    if (stemCheck) stemCheck.checked = false;
    const stemOpts = document.getElementById('ug-stem-options');
    if (stemOpts) stemOpts.classList.add('hidden');
    const replicateKey = document.getElementById('ug-replicate-key');
    if (replicateKey) replicateKey.value = '';

    // Clear progress log
    const logEl = document.getElementById('ug-progress-log');
    if (logEl) logEl.innerHTML = '';
}
