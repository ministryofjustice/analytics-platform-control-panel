moj.Modules.autocomplete = {
  selector: "#display_result_repo",
  repos : [],
  bindEvents() {
    var repos = this.repos;
    var search_tag = this.selector;
    $(search_tag).autocomplete({source: repos});

    for (let index = 1; index < 15; index++) {
      fetch('/api/cpanel/v1/repos/?' + new URLSearchParams({page: index}))
      .then(response => response.json())
      .then(data => {
        repos = repos.concat(data.map(item => ({label: item.full_name, value: item.html_url})));
        let count = parseInt($('#repos_loaded').text());
        $('#repos_loaded').text(count + data.length)
        $(search_tag).autocomplete('option', 'source', repos);

        if(data.length == 0){
          $("#loading_gif").hide();
          $("#loading_text").text("complete: ");
        }
      })
      .catch(err => console.log('err', err));
    }
  },
  init() {
    if($(this.selector).length){
      this.bindEvents();
    }
  }
}
