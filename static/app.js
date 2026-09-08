let currentTab = 'qa';
let qaRows = [];
let currentQAIndex = 0;
let isAudioPlaying = false;
let audioClockInterval = null;

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

// ============================================================
// 1. OPTION A: NEW TEXT + MP3
// ============================================================

async function loadTextAndMp3() {
  if (!window.pywebview?.api) return;
  const btn = document.getElementById('btn-load-unified');
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Loading...";
  }

  const res = await window.pywebview.api.load_txt_and_mp3();
  if (btn) {
    btn.disabled = false;
    btn.innerText = "⚡ New: Text + MP3";
  }

  if (res && res.success) {
    qaRows = res.rows || [];
    currentQAIndex = 0;
    document.getElementById('qa-editor-card').classList.remove('hidden');
    displayQARow();
    resetAudioClock();
    alert(`Loaded ${res.total} sentences from text file!\nPress Space to Play/Pause, and Enter to Stamp.`);
  } else if (res && res.error) {
    alert(res.error);
  }
}

// ============================================================
// 2. OPTION B: OPEN CLEANED CSV
// ============================================================

async function browseCSV() {
  if (!window.pywebview?.api) return;
  const res = await window.pywebview.api.select_file('csv');
  if (res && res.success) {
    qaRows = res.rows || [];
    currentQAIndex = 0;
    document.getElementById('qa-editor-card').classList.remove('hidden');
    displayQARow();
    resetAudioClock();
    alert(`Loaded CSV with ${res.total} rows.\nAudio: ${res.audio_filename || "Please click 'Select MP3' to connect"}`);
  } else if (res && res.error) {
    alert(res.error);
  }
}

