"use strict";
let imagePickerNumber = 0;
function imageNode(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
class ImagePicker {
  constructor(root, {existing = 0} = {}) {
    this.root = root; this.existing = existing; this.entries = [];
    const id = `image-picker-${++imagePickerNumber}`;
    const label = imageNode("label", existing ? "Add images to this revision" : "Activity images (optional)");
    label.htmlFor = id;
    this.input = imageNode("input"); this.input.id = id; this.input.type = "file";
    this.input.multiple = true; this.input.accept = "image/jpeg,image/png,image/webp";
    const help = imageNode("p", "JPEG, PNG or WebP · Up to 20 images per activity · 8 MB each", "field-help");
    help.id = id + "-help"; this.input.setAttribute("aria-describedby", help.id);
    this.count = imageNode("p", undefined, "image-count"); this.count.setAttribute("aria-live", "polite");
    this.error = imageNode("p", "", "image-error"); this.error.setAttribute("role", "alert"); this.error.hidden = true;
    this.previews = imageNode("div", undefined, "image-grid selection-grid");
    root.append(label, help, this.input, this.count, this.error, this.previews);
    this.input.addEventListener("change", () => { this.add([...this.input.files]); this.input.value = ""; });
    this.render();
  }
  get files() { return this.entries.map(entry => entry.file); }
  add(files) {
    let error = "";
    if (this.existing + this.entries.length + files.length > 20) error = "An activity can contain at most 20 images. Choose fewer files.";
    else if (files.some(file => !( ["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
      (!file.type && /\.(jpe?g|png|webp)$/i.test(file.name)) ))) error = "Choose JPEG, PNG or WebP images.";
    else if (files.some(file => !file.size || file.size > 8 * 1024 * 1024)) error = "Each image must contain data and be at most 8 MB.";
    this.error.textContent = error; this.error.hidden = !error;
    if (error) return false;
    this.entries.push(...files.map(file => ({file, url: URL.createObjectURL(file)})));
    this.render(); return true;
  }
  remove(index) {
    const [entry] = this.entries.splice(index, 1);
    if (entry?.url) URL.revokeObjectURL(entry.url);
    this.error.hidden = true; this.render();
  }
  clear() {
    this.entries.forEach(entry => { if (entry.url) URL.revokeObjectURL(entry.url); }); this.entries = [];
    this.input.value = ""; this.error.hidden = true; this.render();
  }
  suspend() {
    this.entries.forEach(entry => { if (entry.url) URL.revokeObjectURL(entry.url); entry.url = null; });
    this.previews.replaceChildren();
  }
  resume() {
    this.entries.forEach(entry => { if (!entry.url) entry.url = URL.createObjectURL(entry.file); });
    this.render();
  }
  render() {
    this.count.textContent = `${this.existing + this.entries.length} / 20 images${this.existing ? ` · ${this.existing} already saved` : ""}`;
    this.input.disabled = this.existing + this.entries.length >= 20;
    this.previews.replaceChildren(...this.entries.map((entry, index) => {
      const tile = imageNode("div", undefined, "image-tile"), image = imageNode("img");
      image.src = entry.url; image.alt = `Selected image: ${entry.file.name}`;
      const caption = imageNode("p", entry.file.name, "image-filename");
      const remove = imageNode("button", "Remove", "secondary image-remove"); remove.type = "button";
      remove.setAttribute("aria-label", `Remove ${entry.file.name}`); remove.addEventListener("click", () => this.remove(index));
      tile.append(image, caption, remove); return tile;
    }));
  }
}
function submissionBody(description, files, expectedVersion) {
  if (!files.length) return expectedVersion === undefined ? {description} : {description, expected_version: expectedVersion};
  const body = new FormData(); body.append("description", description);
  if (expectedVersion !== undefined) body.append("expected_version", String(expectedVersion));
  files.forEach(file => body.append("images", file, file.name)); return body;
}
function imageGallery(record, ids = (record.images || []).map(image => image.id)) {
  const grid = imageNode("div", undefined, "image-grid evidence-gallery");
  const images = new Map((record.images || []).map(image => [image.id, image]));
  for (const id of ids) {
    const image = images.get(id); if (!image) continue;
    const tile = imageNode("div", undefined, "image-tile"), link = imageNode("a");
    link.href = `/api/images/${encodeURIComponent(image.id)}`; link.target = "_blank"; link.rel = "noopener noreferrer";
    link.setAttribute("aria-label", `Open original: ${image.filename}`);
    const thumbnail = imageNode("img"); thumbnail.src = link.href; thumbnail.alt = image.filename; thumbnail.loading = "lazy";
    link.append(thumbnail); tile.append(link, imageNode("p", image.filename, "image-filename"),
      imageNode("p", `${image.width} × ${image.height} · ${(image.size_bytes / 1024).toFixed(1)} KB`, "image-metadata"));
    grid.append(tile);
  }
  return grid;
}
