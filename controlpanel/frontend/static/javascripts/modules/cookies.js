moj.Modules.cookies = {
  read(name) {
    const nameEQ = `${encodeURIComponent(name)}=`;
    const cookies = document.cookie.split(/\s*;\s*/);
    const matchCookie = cookies.find(cookie => cookie.startsWith(nameEQ));
    let cookieValue;

    if (matchCookie) {
      cookieValue = decodeURIComponent(matchCookie.substring(nameEQ.length, matchCookie.length));
    }
    return cookieValue;
  },

  store(name, value, days) {
    let expires;
    const dayInMS = 24 * 60 * 60 * 1000;

    if (days) {
      const date = new Date();
      date.setTime(date.getTime() + (days * dayInMS));
      expires = `; expires=${encodeURIComponent(date.toGMTString())}`;
    } else {
      expires = '';
    }
    document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}${expires}; path=/`;
  },

  erase(name) {
    this.store(name, '', -1);
  },
};
