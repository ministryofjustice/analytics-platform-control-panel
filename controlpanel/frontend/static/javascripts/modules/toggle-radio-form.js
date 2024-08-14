moj.Modules.toggleRadioForm = {
  panelClass: 'radio-subform',
  selector: 'data-show-if-selected',
  radioButtonClass: 'govuk-radios__input',
  hiddenClass: 'govuk-!-display-none',

  init() {
    const panels = document.querySelectorAll(`.${this.panelClass}`);
    if (panels) {
      this.bindEvents(panels);
    }
  },

  bindEvents(panels) {

    const radios = document.querySelectorAll(`.${this.radioButtonClass}`);

    radios.forEach(radio => {
      radio.addEventListener('change', () => {
        const name = radio.getAttribute('name');

        document.querySelectorAll(`input[name="${name}"]`).forEach(otherRadio => {
          if (otherRadio !== radio) {
              // Trigger a custom 'deselect' event on every member of the current radio group except the clicked one...
              const event = new Event('deselect');
              otherRadio.dispatchEvent(event);
          }
        });
      });
    });

    panels.forEach(panel => {
      const attribute = panel.getAttribute(this.selector);
      var formItem = document.querySelector(`#${attribute}`);

      this.setVisibility(panel, formItem.checked);

      formItem.addEventListener('change', (event) => {
        this.setVisibility(panel, event.target.checked);
      });

      formItem.addEventListener('deselect', (event) => {
        this.setVisibility(panel, event.target.checked);
      });
    });
  },

  setVisibility(panel, show) {
    if (show) {
      panel.classList.remove(this.hiddenClass);
    } else {
      panel.classList.add(this.hiddenClass);
    }
  }
};