async function browseSingleAudioFile() {
  if (!window.pywebview?.api) return;
  const res = await window.pywebview.api.select_audio_file();
  if (res && res.success) {
    qaRows.forEach(r => r.mp3 = res.audio_name);
    const mp3In = document.getElementById('qa-mp3-input');
    if (mp3In) mp3In.value = res.audio_name;

    resetAudioClock();
    displayQARow();
    alert(`Connected Audio: ${res.audio_name}\nYou can now Play/Pause and Sync.`);
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

// ============================================================
// AUDIO CONTROLS (PLAY / PAUSE / REWIND / TIME TRACKER)
// ============================================================

async function toggleMasterPlay() {
  if (!window.pywebview?.api || qaRows.length === 0) return;

  const res = await window.pywebview.api.play_or_pause_audio();
  if (res && res.success) {
    updateMasterPlayUI(res.state === "playing");
    if (res.state === "playing") {
      startAudioClock();
    } else {
      stopAudioClock();
      updateClockDisplay(res.current_sec);
    }
  } else if (res && res.error) {
    alert(res.error);
  }
}

async function seekAudioRelative(offset) {
  if (!window.pywebview?.api || qaRows.length === 0) return;
  const res = await window.pywebview.api.seek_audio_relative(offset);
  if (res && res.success) {
    updateMasterPlayUI(res.state === "playing");
    updateClockDisplay(res.current_sec);
    if (res.state === "playing") startAudioClock();
  }
}

function updateMasterPlayUI(playing) {
  isAudioPlaying = playing;
  const icon = document.getElementById('btn-master-icon');
  const txt = document.getElementById('btn-master-text');
  const btn = document.getElementById('btn-master-play');

  if (playing) {
    if (icon) icon.innerText = "⏸";
    if (txt) txt.innerText = "Pause";
    if (btn) btn.style.backgroundColor = "#d97706";
  } else {
    if (icon) icon.innerText = "▶";
    if (txt) txt.innerText = "Play Audio";
    if (btn) btn.style.backgroundColor = "#059669";
  }
}

function startAudioClock() {
  if (audioClockInterval) clearInterval(audioClockInterval);
  audioClockInterval = setInterval(async () => {
    const sec = await window.pywebview.api.get_current_audio_sec();
    if (sec !== undefined) {
      updateClockDisplay(sec);
    }
  }, 100);
}

function stopAudioClock() {
  if (audioClockInterval) clearInterval(audioClockInterval);
}

function resetAudioClock() {
  stopAudioClock();
  updateMasterPlayUI(false);
  updateClockDisplay(0.0);
}

function updateClockDisplay(sec) {
  const clock = document.getElementById('live-audio-clock');
  if (clock) {
    clock.innerText = `${parseFloat(sec).toFixed(2)}s`;
  }
}

// ============================================================
// STAMP & NEXT (ENTER KEY ACTION)
// ============================================================

async function stampAndGoNext() {
  if (qaRows.length === 0 || !window.pywebview?.api) return;

  const currentSec = await window.pywebview.api.get_current_audio_sec();

  document.getElementById('qa-end-time').value = currentSec;
  syncCurrentInputsToMemory();

  await saveQARowSilently();

  if (currentQAIndex < qaRows.length - 1) {
    qaRows[currentQAIndex + 1].start_time = currentSec;
    currentQAIndex++;
    displayQARow();
  } else {
    alert("🎉 All lines in dataset stamped successfully!");
  }
}

async function previewCurrentSegment() {
  if (qaRows.length === 0 || !window.pywebview?.api) return;
  const st = parseFloat(document.getElementById('qa-start-time')?.value) || 0.0;
  const et = parseFloat(document.getElementById('qa-end-time')?.value) || 0.0;

  if (et <= st) {
    alert("Please stamp or enter an End Time greater than Start Time.");
    return;
  }

  await window.pywebview.api.play_segment_preview(st, et);
}

// ============================================================
// DISPLAY & VISUAL STYLING
// ============================================================

function syncCurrentInputsToMemory() {
  if (qaRows.length === 0) return;
  const mp3 = document.getElementById('qa-mp3-input')?.value.trim() || '';
  const editor = document.getElementById('qa-caption-editor');
  const cap = editor ? editor.innerHTML : '';
  const st = parseFloat(document.getElementById('qa-start-time')?.value) || 0.0;
  const et = parseFloat(document.getElementById('qa-end-time')?.value) || 0.0;

  qaRows[currentQAIndex].mp3 = mp3;
  qaRows[currentQAIndex].caption = cap;
  qaRows[currentQAIndex].start_time = st;
  qaRows[currentQAIndex].end_time = et;
}

function displayQARow() {
  if (!qaRows || qaRows.length === 0) return;
  const row = qaRows[currentQAIndex];

  const rowInd = document.getElementById('qa-row-indicator');
  const mp3In = document.getElementById('qa-mp3-input');
  const badge = document.getElementById('qa-sync-badge');
  const editor = document.getElementById('qa-caption-editor');
  const stIn = document.getElementById('qa-start-time');
  const etIn = document.getElementById('qa-end-time');
  const nextPreview = document.getElementById('qa-next-line-preview');

  if (rowInd) rowInd.innerText = `Row ${currentQAIndex + 1} of ${qaRows.length}`;
  if (mp3In) mp3In.value = row.mp3 || '';
  if (stIn) stIn.value = row.start_time !== undefined ? row.start_time : 0.0;
  if (etIn) etIn.value = row.end_time !== undefined ? row.end_time : 0.0;

  if (nextPreview) {
    if (currentQAIndex + 1 < qaRows.length) {
      nextPreview.innerText = qaRows[currentQAIndex + 1].caption.replace(/<[^>]+>/g, '') || '-';
    } else {
      nextPreview.innerText = "(End of text)";
    }
  }

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
    const dur = Math.max(0, (row.end_time - row.start_time)).toFixed(2);
    if (row.end_time > 0) {
      badge.style.backgroundColor = '#022c22';
      badge.style.color = '#34d399';
      badge.innerText = `✅ Synced (${dur}s) [${row.start_time}s - ${row.end_time}s]`;
    } else {
      badge.style.backgroundColor = '#1f2937';
      badge.style.color = '#94a3b8';
      badge.innerText = `⏳ Pending Sync`;
    }
  }
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
    targetNode.style.padding = '4px 12px';
    targetNode.style.borderRadius = '4px';
    syncCurrentInputsToMemory();
    saveQARowSilently();
    return;
  }

  if (!selectedText.trim()) {
    alert("Please select words inside Caption Editor first.");
    return;
  }

  const span = document.createElement('span');
  span.setAttribute('data-style', 'box');
  span.setAttribute('data-bg', bg);
  span.setAttribute('data-bc', bc);
  span.style.backgroundColor = bg;
  span.style.border = `3px solid ${bc}`;
  span.style.color = '#ffffff';
  span.style.padding = '4px 12px';
  span.style.borderRadius = '4px';
  span.style.display = 'inline-block';
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
    targetNode.style.textShadow = `-2px -2px 0 ${c}, 2px -2px 0 ${c}, -2px 2px 0 ${c}, 2px 2px 0 ${c}`;
    syncCurrentInputsToMemory();
    saveQARowSilently();
    return;
  }

  if (!selectedText.trim()) {
    alert("Please select words inside Caption Editor first.");
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
  const row = qaRows[currentQAIndex];
  await window.pywebview.api.update_row_data(
    currentQAIndex, row.mp3, row.caption, row.start_time || 0.0, row.end_time || 0.0
  );
}

