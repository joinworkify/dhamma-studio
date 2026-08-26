let currentTab = 'qa';
let qaRows = [];
let currentQAIndex = 0;
let isPlaying = false;

function switchTab(tab) {
  currentTab = tab;
  const tabQA = document.getElementById('tab-qa');
  const tabGen = document.getElementById('tab-gen');
  const navQA = document.getElementById('nav-qa');
  const navGen = document.getElementById('nav-gen');

  if (tab === 'qa') {
    tabQA.classList.remove('hidden');
    tabGen.classList.add('hidden');
    navQA.className = "btn btn-primary";
    navGen.className = "btn btn-secondary";
  } else {
    syncCurrentInputsToMemory();
    tabQA.classList.add('hidden');
    tabGen.classList.remove('hidden');
    navGen.className = "btn btn-primary";
    navQA.className = "btn btn-secondary";
  }
}

function adjustDefaultFontSettings() {
  const fmt = document.getElementById('gen-format')?.value;
  const fontIn = document.getElementById('gen-font-size');
  const spaceIn = document.getElementById('gen-line-spacing');
  if (fmt === 'mobile') {
    if (fontIn) fontIn.value = 38;
    if (spaceIn) spaceIn.value = 18;
  } else {
    if (fontIn) fontIn.value = 44;
    if (spaceIn) spaceIn.value = 22;
  }
}

async function browseCSV() {
  if (!window.pywebview?.api) return;
  const res = await window.pywebview.api.select_file('csv');
  if (res && res.success) {
    document.getElementById('label-csv-path').innerText = res.path;
    qaRows = res.rows || [];
    currentQAIndex = 0;
    document.getElementById('qa-editor-card').classList.remove('hidden');
    displayQARow();
  } else if (res && res.error) {
    alert(res.error);
  }
}

async function browseAudios() {
  if (!window.pywebview?.api) return;
  const res = await window.pywebview.api.select_folder('audios');
  if (res && res.success) {
    document.getElementById('label-audios-path').innerText = res.path;
    if (qaRows.length > 0) {
      displayQARow();
    }
  }
}

async function browseImages() {
  if (!window.pywebview?.api) return;
  const res = await window.pywebview.api.select_folder('images');
  if (res && res.success) {
    document.getElementById('label-images-path').innerText = res.path;
  }
}

async function browseLogo() {
  if (!window.pywebview?.api) return;
  const res = await window.pywebview.api.select_file('logo');
  if (res && res.success) {
    document.getElementById('label-logo-path').innerText = res.path;
  }
}

async function browseOutput() {
  if (!window.pywebview?.api) return;
  const res = await window.pywebview.api.select_file('output');
  if (res && res.success) {
    document.getElementById('label-output-path').innerText = res.path;
  }
}

function syncCurrentInputsToMemory() {
  if (qaRows.length === 0) return;
  const mp3 = document.getElementById('qa-mp3-input')?.value.trim() || '';
  const editor = document.getElementById('qa-caption-editor');
  const cap = editor ? editor.innerHTML : '';
  qaRows[currentQAIndex].mp3 = mp3;
  qaRows[currentQAIndex].caption = cap;
}

function displayQARow() {
  if (!qaRows || qaRows.length === 0) return;
  const row = qaRows[currentQAIndex];

  const rowInd = document.getElementById('qa-row-indicator');
  const mp3In = document.getElementById('qa-mp3-input');
  const badge = document.getElementById('qa-sync-badge');
  const editor = document.getElementById('qa-caption-editor');

  if (rowInd) rowInd.innerText = `Row ${currentQAIndex + 1} of ${qaRows.length}`;
  if (mp3In) mp3In.value = row.mp3 || '';

  let cap = row.caption || '';
  if (editor) {
    if (!cap.includes('<div') && !cap.includes('<span') && !cap.includes('<p')) {
      const lines = cap.split('\n').filter(l => l.trim() !== '');
      if (lines.length > 0) {
        cap = lines.map(l => `<div>${l}</div>`).join('');
      } else {
        cap = '<div></div>';
      }
    }
    editor.innerHTML = cap;
  }

  if (badge) {
    if (row.status === 'missing') {
      badge.style.backgroundColor = '#450a0a';
      badge.style.color = '#f87171';
      badge.innerText = "❌ Missing Audio File";
    } else if (row.status === 'too_short') {
      badge.style.backgroundColor = '#451a03';
      badge.style.color = '#fbbf24';
      badge.innerText = `⚠️ Duration Too Short (${row.duration}s)`;
    } else if (row.status === 'too_long') {
      badge.style.backgroundColor = '#451a03';
      badge.style.color = '#fbbf24';
      badge.innerText = `⚠️ Duration Too Long (${row.duration}s)`;
    } else {
      badge.style.backgroundColor = '#022c22';
      badge.style.color = '#34d399';
      badge.innerText = `✅ In Sync (${row.duration}s)`;
    }
  }
  stopAudioState();
}

