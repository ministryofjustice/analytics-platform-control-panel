moj.Modules.bucketName = {
  inputName: 'new-datasource-name',

  init() {
    this.$input = $(`#${this.inputName}`);

    if (this.$input.length) {
      this.prefix = this.$input.data('bucket-prefix');
      this.bindEvents();
    }
  },

  bindEvents() {
    this.$input.on('keypress blur', () => {
      this.formatBucketName();
    });
  },

  formatBucketName() {
    let val = this.$input.val();

    if (val.length < this.prefix.length) {
      val = this.prefix;
    }

    val = val.toLowerCase().replace(/ /gi, '-');
    this.$input.val(val);
  },
};
