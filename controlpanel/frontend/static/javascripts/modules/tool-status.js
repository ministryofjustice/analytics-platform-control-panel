moj.Modules.toolStatus = {
  eventType: "toolStatusChange",
  listenerClass: ".sse-listener.tool-status",

  init() {
    if (document.querySelectorAll(this.listenerClass).length) {
      this.bindEvents();
    }
  },

  bindEvents() {
    document.querySelectorAll(this.listenerClass).forEach(listener => {
      moj.Modules.eventStream.addEventListener(
        this.eventType,
        this.buildEventHandler(listener)
      );
    });
  },

  buildEventHandler(listener) {
    return event => {
      const data = JSON.parse(event.data);
      if (data.toolName == listener.dataset.toolName) {
        listener.innerText = data.status;
      }
    };
  }
};