function applyBoxToSelection() {
  const editor = document.getElementById('qa-caption-editor');
  const selection = window.getSelection();
  if (!selection || !selection.rangeCount) return;

  const range = selection.getRangeAt(0);
  let selectedText = range.toString();

  let targetNode = range.commonAncestorContainer;
  if (targetNode.nodeType === Node.TEXT_NODE) {
    targetNode = targetNode.parentElement;
  }

  const bg = document.getElementById('tool-box-bg')?.value || '#8c4e12';
  const bc = document.getElementById('tool-box-bc')?.value || '#ffffff';

  if (!selectedText && targetNode && targetNode !== editor && targetNode.getAttribute('data-style')) {
    targetNode.setAttribute('data-style', 'box');
    targetNode.setAttribute('data-bg', bg);
    targetNode.setAttribute('data-bc', bc);
    targetNode.style.backgroundColor = bg;
    targetNode.style.border = `3px solid ${bc}`;
    targetNode.style.textShadow = 'none';
    targetNode.style.padding = '4px 12px';
    targetNode.style.margin = '3px 0';
    targetNode.style.display = 'inline-block';
    targetNode.style.borderRadius = '4px';
    targetNode.style.fontWeight = 'bold';
    syncCurrentInputsToMemory();
    saveQARowSilently();
    return;
  }

  if (!selectedText.trim()) {
    alert("Please select the text in the Caption Editor first.");
    return;
  }

  const span = document.createElement('span');
  span.setAttribute('data-style', 'box');
  span.setAttribute('data-bg', bg);
  span.setAttribute('data-bc', bc);
  span.style.backgroundColor = bg;
  span.style.border = `3px solid ${bc}`;
  span.style.color = '#ffffff';
  span.style.textShadow = 'none';
  span.style.padding = '4px 12px';
  span.style.margin = '3px 0';
  span.style.display = 'inline-block';
  span.style.borderRadius = '4px';
  span.style.fontWeight = 'bold';
  span.textContent = selectedText;

  range.deleteContents();
  range.insertNode(span);

  selection.removeAllRanges();
  syncCurrentInputsToMemory();
  saveQARowSilently();
}

function applyOutlineToSelection() {
  const editor = document.getElementById('qa-caption-editor');
  const selection = window.getSelection();
  if (!selection || !selection.rangeCount) return;

  const range = selection.getRangeAt(0);
  let selectedText = range.toString();

  let targetNode = range.commonAncestorContainer;
  if (targetNode.nodeType === Node.TEXT_NODE) {
    targetNode = targetNode.parentElement;
  }

  const w = document.getElementById('tool-outline-w')?.value || '3';
  const c = document.getElementById('tool-outline-c')?.value || '#000000';

  if (!selectedText && targetNode && targetNode !== editor && targetNode.getAttribute('data-style')) {
    targetNode.setAttribute('data-style', 'outline');
    targetNode.setAttribute('data-w', w);
    targetNode.setAttribute('data-c', c);
    targetNode.style.backgroundColor = 'transparent';
    targetNode.style.border = 'none';
    targetNode.style.padding = '0';
    targetNode.style.margin = '0';
    targetNode.style.display = 'inline';
    targetNode.style.fontWeight = 'normal';
    targetNode.style.textShadow = `-2px -2px 0 ${c}, 2px -2px 0 ${c}, -2px 2px 0 ${c}, 2px 2px 0 ${c}`;
    syncCurrentInputsToMemory();
    saveQARowSilently();
    return;
  }

  if (!selectedText.trim()) {
    alert("Please select the text in the Caption Editor first.");
    return;
  }

  const span = document.createElement('span');
  span.setAttribute('data-style', 'outline');
  span.setAttribute('data-w', w);
  span.setAttribute('data-c', c);
  span.style.textShadow = `-2px -2px 0 ${c}, 2px -2px 0 ${c}, -2px 2px 0 ${c}, 2px 2px 0 ${c}`;
  span.style.color = '#ffffff';
  span.textContent = selectedText;

  range.deleteContents();
  range.insertNode(span);

  selection.removeAllRanges();
  syncCurrentInputsToMemory();
  saveQARowSilently();
}

