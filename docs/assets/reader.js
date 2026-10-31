// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
function enhanceReading() {
  for (const example of document.querySelectorAll('.md-typeset .highlight')) {
    const pre = example.querySelector('pre');
    if (!pre) continue;
    let filename = example.querySelector('.filename');
    if (!filename) {
      filename = document.createElement('span');
      filename.className = 'filename';
      filename.textContent = 'Code';
      example.prepend(filename);
    }
    const language = filename.textContent.trim();
    pre.tabIndex = 0;
    pre.setAttribute('role', 'region');
    pre.setAttribute('aria-label', `${language} code example`);
    pre.setAttribute('aria-description', 'Use the arrow keys to scroll when this example is wider than the page.');
    const toolbar = pre.querySelector(':scope > .md-code__nav');
    if (toolbar) example.append(toolbar);
    const copy = example.querySelector('[data-md-type="copy"]');
    if (copy) copy.setAttribute('aria-label', `Copy ${language} example`);
    for (const number of example.querySelectorAll('[data-linenos]')) {
      number.setAttribute('aria-hidden', 'true');
    }
  }

  for (const table of document.querySelectorAll('.md-typeset__scrollwrap')) {
    table.tabIndex = 0;
    table.setAttribute('role', 'region');
    table.setAttribute('aria-label', 'Data table');
    table.setAttribute('aria-description', 'Use the arrow keys to scroll when this table is wider than the page.');
  }

  for (const set of document.querySelectorAll('.md-typeset .tabbed-set')) {
    if (set.dataset.readerTabs) continue;
    const labels = [...set.querySelectorAll(':scope > .tabbed-labels > label')];
    const panels = [...set.querySelectorAll(':scope > .tabbed-content > .tabbed-block')];
    const list = set.querySelector(':scope > .tabbed-labels');
    if (!list || !labels.length || labels.length !== panels.length) continue;
    list.setAttribute('role', 'tablist');
    list.setAttribute('aria-label', 'Example options');
    const inputs = labels.map((label) => document.getElementById(label.htmlFor));
    if (inputs.some((input) => !(input instanceof HTMLInputElement))) continue;
    set.dataset.readerTabs = 'ready';
    const sync = () => {
      labels.forEach((label, index) => {
        const selected = inputs[index].checked;
        label.setAttribute('aria-selected', String(selected));
        label.tabIndex = selected ? 0 : -1;
      });
    };
    labels.forEach((label, index) => {
      const input = inputs[index];
      label.id ||= `${input.id}-tab`;
      panels[index].id ||= `${input.id}-panel`;
      label.setAttribute('role', 'tab');
      label.setAttribute('aria-controls', panels[index].id);
      panels[index].setAttribute('role', 'tabpanel');
      panels[index].setAttribute('aria-labelledby', label.id);
      input.addEventListener('change', sync);
      label.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Enter', ' '].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? labels.length - 1
          : event.key === 'ArrowLeft' ? (index + labels.length - 1) % labels.length
          : event.key === 'ArrowRight' ? (index + 1) % labels.length : index;
        inputs[next].click();
        labels[next].focus();
      });
    });
    sync();
  }
}
function startReading() {
  // Material mounts code controls and table wrappers after the document stream.
  const content = document.querySelector('.md-content');
  if (content) new MutationObserver(enhanceReading).observe(content, { childList: true, subtree: true });
  enhanceReading();
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startReading, { once: true });
} else {
  startReading();
}
