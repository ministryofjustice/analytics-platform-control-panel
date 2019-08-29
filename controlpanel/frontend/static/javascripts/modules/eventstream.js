/* Listen for Server Sent Events */
moj.Modules.eventStream = {
  eventsPath: '/events/',
  eventSource: null,
  listenerClass: '.sse-listener',

  init() {
    const listeners = document.querySelectorAll(this.listenerClass);
    if (listeners) {
      this.eventSource = new EventSource(this.eventsPath);
    }
  },

  addEventListener(type, listener, options) {
    this.eventSource.addEventListener(type, listener, options);
  }
};