function removeStyleFromSelection() {
  const editor = document.getElementById('qa-caption-editor');
  if (!editor) return;

  const selection = window.getSelection();
  let range = (selection && selection.rangeCount > 0) ? selection.getRangeAt(0) : null;
  let selectedText = range ? range.toString().trim() : "";

  if (selectedText && range) {
    const textNode = document.createTextNode(selectedText);
    range.deleteContents();
    range.insertNode(textNode);
  } else if (range) {
    let node = range.commonAncestorContainer;
    if (node.nodeType === Node.TEXT_NODE) {
      node = node.parentElement;
    }
    if (node && node !== editor && node.getAttribute('data-style')) {
      const textNode = document.createTextNode(node.innerText);
      node.replaceWith(textNode);
    } else {
      const plainText = editor.innerText;
      const lines = plainText.split('\n').filter(l => l.trim() !== '');
      if (lines.length > 0) {
        editor.innerHTML = lines.map(l => `<div>${l}</div>`).join('');
      } else {
        editor.innerHTML = '<div></div>';
      }
    }
  } else {
    const plainText = editor.innerText;
    editor.innerHTML = `<div>${plainText}</div>`;
  }

  if (selection) selection.removeAllRanges();
  syncCurrentInputsToMemory();
  saveQARowSilently();
}

async function saveQARowSilently() {
  if (qaRows.length === 0 || !window.pywebview?.api) return;
  syncCurrentInputsToMemory();
  const mp3 = qaRows[currentQAIndex].mp3;
  const cap = qaRows[currentQAIndex].caption;
  await window.pywebview.api.update_row_data(currentQAIndex, mp3, cap);
}

async function saveQARow() {
  if (qaRows.length === 0 || !window.pywebview?.api) return;
  syncCurrentInputsToMemory();
  const mp3 = qaRows[currentQAIndex].mp3;
  const cap = qaRows[currentQAIndex].caption;

  const res = await window.pywebview.api.update_row_data(currentQAIndex, mp3, cap);
  if (res && res.success) {
    qaRows[currentQAIndex].status = res.status;
    qaRows[currentQAIndex].duration = res.duration;
    displayQARow();
    alert("Saved successfully!");
  }
}

async function prevQARow() {
  if (currentQAIndex > 0) {
    await saveQARowSilently();
    currentQAIndex--;
    displayQARow();
  }
}

async function nextQARow() {
  if (currentQAIndex < qaRows.length - 1) {
    await saveQARowSilently();
    currentQAIndex++;
    displayQARow();
  }
}

async function jumpNextIssue() {
  await saveQARowSilently();
  for (let i = currentQAIndex + 1; i < qaRows.length; i++) {
    if (qaRows[i].status !== 'ok') {
      currentQAIndex = i;
      displayQARow();
      return;
    }
  }
  for (let i = 0; i <= currentQAIndex; i++) {
    if (qaRows[i].status !== 'ok') {
      currentQAIndex = i;
      displayQARow();
      return;
    }
  }
  alert("No more warnings or issues found.");
}

