var repos = [];

moj.Modules.registerAppFromRepo = {
  $repoListSelector: $("#display_result_repo"),
  formId: "register_app",
  $orgSelectName: $("input[type=radio][name=org_names]"),
  $loadingGIF: $("#loading_gif"),
  $loadingText: $("#loading_text"),
  $currentPageIndex: $('#current_index'),
  $reposLoaded: $('#repos_loaded'),
  $nextRepoPageBtn: $('#add_more'),
  $envMultiSelector: $("#deployment_envs_list"),

  init() {
    if ($(`form#${this.formId}`).length) {
      this.$form = $(`form#${this.formId}`);
      this.$formSubmit = this.$form.find('input[type="submit"]');

      this.$repoListSelector.autocomplete({source: repos});
      $('#ui-id-1').css({'padding-inline-start': '0px'})

      this.bindEvents();
      this.addToRepos(1);
    }
  },

  addToRepos(index) {
    let currentOrg = $("input[name='org_names']:checked").val();
    this.$loadingGIF.show();

    fetch('/api/cpanel/v1/repos/' + currentOrg + '/?' + new URLSearchParams({page: index}))
    .then(response => response.json())
    .then(data => {
      repos = repos.concat(data.map(item => ({label: item.full_name, value: item.html_url})));
      this.$reposLoaded.text(repos.length)
      this.$repoListSelector.autocomplete('option', 'source', repos);

      this.$loadingGIF.hide();
      this.$loadingText.text("added: ");

      this.$currentPageIndex.val(index +1);
     })
    .catch(err => console.log('err', err));
  },

  readRepoEnvs() {
    let currentOrg = this.$orgSelectName.val();
    let currentRepo = this.$repoListSelector.val();
    let repoURLs = currentRepo.split("/")
    fetch('/api/cpanel/v1/repos/' + repoURLs[3] + '/' + repoURLs[4] + '/environments')
    .then(response => response.json())
    .then(data => {
      this.$envMultiSelector.empty();
      for (let i = 0; i < data.length; ++i) {
        var item_str = '<div class="govuk-checkboxes__item">';
        item_str += '<input class="govuk-checkboxes__input" id="deployemnt_env_'+ i +'" name="deployment_envs" type="checkbox" value="' + data[i] + '">';
        item_str += '<label class="govuk-label govuk-checkboxes__label" for="deployemnt_env_i">' + data[i] + '</label>';
        item_str += '</div>';
        this.$envMultiSelector.append(item_str);
      }
     })
    .catch(err => console.log('err', err));
  },

  bindEvents() {

    this.$nextRepoPageBtn.on('click', () => {
      let index = parseInt($('#current_index').val());
      this.addToRepos(index);
    });

    this.$repoListSelector.on('change', () => {
      this.readRepoEnvs();
    });

    this.$orgSelectName.on('change', () => {
      repos = [];
      this.$currentPageIndex.val(1);
      let index = parseInt(this.$currentPageIndex.val());
      this.addToRepos(index)
    });

  },

}
