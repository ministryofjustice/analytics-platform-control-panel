moj.Modules.listField = {
  fieldSelector: ".js-list-field",
  listSelector: ".js-list-field-list",
  addButtonSelector: ".js-list-field-add-item",
  removeButtonClass: "js-list-field-remove-item",
  inputClass: "js-list-field-input",
  listItemClass: "govuk-form-group",

  init() {
    if (document.querySelector(this.fieldSelector)) {
      document.querySelectorAll(this.fieldSelector).forEach(listField => {
        this.initListField(listField);
      });
    }
  },

  initListField(container) {
    const addItemButton = container.querySelector(this.addButtonSelector);
    addItemButton.addEventListener('click', (event) => {
      event.stopPropagation();
      event.preventDefault();
      this.addListItem(container);
    });
    container.querySelectorAll(`.${this.listItemClass}`).forEach(listItem => {
      this.initListItem(listItem);
    });
  },

  addListItem(container) {
    const listContainer = container.querySelector(this.listSelector);

    const listItem = document.createElement("div");
    listItem.className = this.listItemClass;

    const listItemInput = document.createElement("input");
    listItemInput.type = "text";
    listItemInput.className = `govuk-input govuk-!-width-two-thirds ${this.inputClass}`;
    listItemInput.name = `${listContainer.dataset.name}_${this.getNextIndex(container)}`;

    const removeItemButton = document.createElement("button");
    removeItemButton.className = `govuk-button hmcts-button--secondary ${this.removeButtonClass}`;
    removeItemButton.innerText = "Remove";

    listItem.appendChild(listItemInput);
    listItem.appendChild(removeItemButton);
    listContainer.appendChild(listItem);

    this.initListItem(listItem)
  },

  initListItem(listItem) {
    const removeButton = listItem.querySelector(`.${this.removeButtonClass}`);
    removeButton.addEventListener('click', (event) => {
      event.stopPropagation();
      event.preventDefault();
      const listContainer = listItem.parentElement;
      listItem.remove();
      this.resetNames(listContainer);
    });
  },

  getNextIndex(container) {
    return container.querySelectorAll(`.${this.inputClass}`).length;
  },

  resetNames(listContainer) {
    listContainer.querySelectorAll(`.${this.inputClass}`).forEach((listItemInput, index) => {
      listItemInput.name = `${listContainer.dataset.name}_${index}`;
    })
  }
};