async function toggleAudio() {
  if (!window.pywebview?.api || qaRows.length === 0) return;
  const btn = document.getElementById('qa-play-btn');

  if (isPlaying) {
    await window.pywebview.api.stop_audio();
    stopAudioState();
  } else {
    const mp3 = document.getElementById('qa-mp3-input')?.value.trim() || '';
    const res = await window.pywebview.api.play_audio(mp3);
    if (res && res.success) {
      isPlaying = true;
      if (btn) {
        btn.innerHTML = `<span>⏹ Stop</span> <span style="background: rgba(0,0,0,0.25); padding: 2px 6px; border-radius: 4px; font-size: 10px; font-family: monospace;">Space</span>`;
        btn.style.backgroundColor = '#dc2626';
      }
    } else {
      alert(res?.error || "Cannot play audio file.");
    }
  }
}

function stopAudioState() {
  isPlaying = false;
  const btn = document.getElementById('qa-play-btn');
  if (btn) {
    btn.innerHTML = `<span>▶ Play</span> <span style="background: rgba(0,0,0,0.25); padding: 2px 6px; border-radius: 4px; font-size: 10px; font-family: monospace;">Space</span>`;
    btn.style.backgroundColor = '#059669';
  }
}

async function exportCleanedCSV() {
  if (!window.pywebview?.api) return;
  await saveQARowSilently();
  const res = await window.pywebview.api.export_cleaned_csv();
  if (res && res.success) {
    alert(`Cleaned CSV saved successfully:\n${res.path}`);
  }
}

async function startRender() {
  if (!window.pywebview?.api) return;
  await saveQARowSilently();

  const cfg = {
    format: document.getElementById('gen-format')?.value || 'landscape',
    position: document.getElementById('gen-position')?.value || 'middle',
    font_size: parseInt(document.getElementById('gen-font-size')?.value) || 44,
    line_spacing: parseInt(document.getElementById('gen-line-spacing')?.value) || 22,
    overlay_mode: document.getElementById('gen-overlay-mode')?.value || 'Full Video Overlay',
    color: document.getElementById('gen-color')?.value || '#000000',
    opacity: document.getElementById('gen-opacity')?.value || '50',
  };

  const statusContainer = document.getElementById('render-status-container');
  const bar = document.getElementById('render-progress-bar');
  const pctTxt = document.getElementById('render-status-pct');
  const txt = document.getElementById('render-status-text');

  if (statusContainer) statusContainer.classList.remove('hidden');
  if (bar) bar.style.width = '0%';
  if (pctTxt) pctTxt.innerText = '0%';
  if (txt) txt.innerText = 'Starting Render...';

  const btn = document.getElementById('btn-start-render');
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Rendering...";
  }

  const res = await window.pywebview.api.start_video_rendering(cfg);
  if (!res.success) {
    alert(res.error);
    if (btn) {
      btn.disabled = false;
      btn.innerText = "🎬 Start Video Rendering";
    }
  }
}

window.updateRenderStatus = function(msg, pct) {
  const txt = document.getElementById('render-status-text');
  const pctTxt = document.getElementById('render-status-pct');
  const bar = document.getElementById('render-progress-bar');
  if (txt) txt.innerText = msg;
  if (pctTxt) pctTxt.innerText = `${pct}%`;
  if (bar) bar.style.width = `${pct}%`;
};

window.renderFinished = function(success, message) {
  alert(message);
  const btn = document.getElementById('btn-start-render');
  if (btn) {
    btn.disabled = false;
    btn.innerText = "🎬 Start Video Rendering";
  }

  const statusContainer = document.getElementById('render-status-container');
  const txt = document.getElementById('render-status-text');
  const pctTxt = document.getElementById('render-status-pct');
  const bar = document.getElementById('render-progress-bar');

  if (txt) txt.innerText = "Ready for next video";
  if (pctTxt) pctTxt.innerText = "0%";
  if (bar) bar.style.width = "0%";

  setTimeout(() => {
    if (statusContainer) statusContainer.classList.add('hidden');
  }, 2000);
};

window.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && e.target.tagName !== 'TEXTAREA' && e.target.tagName !== 'INPUT' && e.target.getAttribute('contenteditable') !== 'true') {
    e.preventDefault();
    if (currentTab === 'qa') {
      toggleAudio();
    }
  }
});