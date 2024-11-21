moj.Modules.toggleCheckboxForm = {
  subFormClass: 'checkbox-subform',
  selector: 'data-show-if-selected',
  hiddenClass: 'govuk-!-display-none',

  init() {
    const panels = document.querySelectorAll(`.${this.subFormClass}`);
    if (panels) {
      console.log(panels);
      this.bindEvents(panels);
    }
  },

  bindEvents(panels) {

    panels.forEach(panel => {
      console.log(panel);
      console.log(this.selector);
      const attribute = panel.getAttribute(this.selector);
      console.log(attribute);
      var formItem = document.querySelector(`[value=${attribute}]`);
      console.log(formItem);

      this.setVisibility(panel, formItem.checked);

      formItem.addEventListener('change', () => {
        this.togglePanel(panel);
      });
    });
  },

  togglePanel(panel) {
    panel.classList.toggle(this.hiddenClass);
  },

  setVisibility(panel, show) {
    if (show) {
      panel.classList.remove(this.hiddenClass);
    } else {
      panel.classList.add(this.hiddenClass);
    }
  }
};
