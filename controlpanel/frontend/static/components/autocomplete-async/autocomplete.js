var repos = [];
var search_tag = "#display_result_repo";

function addToRepos(index) {
  $("#loading_gif").show();

  fetch('/api/cpanel/v1/repos/?' + new URLSearchParams({page: index}))
  .then(response => response.json())
  .then(data => {

    repos = repos.concat(data.map(item => ({label: item.full_name, value: item.html_url})));
    let count = parseInt($('#repos_loaded').text());
    $('#repos_loaded').text(repos.length)
    $(search_tag).autocomplete('option', 'source', repos);

    $("#loading_gif").hide();
    $("#loading_text").text("added: ");

    $('#current_index').val(index +1);
  })
  .catch(err => console.log('err', err));
}

moj.Modules.autocomplete = {
  selector: "#display_result_repo",
  bindEvents() {
    $(search_tag).autocomplete({source: repos});

    let index = parseInt($('#current_index').val());
    addToRepos(index)
    $('#ui-id-1').css({'padding-inline-start': '0px'})

    $('#add_more').on('click', function() {
      let index = parseInt($('#current_index').val());
      addToRepos(index)
    });
  },
  init() {
    if($(this.selector).length){
      this.bindEvents();
    }
  }
}