async function saveQARow() {
  if (qaRows.length === 0 || !window.pywebview?.api) return;
  syncCurrentInputsToMemory();
  const row = qaRows[currentQAIndex];

  const res = await window.pywebview.api.update_row_data(
    currentQAIndex, row.mp3, row.caption, row.start_time || 0.0, row.end_time || 0.0
  );
  if (res && res.success) {
    qaRows[currentQAIndex].status = res.status;
    qaRows[currentQAIndex].duration = res.duration;
    displayQARow();
    alert("Saved row successfully!");
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
    if (!qaRows[i].end_time || qaRows[i].end_time <= qaRows[i].start_time) {
      currentQAIndex = i;
      displayQARow();
      return;
    }
  }
  alert("All rows have timestamps assigned!");
}

async function exportCleanedCSV() {
  if (!window.pywebview?.api) return;
  await saveQARowSilently();
  const res = await window.pywebview.api.export_cleaned_csv();
  if (res && res.success) {
    alert(`Cleaned CSV exported to:\n${res.path}`);
  }
}

async function startRender() {
  if (!window.pywebview?.api) return;
  await saveQARowSilently();

  const bgmCheckbox = document.getElementById('gen-enable-bgm');

  const cfg = {
    format: document.getElementById('gen-format')?.value || 'landscape',
    position: document.getElementById('gen-position')?.value || 'middle',
    font_size: parseInt(document.getElementById('gen-font-size')?.value) || 44,
    line_spacing: parseInt(document.getElementById('gen-line-spacing')?.value) || 22,
    max_lines: parseInt(document.getElementById('gen-max-lines')?.value) || 3,
    lines_per_page: parseInt(document.getElementById('gen-max-lines')?.value) || 3,
    overlay_mode: document.getElementById('gen-overlay-mode')?.value || 'Full Video Overlay',
    color: document.getElementById('gen-color')?.value || '#000000',
    opacity: document.getElementById('gen-opacity')?.value || '50',
    enable_bgm: bgmCheckbox ? bgmCheckbox.checked : true,
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
  setTimeout(() => {
    if (statusContainer) statusContainer.classList.add('hidden');
  }, 2000);
};

// ============================================================
// GLOBAL HOTKEYS (SPACE = PLAY/PAUSE, ENTER = STAMP & NEXT)
// ============================================================

window.addEventListener('keydown', (e) => {
  const isEditingText = (
    e.target.tagName === 'INPUT' || 
    e.target.tagName === 'TEXTAREA' || 
    e.target.getAttribute('contenteditable') === 'true'
  );

  // Spacebar to Play/Pause
  if (e.code === 'Space' && !isEditingText) {
    e.preventDefault();
    if (currentTab === 'qa') {
      toggleMasterPlay();
    }
    return;
  }

  // Enter or Ctrl+Enter to Stamp End & Go Next
  if (e.code === 'Enter') {
    if (!isEditingText || e.ctrlKey) {
      e.preventDefault();
      if (currentTab === 'qa') {
        stampAndGoNext();
      }
      return;
    }
  }

  // Preview shortcut (P key)
  if ((e.key === 'p' || e.key === 'P') && !isEditingText) {
    e.preventDefault();
    if (currentTab === 'qa') {
      previewCurrentSegment();
    }
    return;
  }
});