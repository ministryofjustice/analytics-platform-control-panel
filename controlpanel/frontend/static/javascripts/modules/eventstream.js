/* Listen for Server Sent Events */
moj.Modules.eventStream = {
  eventsPath: '/events',
  eventSource: null,
  listenerClass: '.sse-listener',

  init() {
    if (document.querySelectorAll(this.listenerClass).length) {
      this.eventSource = new EventSource(this.eventsPath);
    }
  },

  addEventListener(type, listener, options) {
    this.eventSource.addEventListener(type, listener, options);
  }
};
