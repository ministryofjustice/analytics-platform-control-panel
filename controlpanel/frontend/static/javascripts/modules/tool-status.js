moj.Modules.toolStatus = {
  eventType: "toolStatusChange",
  listenerClass: ".tool-status",

  init() {
    const toolStatusListeners = document.querySelectorAll(this.listenerClass);
    if (toolStatusListeners) {
      this.bindEvents(toolStatusListeners);
    }
  },

  bindEvents(listeners) {
    listeners.forEach(listener => {
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
