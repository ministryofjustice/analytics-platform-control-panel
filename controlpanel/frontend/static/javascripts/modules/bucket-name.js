moj.Modules.bucketName = {
  selector: '[data-bucket-prefix]',

  init() {
    const input = document.querySelector(this.selector);
    if (input) {
      this.bindEvents(input);
    }
  },

  bindEvents(input) {
    input.addEventListener('keypress', this.ensurePrefix.bind(input));
    input.addEventListener('blur', this.ensurePrefix.bind(input));
  },

  ensurePrefix(e) {
    let val = this.value;
    if (val.length < this.dataset.bucketPrefix.length) {
      val = this.dataset.bucketPrefix;
    }
    this.value = val.toLowerCase().replace(/ /gi, '-');
  },
};
