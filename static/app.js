let qaRows = [];
let currentQAIndex = 0;

function switchTab(tab) {
  const qaBtn = document.getElementById('tab-qa-btn');
  const genBtn = document.getElementById('tab-gen-btn');
  const qaSec = document.getElementById('tab-qa');
  const genSec = document.getElementById('tab-gen');

  if (!qaSec || !genSec) return;

  if (tab === 'qa') {
    if (qaBtn) qaBtn.className = "px-5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 text-white shadow-sm transition";
    if (genBtn) genBtn.className = "px-5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 transition";
    qaSec.classList.remove('hidden');
    genSec.classList.add('hidden');
  } else {
    if (genBtn) genBtn.className = "px-5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 text-white shadow-sm transition";
    if (qaBtn) qaBtn.className = "px-5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 transition";
    genSec.classList.remove('hidden');
    qaSec.classList.add('hidden');
  }
}

async function browseFile(type) {
  if (!window.pywebview?.api) return;
  const res = await window.pywebview.api.select_file(type);
  if (res && res.success && type === 'csv') {
    const pathElem = document.getElementById('csv-path-display');
    if (pathElem) pathElem.innerText = res.path;
    qaRows = res.rows || [];
    currentQAIndex = 0;
    displayQARow();
  }
}

async function browseFolder(type) {
  if (!window.pywebview?.api) return;
  const res = await window.pywebview.api.select_folder(type);
  if (res && res.success) {
    if (type === 'audios') {
      const audioElem = document.getElementById('audios-path-display');
      if (audioElem) audioElem.innerText = res.path;
      if (qaRows.length > 0) displayQARow();
    } else if (type === 'images') {
      const imgElem = document.getElementById('images-path-display');
      if (imgElem) imgElem.innerText = res.path;
    }
  }
}

async function browseSaveOutput() {
  if (!window.pywebview?.api) return;
  const res = await window.pywebview.api.select_file('output');
  if (res && res.success) {
    const outElem = document.getElementById('output-path-display');
    if (outElem) outElem.innerText = res.path;
  }
}

function displayQARow() {
  if (!qaRows || qaRows.length === 0) return;
  const row = qaRows[currentQAIndex];

  const rowInd = document.getElementById('qa-row-indicator');
  const mp3In = document.getElementById('qa-mp3-input');
  const capIn = document.getElementById('qa-caption-input');
  const badge = document.getElementById('qa-sync-badge');

  if (rowInd) rowInd.innerText = `Row ${currentQAIndex + 1} of ${qaRows.length}`;
  if (mp3In) mp3In.value = row.mp3 || '';
  if (capIn) capIn.value = row.caption || '';

  if (badge) {
    if (row.status === 'missing') {
      badge.className = "text-xs font-semibold px-2.5 py-1 rounded-full bg-red-950 text-red-400 border border-red-800";
      badge.innerText = "❌ Missing Audio File";
    } else if (row.status === 'too_short') {
      badge.className = "text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-950 text-amber-400 border border-amber-800";
      badge.innerText = `⚠️ Duration Too Short (${row.duration}s)`;
    } else if (row.status === 'too_long') {
      badge.className = "text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-950 text-amber-400 border border-amber-800";
      badge.innerText = `⚠️ Duration Too Long (${row.duration}s)`;
    } else {
      badge.className = "text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800";
      badge.innerText = `✅ In Sync (${row.duration}s | ${row.char_len} chars)`;
    }
  }
}

async function saveQARow() {
  if (qaRows.length === 0 || !window.pywebview?.api) return;
  const mp3 = document.getElementById('qa-mp3-input')?.value.trim() || '';
  const cap = document.getElementById('qa-caption-input')?.value.trim() || '';
  
  const res = await window.pywebview.api.update_row_data(currentQAIndex, mp3, cap);
  if (res && res.success) {
    qaRows[currentQAIndex].mp3 = mp3;
    qaRows[currentQAIndex].caption = cap;
    qaRows[currentQAIndex].status = res.status;
    qaRows[currentQAIndex].duration = res.duration;
    qaRows[currentQAIndex].char_len = res.char_len;
    displayQARow();
  }
}

async function nextQARow() {
  if (currentQAIndex < qaRows.length - 1) {
    await saveQARow();
    currentQAIndex++;
    displayQARow();
  }
}

async function prevQARow() {
  if (currentQAIndex > 0) {
    await saveQARow();
    currentQAIndex--;
    displayQARow();
  }
}

async function jumpToIssue() {
  await saveQARow();
  for (let i = currentQAIndex + 1; i < qaRows.length; i++) {
    if (qaRows[i].status !== 'ok') {
      currentQAIndex = i;
      displayQARow();
      return;
    }
  }
  alert("No further flagged issues found ahead!");
}

async function playCurrentAudio() {
  if (!window.pywebview?.api) return;
  const mp3 = document.getElementById('qa-mp3-input')?.value.trim() || '';
  const res = await window.pywebview.api.play_audio(mp3);
  if (res && !res.success) alert(res.error);
}

function stopAudio() {
  if (window.pywebview?.api) {
    window.pywebview.api.stop_audio();
  }
}

async function exportCleanCSV() {
  if (!window.pywebview?.api) return;
  await saveQARow();
  const res = await window.pywebview.api.export_cleaned_csv();
  if (res && res.success) alert("Cleaned CSV exported to:\n" + res.path);
}

async function startRender() {
  if (!window.pywebview?.api) return;
  const cfg = {
    format: document.getElementById('gen-format')?.value || 'landscape',
    overlay_mode: document.getElementById('gen-overlay-mode')?.value || 'Full Video Overlay',
    position: document.getElementById('gen-position')?.value || 'middle',
    color: document.getElementById('gen-color')?.value || '#000000',
    opacity: document.getElementById('gen-opacity')?.value || '70',
    font_size: document.getElementById('gen-font-size')?.value || '46',
    line_spacing: document.getElementById('gen-line-spacing')?.value || '20'
  };

  const btn = document.getElementById('btn-render-start');
  if (btn) {
    btn.disabled = true;
    btn.classList.add('opacity-50', 'cursor-not-allowed');
  }

  const res = await window.pywebview.api.start_video_rendering(cfg);
  if (res && !res.success) {
    alert(res.error);
    if (btn) {
      btn.disabled = false;
      btn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
  }
}

// Window scope functions for Python evaluate_js callbacks
window.updateRenderStatus = function(text, pct) {
  const statusText = document.getElementById('render-status-text');
  const pctText = document.getElementById('render-pct-text');
  const pBar = document.getElementById('render-progress-bar');
  if (statusText) statusText.innerText = text;
  if (pctText) pctText.innerText = `${pct}%`;
  if (pBar) pBar.style.width = `${pct}%`;
};

window.renderFinished = function(success, msg) {
  const btn = document.getElementById('btn-render-start');
  if (btn) {
    btn.disabled = false;
    btn.classList.remove('opacity-50', 'cursor-not-allowed');
  }
  alert(msg);
};

// Setup DOM Event Listeners after document loads
document.addEventListener('DOMContentLoaded', () => {
  const colorPicker = document.getElementById('gen-color');
  const colorLabel = document.getElementById('gen-color-label');
  if (colorPicker && colorLabel) {
    colorPicker.addEventListener('input', (e) => {
      colorLabel.innerText = e.target.value;
    });
  }
});

// Spacebar shortcut for Audio Play
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && document.activeElement.tagName !== 'TEXTAREA' && document.activeElement.tagName !== 'INPUT') {
    e.preventDefault();
    playCurrentAudio();
  }
});