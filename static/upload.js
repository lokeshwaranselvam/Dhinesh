cat > /home/claude/project/static/js/upload.js << 'JSEOF'
// Drag & drop enhancement for file upload
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const dropContent = document.getElementById('dropContent');

if (dropZone && fileInput) {
  ['dragenter', 'dragover'].forEach(e =>
    dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.add('dragover'); })
  );
  ['dragleave', 'drop'].forEach(e =>
    dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.remove('dragover'); })
  );

  dropZone.addEventListener('drop', ev => {
    const files = ev.dataTransfer.files;
    if (files.length) {
      fileInput.files = files;
      updateLabel(files[0].name);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length) updateLabel(fileInput.files[0].name);
  });

  function updateLabel(name) {
    dropContent.innerHTML = `
      <div class="drop-icon">✅</div>
      <p><strong>${name}</strong></p>
      <p class="hint">Click to change file</p>
    `;
  }
}
JSEOF