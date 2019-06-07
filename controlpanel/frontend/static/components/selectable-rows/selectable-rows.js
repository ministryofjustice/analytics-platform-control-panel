moj.Modules.selectable_rows = {
  selector: '.selectable-rows tr',

  init() {
    if (document.querySelector(this.selector)) {
      this.bindEvents();
    }
  },

  bindEvents() {
    document.querySelectorAll(this.selector).forEach(row => {
      row.addEventListener("click", event => {
        const checkbox = row.querySelector("input[type='checkbox'].row-selector");
        if (checkbox) {
          if (checkbox.checked) {
            checkbox.checked = false;
            row.classList.remove('selected');
          } else {
            checkbox.checked = true;
            row.classList.add('selected');
          }
        }
      });
    });
  }
};
