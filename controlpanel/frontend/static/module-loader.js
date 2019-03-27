const moj = {

  Modules: {},

  Helpers: {},

  Events: $({}),

  init() {
    Object.keys(moj.Modules).forEach((key) => {
      if (typeof moj.Modules[key].init === 'function') {
        moj.Modules[key].init();
      }
    });

    moj.Events.trigger('render');
  },

  // safe logging
  log(msg) {
    if (window && window.console) {
      window.console.log(msg);
    }
  },

  dir(obj) {
    if (window && window.console) {
      window.console.dir(obj);
    }
  },

};

window.moj = moj;
