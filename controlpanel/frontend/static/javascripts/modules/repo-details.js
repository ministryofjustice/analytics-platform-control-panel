moj.Modules.repoDetails = {
  formId: 'create_app',
  repoPrefix: 'https://github.com',
  orgSelectName: 'repo_org',
  repoSlugSelectName: 'name',
  repoSlugTypeaheadName: 'repo_typeahead',
  repoUrlHiddenInputName: 'repo_url',
  descriptionInputName: 'description',
  repos: null,
  descriptions: null,

  init() {
    if ($(`form#${this.formId}`).length) {
      this.$form = $(`form#${this.formId}`);
      this.$formSubmit = this.$form.find('input[type="submit"]');
      this.$repoSlugSelect = this.$form.find(`#${this.repoSlugSelectName}`);
      this.$orgSelect = this.$form.find(`#${this.orgSelectName}`);
      this.$repoUrlHiddenInput = this.$form.find(`#${this.repoUrlHiddenInputName}`);
      this.$repoSlugTypeahead = this.$form.find(`#${this.repoSlugTypeaheadName}`);

      this.bindEvents();
      this.showOrgRepos();
      this.checkRepoValue();
    }
  },

  bindEvents() {
    this.$orgSelect.on('change', () => {
      this.showOrgRepos();
    });
    this.$repoSlugTypeahead.on('change keyup', () => {
      this.checkRepoValue();
    });
  },

  checkRepoValue() {
    this.updateRepoUrl();
    if (this.$repoSlugTypeahead.val()) {
      this.$formSubmit.prop('disabled', false);
    } else {
      this.$formSubmit.prop('disabled', true);
    }
  },

  showOrgRepos() {
    const currentOrg = this.$orgSelect.val();
    const repoOptions = Array.from($(`optgroup[label="${currentOrg}"] option`));

    this.repos = repoOptions.map(opt => opt.text);
    this.descriptions = repoOptions.map(opt => opt.dataset.description);
    this.resetTypeahead();

    this.$repoSlugTypeahead.typeahead({
      order: 'asc',
      maxItem: 0,
      source: {
        data: this.repos,
      },
      callback: {
        onClickAfter: () => {
          this.checkRepoValue();
        },
        onCancel: () => {
          this.showOrgRepos();
        },
      },
    });
  },

  resetTypeahead() {
    this.$repoSlugTypeahead.val('');
    this.checkRepoValue();
    this.$repoSlugSelect.hide();
    this.updateDescription('');
    $('.typeahead__result, .typeahead__cancel-button').remove();
    $('.typeahead__container').removeClass('cancel result');
    $('#repo-results').addClass('js-hidden');
  },

  getRepoDescription(description) {
    this.updateDescription(description);
    $('#repo-results').removeClass('js-hidden');
  },

  updateRepoUrl() {
    const repoUrl = this.concatUrl(this.repoPrefix);
    this.$repoUrlHiddenInput.val(repoUrl);
    this.checkForExistingRepo();
  },

  checkForExistingRepo() {
    const index = this.repos.indexOf(this.$repoSlugTypeahead.val());
    this.updateDescription(this.descriptions[index]);

    if (index !== -1) {
      $('#repo-results').removeClass('js-hidden');
    } else {
      $('#repo-results').addClass('js-hidden');
    }
  },

  concatUrl(prefix) {
    const org = this.$orgSelect.val();
    const slug = this.$repoSlugTypeahead.val();

    return [prefix, org, slug].join('/');
  },

  updateDescription(description) {
    if (description) {
      $(`#${this.descriptionInputName}`).val(description);
      $(`#repo-${this.descriptionInputName}`).text(description);
    } else {
      $(`#repo-${this.descriptionInputName}`).text('None provided');
      $(`#${this.descriptionInputName}`).val('');
    }
  },
};
